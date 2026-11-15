import json
from datetime import UTC, datetime

import httpx2
import pytest
import respx
from pydantic import SecretStr

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.platforms.github_gist import GithubGistPublisher, GithubGistSettings

ENDPOINT = "https://api.github.com/gists"
MESSAGE = Message("Grow your visibility https://example.com")


@pytest.fixture
def publisher(client: httpx2.AsyncClient) -> GithubGistPublisher:
    return GithubGistPublisher(client, GithubGistSettings(token=SecretStr("token")))


@respx.mock
async def test_publishes_public_markdown_gist(publisher: GithubGistPublisher) -> None:
    route = respx.post(ENDPOINT).respond(
        201,
        json={
            "id": "aa5a315d61ae9438b18d",
            "url": "https://api.github.com/gists/aa5a315d61ae9438b18d",
            "html_url": "https://gist.github.com/aa5a315d61ae9438b18d",
            "public": True,
            "created_at": "2026-11-15T12:00:00Z",
        },
    )

    post = await publisher.publish(MESSAGE)

    assert post == PublishedPost(
        url="https://gist.github.com/aa5a315d61ae9438b18d",
        published_at=datetime(2026, 11, 15, 12, 0, tzinfo=UTC),
    )
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer token"
    assert request.headers["Accept"] == "application/vnd.github+json"
    assert request.headers["X-GitHub-Api-Version"] == "2026-03-10"
    assert json.loads(request.content) == {
        "description": MESSAGE.text,
        "public": True,
        "files": {"message.md": {"content": MESSAGE.text}},
    }


@respx.mock
async def test_reports_token_without_gist_permission(publisher: GithubGistPublisher) -> None:
    respx.post(ENDPOINT).respond(
        403,
        json={
            "message": "Resource not accessible by personal access token",
            "documentation_url": "https://docs.github.com/rest/gists/gists#create-a-gist",
            "status": "403",
        },
    )

    with pytest.raises(PublicationError, match=r"Authentication failed.*not accessible"):
        await publisher.publish(MESSAGE)


@respx.mock
async def test_reports_validation_failure(publisher: GithubGistPublisher) -> None:
    respx.post(ENDPOINT).respond(
        422,
        json={
            "message": "Validation Failed",
            "errors": [{"resource": "Gist", "field": "files", "code": "missing_field"}],
        },
    )

    with pytest.raises(PublicationError, match=r"Request rejected \(HTTP 422\): Validation Failed"):
        await publisher.publish(MESSAGE)
