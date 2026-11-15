import json
from datetime import UTC, datetime

import httpx2
import pytest
import respx
from pydantic import SecretStr

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.platforms.devto import DevtoPublisher, DevtoSettings

ENDPOINT = "https://forem.example/api/articles"
MESSAGE = Message("Release notes are out: https://example.com/notes")
CREATED_ARTICLE = {
    "url": "https://forem.example/demo/post",
    "created_at": "2026-11-15T09:30:10Z",
    "published_at": "2026-11-15T09:30:12Z",
}


@pytest.fixture
def publisher(client: httpx2.AsyncClient) -> DevtoPublisher:
    settings = DevtoSettings(base_url="https://forem.example", api_key=SecretStr("secret-key"))
    return DevtoPublisher(client, settings)


@respx.mock
async def test_publishes_article(publisher: DevtoPublisher) -> None:
    route = respx.post(ENDPOINT).respond(
        201,
        json={
            "id": 2345678,
            "url": "https://forem.example/demo/release-notes-are-out-3kd9",
            "created_at": "2026-11-15T09:30:10Z",
            "published_at": "2026-11-15T09:30:12Z",
        },
    )

    post = await publisher.publish(MESSAGE)

    assert post == PublishedPost(
        url="https://forem.example/demo/release-notes-are-out-3kd9",
        published_at=datetime(2026, 11, 15, 9, 30, 12, tzinfo=UTC),
    )
    request = route.calls.last.request
    assert request.headers["api-key"] == "secret-key"
    assert request.headers["Accept"] == "application/vnd.forem.api-v1+json"
    assert "Authorization" not in request.headers
    assert json.loads(request.content) == {
        "article": {
            "title": "Release notes are out",
            "body_markdown": MESSAGE.text,
            "published": True,
        }
    }


@respx.mock
async def test_falls_back_to_creation_time_without_publish_time(
    publisher: DevtoPublisher,
) -> None:
    respx.post(ENDPOINT).respond(
        201,
        json={
            "url": "https://forem.example/demo/post",
            "created_at": "2026-11-15T09:30:10Z",
            "published_at": None,
        },
    )

    post = await publisher.publish(MESSAGE)

    assert post.published_at == datetime(2026, 11, 15, 9, 30, 10, tzinfo=UTC)


@respx.mock
async def test_reports_invalid_api_key(publisher: DevtoPublisher) -> None:
    respx.post(ENDPOINT).respond(401, json={"error": "unauthorized", "status": 401})

    with pytest.raises(PublicationError, match=r"Authentication failed.*unauthorized"):
        await publisher.publish(MESSAGE)


@respx.mock
async def test_reports_validation_failure(publisher: DevtoPublisher) -> None:
    respx.post(ENDPOINT).respond(422, json={"error": "Title can't be blank", "status": 422})

    with pytest.raises(PublicationError, match=r"Request rejected \(HTTP 422\).*can't be blank"):
        await publisher.publish(MESSAGE)


@respx.mock
async def test_reports_plain_text_rate_limit(publisher: DevtoPublisher) -> None:
    respx.post(ENDPOINT).respond(429, text="Retry later\n", headers={"Retry-After": "1"})

    with pytest.raises(PublicationError, match=r"Rate limit exceeded \(HTTP 429\): Retry later"):
        await publisher.publish(MESSAGE)


@pytest.mark.parametrize(
    ("text", "expected_title"),
    [
        ("https://example.com/notes", "example.com"),
        ("https://example.com/notes - :", "example.com"),
        ("- Read   this\nnow https://example.com/notes today.", "Read this now today"),
        ("Visit https://example.com, please", "Visit please"),
        ("Grow your visibility (https://example.com)", "Grow your visibility"),
        (f"{' '.join(['visibility'] * 15)} https://example.com", " ".join(["visibility"] * 7)),
        (f"{'a' * 150} https://example.com", "a" * 80),
    ],
)
@respx.mock
async def test_derives_title_from_text_without_link(
    publisher: DevtoPublisher, text: str, expected_title: str
) -> None:
    route = respx.post(ENDPOINT).respond(201, json=CREATED_ARTICLE)

    await publisher.publish(Message(text))

    assert json.loads(route.calls.last.request.content)["article"]["title"] == expected_title
