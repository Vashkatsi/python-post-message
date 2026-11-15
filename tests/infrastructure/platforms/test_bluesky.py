import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
import respx
from pydantic import SecretStr

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.platforms.bluesky import BlueskyPublisher, BlueskySettings

SESSION_ENDPOINT = "https://pds.example/xrpc/com.atproto.server.createSession"
RECORD_ENDPOINT = "https://pds.example/xrpc/com.atproto.repo.createRecord"
NOW = datetime(2026, 11, 15, 10, 21, 7, 123000, tzinfo=UTC)
MESSAGE = Message("Grow your visibility https://example.com")
DID = "did:plc:u5cwb2mwiv2bfq53cjufe6yn"
SESSION = {
    "did": DID,
    "handle": "alice.bsky.social",
    "accessJwt": "access-jwt",
    "refreshJwt": "refresh-jwt",
    "active": True,
}
CREATED_RECORD = {
    "uri": f"at://{DID}/app.bsky.feed.post/3k4duaz5vfs2b",
    "cid": "bafyreibjifzpqj6o6wcq3hejh7y4z4z2vmiklkvykc57tw3pcbx3kxifpm",
}


@dataclass(frozen=True, slots=True)
class FixedClock:
    def now(self) -> datetime:
        return NOW


@dataclass(slots=True)
class AdjustableClock:
    moment: datetime

    def now(self) -> datetime:
        return self.moment


SETTINGS = BlueskySettings(
    handle="alice.bsky.social",
    app_password=SecretStr("abcd-efgh-ijkl-mnop"),
    service_url="https://pds.example",
)


@pytest.fixture
def publisher(client: httpx2.AsyncClient) -> BlueskyPublisher:
    return BlueskyPublisher(client, SETTINGS, FixedClock())


@respx.mock
async def test_publishes_post_with_link_facet(publisher: BlueskyPublisher) -> None:
    session_route = respx.post(SESSION_ENDPOINT).respond(200, json=SESSION)
    record_route = respx.post(RECORD_ENDPOINT).respond(200, json=CREATED_RECORD)

    post = await publisher.publish(MESSAGE)

    assert post == PublishedPost(
        url="https://bsky.app/profile/alice.bsky.social/post/3k4duaz5vfs2b",
        published_at=NOW,
    )
    session_request = session_route.calls.last.request
    assert "Authorization" not in session_request.headers
    assert json.loads(session_request.content) == {
        "identifier": "alice.bsky.social",
        "password": "abcd-efgh-ijkl-mnop",
    }
    record_request = record_route.calls.last.request
    assert record_request.headers["Authorization"] == "Bearer access-jwt"
    assert json.loads(record_request.content) == {
        "repo": DID,
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": MESSAGE.text,
            "createdAt": "2026-11-15T10:21:07.123Z",
            "facets": [
                {
                    "index": {"byteStart": 21, "byteEnd": 40},
                    "features": [
                        {"$type": "app.bsky.richtext.facet#link", "uri": "https://example.com"}
                    ],
                }
            ],
        },
    }


@respx.mock
async def test_link_facet_uses_utf8_byte_offsets(publisher: BlueskyPublisher) -> None:
    respx.post(SESSION_ENDPOINT).respond(200, json=SESSION)
    record_route = respx.post(RECORD_ENDPOINT).respond(200, json=CREATED_RECORD)
    message = Message("Привет 🚀 https://example.com")

    await publisher.publish(message)

    record = json.loads(record_route.calls.last.request.content)["record"]
    assert record["facets"][0]["index"] == {"byteStart": 18, "byteEnd": 37}
    assert message.text.encode()[18:37] == b"https://example.com"


@respx.mock
async def test_reports_invalid_credentials(publisher: BlueskyPublisher) -> None:
    respx.post(SESSION_ENDPOINT).respond(
        401,
        json={"error": "AuthenticationRequired", "message": "Invalid identifier or password"},
    )
    record_route = respx.post(RECORD_ENDPOINT)

    with pytest.raises(
        PublicationError, match=r"Authentication failed.*Invalid identifier or password"
    ):
        await publisher.publish(MESSAGE)
    assert not record_route.called


@respx.mock
async def test_reports_rejected_record(publisher: BlueskyPublisher) -> None:
    respx.post(SESSION_ENDPOINT).respond(200, json=SESSION)
    respx.post(RECORD_ENDPOINT).respond(
        400, json={"error": "InvalidRequest", "message": "Invalid app.bsky.feed.post record"}
    )

    with pytest.raises(PublicationError, match=r"Request rejected.*Invalid app\.bsky\.feed\.post"):
        await publisher.publish(MESSAGE)


@respx.mock
async def test_rejects_unexpected_record_uri(publisher: BlueskyPublisher) -> None:
    respx.post(SESSION_ENDPOINT).respond(200, json=SESSION)
    respx.post(RECORD_ENDPOINT).respond(200, json={"uri": "https://example.com/post"})

    with pytest.raises(PublicationError, match="Unexpected response format"):
        await publisher.publish(MESSAGE)


@respx.mock
async def test_reuses_the_session_until_it_should_be_renewed(client: httpx2.AsyncClient) -> None:
    session_route = respx.post(SESSION_ENDPOINT).respond(200, json=SESSION)
    respx.post(RECORD_ENDPOINT).respond(200, json=CREATED_RECORD)
    clock = AdjustableClock(NOW)
    publisher = BlueskyPublisher(client, SETTINGS, clock)

    await publisher.publish(MESSAGE)
    clock.moment = NOW + timedelta(minutes=59)
    await publisher.publish(MESSAGE)
    assert session_route.call_count == 1

    clock.moment = NOW + timedelta(minutes=61)
    await publisher.publish(MESSAGE)
    assert session_route.call_count == 2


@respx.mock
async def test_logs_in_again_after_a_rejected_record(publisher: BlueskyPublisher) -> None:
    session_route = respx.post(SESSION_ENDPOINT).respond(200, json=SESSION)
    record_route = respx.post(RECORD_ENDPOINT).respond(
        400, json={"error": "ExpiredToken", "message": "Token has expired"}
    )

    with pytest.raises(PublicationError, match="Token has expired"):
        await publisher.publish(MESSAGE)
    record_route.respond(200, json=CREATED_RECORD)
    await publisher.publish(MESSAGE)

    assert session_route.call_count == 2
