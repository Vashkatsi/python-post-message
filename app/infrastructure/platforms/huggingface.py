from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

import httpx2
from pydantic import BaseModel, SecretStr, StringConstraints

from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.http import send_for_model

_HUB_URL = httpx2.URL("https://huggingface.co")
_MIN_TITLE_LENGTH = 3

type RepoType = Literal["model", "dataset", "space"]


class HuggingFaceSettings(BaseModel):
    token: SecretStr
    repo_id: Annotated[str, StringConstraints(pattern=r"^[\w.-]+/[\w.-]+$")]
    repo_type: RepoType = "space"


class _CreatedDiscussion(BaseModel):
    num: int


@dataclass(frozen=True, slots=True)
class HuggingFacePublisher:
    name: ClassVar[str] = "Hugging Face"

    client: httpx2.AsyncClient
    settings: HuggingFaceSettings

    async def publish(self, message: Message) -> PublishedPost:
        repo_id = self.settings.repo_id
        request = self.client.build_request(
            "POST",
            _HUB_URL.join(f"/api/{self.settings.repo_type}s/{repo_id}/discussions"),
            headers={"Authorization": f"Bearer {self.settings.token.get_secret_value()}"},
            json={
                "title": _discussion_title(message),
                "description": message.text,
                "pullRequest": False,
            },
        )
        discussion = await send_for_model(self.client, request, _CreatedDiscussion)
        return PublishedPost(
            url=str(
                _HUB_URL.join(
                    f"/{_web_repo_path(self.settings.repo_type, repo_id)}"
                    f"/discussions/{discussion.num}"
                )
            )
        )


def _discussion_title(message: Message) -> str:
    if len(message.headline) < _MIN_TITLE_LENGTH:
        return message.text
    return message.headline


def _web_repo_path(repo_type: RepoType, repo_id: str) -> str:
    match repo_type:
        case "model":
            return repo_id
        case "dataset" | "space":
            return f"{repo_type}s/{repo_id}"
