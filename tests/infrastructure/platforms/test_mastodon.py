import json
from datetime import UTC, datetime

import httpx2
import pytest
import respx
from pydantic import SecretStr

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.platforms.mastodon import MastodonPublisher, MastodonSettings

ENDPOINT = "https://mastodon.example/api/v1/statuses"
MESSAGE = Message("Grow your visibility https://example.com")


@pytest.fixture
def publisher(client: httpx2.AsyncClient) -> MastodonPublisher:
    settings = MastodonSettings(
        base_url="https://mastodon.example", access_token=SecretStr("token")
    )
    return MastodonPublisher(client, settings)


@respx.mock
async def test_publishes_public_status(publisher: MastodonPublisher) -> None:
    route = respx.post(ENDPOINT).respond(
        200,
        json={
            "id": "113523456789012345",
            "url": "https://mastodon.example/@demo/113523456789012345",
            "uri": "https://mastodon.example/users/demo/statuses/113523456789012345",
            "created_at": "2026-11-15T10:21:07.123Z",
        },
    )

    post = await publisher.publish(MESSAGE)

    assert post == PublishedPost(
        url="https://mastodon.example/@demo/113523456789012345",
        published_at=datetime(2026, 11, 15, 10, 21, 7, 123000, tzinfo=UTC),
    )
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer token"
    assert request.headers["Idempotency-Key"] == MESSAGE.fingerprint
    assert json.loads(request.content) == {"status": MESSAGE.text, "visibility": "public"}


@respx.mock
async def test_falls_back_to_uri_when_url_is_missing(publisher: MastodonPublisher) -> None:
    respx.post(ENDPOINT).respond(
        200,
        json={
            "url": None,
            "uri": "https://mastodon.example/users/demo/statuses/1",
            "created_at": "2026-11-15T10:21:07Z",
        },
    )

    post = await publisher.publish(MESSAGE)

    assert post.url == "https://mastodon.example/users/demo/statuses/1"


@respx.mock
async def test_reports_invalid_token(publisher: MastodonPublisher) -> None:
    respx.post(ENDPOINT).respond(401, json={"error": "The access token is invalid"})

    with pytest.raises(PublicationError, match=r"Authentication failed.*access token is invalid"):
        await publisher.publish(MESSAGE)
