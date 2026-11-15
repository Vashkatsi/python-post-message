import json

import httpx2
import pytest
import respx
from pydantic import SecretStr, ValidationError

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.platforms.huggingface import (
    HuggingFacePublisher,
    HuggingFaceSettings,
    RepoType,
)

SPACE_ENDPOINT = "https://huggingface.co/api/spaces/demo/launch/discussions"
MESSAGE = Message("Grow your visibility: https://example.com.")


def make_publisher(client: httpx2.AsyncClient, repo_type: RepoType) -> HuggingFacePublisher:
    settings = HuggingFaceSettings(
        token=SecretStr("hf_token"), repo_id="demo/launch", repo_type=repo_type
    )
    return HuggingFacePublisher(client, settings)


@pytest.fixture
def publisher(client: httpx2.AsyncClient) -> HuggingFacePublisher:
    return make_publisher(client, "space")


@respx.mock
async def test_creates_discussion_on_space(publisher: HuggingFacePublisher) -> None:
    route = respx.post(SPACE_ENDPOINT).respond(
        200,
        json={
            "url": "https://huggingface.co/spaces/demo/launch/discussions/3",
            "num": 3,
            "pullRequest": False,
        },
    )

    post = await publisher.publish(MESSAGE)

    assert post == PublishedPost(
        url="https://huggingface.co/spaces/demo/launch/discussions/3", published_at=None
    )
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer hf_token"
    assert json.loads(request.content) == {
        "title": "Grow your visibility",
        "description": MESSAGE.text,
        "pullRequest": False,
    }


@pytest.mark.parametrize(
    ("repo_type", "api_segment", "web_url"),
    [
        ("model", "models", "https://huggingface.co/demo/launch/discussions/7"),
        ("dataset", "datasets", "https://huggingface.co/datasets/demo/launch/discussions/7"),
        ("space", "spaces", "https://huggingface.co/spaces/demo/launch/discussions/7"),
    ],
)
@respx.mock
async def test_builds_web_url_per_repo_type(
    client: httpx2.AsyncClient, repo_type: RepoType, api_segment: str, web_url: str
) -> None:
    respx.post(f"https://huggingface.co/api/{api_segment}/demo/launch/discussions").respond(
        200, json={"num": 7, "pullRequest": False, "url": "/ignored"}
    )

    post = await make_publisher(client, repo_type).publish(MESSAGE)

    assert post.url == web_url


@respx.mock
async def test_falls_back_to_full_text_when_title_would_be_too_short(
    publisher: HuggingFacePublisher,
) -> None:
    route = respx.post(SPACE_ENDPOINT).respond(200, json={"num": 2, "pullRequest": False})
    link_only = Message("Go https://example.com")

    await publisher.publish(link_only)

    assert json.loads(route.calls.last.request.content)["title"] == link_only.text


@respx.mock
async def test_reports_missing_write_permission(publisher: HuggingFacePublisher) -> None:
    respx.post(SPACE_ENDPOINT).respond(403, json={"error": "You don't have the rights"})

    with pytest.raises(PublicationError, match=r"Authentication failed.*rights"):
        await publisher.publish(MESSAGE)


def test_rejects_repo_id_without_namespace() -> None:
    with pytest.raises(ValidationError):
        HuggingFaceSettings(token=SecretStr("hf_token"), repo_id="launch")
