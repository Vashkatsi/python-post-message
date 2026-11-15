from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

import httpx2
from pydantic import BaseModel, SecretStr

from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.http import send_for_model

_ENDPOINT = "https://api.github.com/gists"
_API_VERSION = "2026-03-10"
_FILENAME = "message.md"


class GithubGistSettings(BaseModel):
    token: SecretStr


class _Gist(BaseModel):
    html_url: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class GithubGistPublisher:
    name: ClassVar[str] = "GitHub Gist"

    client: httpx2.AsyncClient
    settings: GithubGistSettings

    async def publish(self, message: Message) -> PublishedPost:
        request = self.client.build_request(
            "POST",
            _ENDPOINT,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.settings.token.get_secret_value()}",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            json={
                "description": message.text,
                "public": True,
                "files": {_FILENAME: {"content": message.text}},
            },
        )
        gist = await send_for_model(self.client, request, _Gist)
        return PublishedPost(url=gist.html_url, published_at=gist.created_at)
