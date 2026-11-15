from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest

from app.api.dependencies import get_posting_service
from app.application.posting_service import PostingService
from app.domain.message import Message
from app.domain.publication import (
    PublicationFailed,
    PublicationReport,
    PublicationResult,
    PublicationSucceeded,
)
from app.main import create_app

VALID_MESSAGE = "Grow your online visibility https://example.com"


class PostingServiceStub(PostingService):
    def __init__(self, results: tuple[PublicationResult, ...]) -> None:
        self.results = results
        self.received: list[Message] = []

    async def post(self, message: Message) -> PublicationReport:
        self.received.append(message)
        return PublicationReport(self.results)


def api_client(service: PostingService) -> httpx.AsyncClient:
    app = create_app()
    app.dependency_overrides[get_posting_service] = lambda: service
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def mixed_service() -> PostingServiceStub:
    return PostingServiceStub(
        (
            PublicationSucceeded(
                "Mastodon",
                "https://mastodon.social/@demo/1",
                True,
                datetime(2026, 11, 15, 10, 30, 0, 123456, tzinfo=UTC),
            ),
            PublicationFailed("Telegram", "Authentication failed (HTTP 401)"),
        )
    )


@pytest.fixture
async def client(mixed_service: PostingServiceStub) -> AsyncIterator[httpx.AsyncClient]:
    async with api_client(mixed_service) as http_client:
        yield http_client


async def test_returns_per_platform_results(
    client: httpx.AsyncClient, mixed_service: PostingServiceStub
) -> None:
    response = await client.post("/posting", json={"message": f"  {VALID_MESSAGE} "})

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "results": [
            {
                "platform": "Mastodon",
                "status": "success",
                "posted_url": "https://mastodon.social/@demo/1",
                "public_access": True,
                "date": "2026-11-15",
                "time": "10:30:00",
                "error": None,
            },
            {
                "platform": "Telegram",
                "status": "failed",
                "posted_url": None,
                "public_access": False,
                "date": None,
                "time": None,
                "error": "Authentication failed (HTTP 401)",
            },
        ],
    }
    assert mixed_service.received == [Message(VALID_MESSAGE)]


async def test_returns_bad_gateway_when_every_platform_fails() -> None:
    service = PostingServiceStub((PublicationFailed("Telegram", "Not configured"),))

    async with api_client(service) as client:
        response = await client.post("/posting", json={"message": VALID_MESSAGE})

    assert response.status_code == 502
    assert response.json()["success"] is False


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        (
            {"message": "No link at all"},
            "message",
            "Message must contain exactly one CTA link, found 0",
        ),
        ({"message": "x" * 201}, "message", "Message must not exceed 200 characters, got 201"),
        (
            {"message": "Bad https://exa_mple.com"},
            "message",
            "CTA link is not a valid absolute http(s) URL: https://exa_mple.com",
        ),
        ({"message": 42}, "message", "Message must be a string"),
        ({}, "message", "Field required"),
        (
            {"message": VALID_MESSAGE, "platforms": ["x"]},
            "platforms",
            "Extra inputs are not permitted",
        ),
    ],
)
async def test_rejects_invalid_input(
    client: httpx.AsyncClient,
    mixed_service: PostingServiceStub,
    payload: dict[str, object],
    field: str,
    message: str,
) -> None:
    response = await client.post("/posting", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": [{"field": field, "message": message}]}
    assert mixed_service.received == []


async def test_rejects_malformed_json(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/posting", content=b"{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422


async def test_documents_the_endpoint(client: httpx.AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()

    operation = schema["paths"]["/posting"]["post"]
    assert set(operation["responses"]) >= {"200", "422", "502"}
    components = schema["components"]["schemas"]
    assert components["PostingRequest"]["properties"]["message"] == {
        "$ref": "#/components/schemas/MessageText"
    }
    assert components["MessageText"]["maxLength"] == 200
