import json
from datetime import UTC, datetime

import httpx2
import pytest
import respx
from pydantic import SecretStr, ValidationError

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.platforms.telegram import TelegramPublisher, TelegramSettings

ENDPOINT = "https://api.telegram.org/bot123456:ABC-secret/sendMessage"
MESSAGE = Message("Grow your visibility https://example.com")


@pytest.fixture
def publisher(client: httpx2.AsyncClient) -> TelegramPublisher:
    settings = TelegramSettings(
        bot_token=SecretStr("123456:ABC-secret"), channel_username="@demo_channel"
    )
    return TelegramPublisher(client, settings)


def sent_message(chat: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "result": {
            "message_id": 42,
            "sender_chat": {"id": -1001234567890, "type": "channel", **chat},
            "chat": {"id": -1001234567890, "type": "channel", **chat},
            "date": 1794738067,
            "text": MESSAGE.text,
        },
    }


@respx.mock
async def test_posts_message_to_channel(publisher: TelegramPublisher) -> None:
    route = respx.post(ENDPOINT).respond(200, json=sent_message({"username": "demo_channel"}))

    post = await publisher.publish(MESSAGE)

    assert post == PublishedPost(
        url="https://t.me/demo_channel/42",
        published_at=datetime(2026, 11, 15, 10, 21, 7, tzinfo=UTC),
    )
    request = route.calls.last.request
    assert "Authorization" not in request.headers
    assert json.loads(request.content) == {
        "chat_id": "@demo_channel",
        "text": MESSAGE.text,
        "link_preview_options": {"url": "https://example.com"},
    }


@respx.mock
async def test_falls_back_to_configured_username(publisher: TelegramPublisher) -> None:
    respx.post(ENDPOINT).respond(200, json=sent_message({"title": "Demo"}))

    post = await publisher.publish(MESSAGE)

    assert post.url == "https://t.me/demo_channel/42"


@respx.mock
async def test_reports_missing_channel_rights(publisher: TelegramPublisher) -> None:
    respx.post(ENDPOINT).respond(
        403,
        json={
            "ok": False,
            "error_code": 403,
            "description": "Forbidden: bot is not a member of the channel chat",
        },
    )

    with pytest.raises(PublicationError, match=r"Authentication failed.*not a member") as error:
        await publisher.publish(MESSAGE)

    assert "ABC-secret" not in str(error.value)


@respx.mock
async def test_rejects_unsuccessful_envelope(publisher: TelegramPublisher) -> None:
    respx.post(ENDPOINT).respond(200, json={"ok": False, "description": "Bad Request"})

    with pytest.raises(PublicationError, match="Unexpected response format"):
        await publisher.publish(MESSAGE)


def test_rejects_invalid_channel_username() -> None:
    with pytest.raises(ValidationError):
        TelegramSettings(bot_token=SecretStr("token"), channel_username="bad/name")
