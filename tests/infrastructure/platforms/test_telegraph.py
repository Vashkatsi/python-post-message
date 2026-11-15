import json

import httpx2
import pytest
import respx
from pydantic import SecretStr

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.platforms.telegraph import TelegraphPublisher, TelegraphSettings

ENDPOINT = "https://api.telegra.ph/createPage"
MESSAGE = Message("Grow your visibility https://example.com/launch today:")
PAGE_CREATED = {
    "ok": True,
    "result": {
        "path": "Grow-your-visibility-today-11-15",
        "url": "https://telegra.ph/Grow-your-visibility-today-11-15",
        "title": "Grow your visibility today",
        "views": 0,
        "can_edit": True,
    },
}


@pytest.fixture
def publisher(client: httpx2.AsyncClient) -> TelegraphPublisher:
    settings = TelegraphSettings(access_token=SecretStr("token"), author_name="Demo")
    return TelegraphPublisher(client, settings)


@respx.mock
async def test_creates_page_with_cta_link_node(publisher: TelegraphPublisher) -> None:
    route = respx.post(ENDPOINT).respond(200, json=PAGE_CREATED)

    post = await publisher.publish(MESSAGE)

    assert post == PublishedPost(url="https://telegra.ph/Grow-your-visibility-today-11-15")
    request = route.calls.last.request
    assert "Authorization" not in request.headers
    assert json.loads(request.content) == {
        "access_token": "token",
        "title": "Grow your visibility today",
        "author_name": "Demo",
        "return_content": False,
        "content": [
            {
                "tag": "p",
                "children": [
                    "Grow your visibility ",
                    {
                        "tag": "a",
                        "attrs": {"href": "https://example.com/launch"},
                        "children": ["https://example.com/launch"],
                    },
                    " today:",
                ],
            }
        ],
    }


@respx.mock
async def test_uses_link_host_as_title_and_omits_missing_author(
    client: httpx2.AsyncClient,
) -> None:
    route = respx.post(ENDPOINT).respond(200, json=PAGE_CREATED)
    publisher = TelegraphPublisher(client, TelegraphSettings(access_token=SecretStr("token")))

    await publisher.publish(Message("https://example.com/launch"))

    body = json.loads(route.calls.last.request.content)
    assert body["title"] == "example.com"
    assert "author_name" not in body
    assert body["content"] == [
        {
            "tag": "p",
            "children": [
                {
                    "tag": "a",
                    "attrs": {"href": "https://example.com/launch"},
                    "children": ["https://example.com/launch"],
                }
            ],
        }
    ]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("ACCESS_TOKEN_INVALID", r"Authentication failed: ACCESS_TOKEN_INVALID"),
        ("FLOOD_WAIT_7", r"Rate limit exceeded: FLOOD_WAIT_7"),
        ("CONTENT_TOO_BIG", r"Request rejected: CONTENT_TOO_BIG"),
    ],
)
@respx.mock
async def test_reports_rejection_returned_with_http_ok(
    publisher: TelegraphPublisher, error: str, expected: str
) -> None:
    respx.post(ENDPOINT).respond(200, json={"ok": False, "error": error})

    with pytest.raises(PublicationError, match=expected):
        await publisher.publish(MESSAGE)


@respx.mock
async def test_reports_unavailable_platform(publisher: TelegraphPublisher) -> None:
    respx.post(ENDPOINT).respond(502, text="Bad Gateway")

    with pytest.raises(PublicationError, match=r"Platform is unavailable \(HTTP 502\)"):
        await publisher.publish(MESSAGE)
