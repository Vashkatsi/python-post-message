from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

import httpx2
from pydantic import BaseModel, HttpUrl, SecretStr

from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.http import send_for_model

_API_V1_MEDIA_TYPE = "application/vnd.forem.api-v1+json"
_MAX_TITLE_LENGTH = 80
_TITLE_EDGE_CHARACTERS = " .,:;-|/"


class DevtoSettings(BaseModel):
    base_url: HttpUrl = HttpUrl("https://dev.to")
    api_key: SecretStr


class _Article(BaseModel):
    url: str
    published_at: datetime | None = None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DevtoPublisher:
    name: ClassVar[str] = "DEV Community"

    client: httpx2.AsyncClient
    settings: DevtoSettings

    async def publish(self, message: Message) -> PublishedPost:
        request = self.client.build_request(
            "POST",
            httpx2.URL(str(self.settings.base_url)).join("/api/articles"),
            headers={
                "api-key": self.settings.api_key.get_secret_value(),
                "Accept": _API_V1_MEDIA_TYPE,
            },
            json={
                "article": {
                    "title": _derive_title(message),
                    "body_markdown": message.text,
                    "published": True,
                }
            },
        )
        article = await send_for_model(self.client, request, _Article)
        return PublishedPost(
            url=article.url, published_at=article.published_at or article.created_at
        )


def _derive_title(message: Message) -> str:
    return _truncate_at_word_boundary(message.headline, _MAX_TITLE_LENGTH).rstrip(
        _TITLE_EDGE_CHARACTERS
    )


def _truncate_at_word_boundary(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    truncated = text[: max_length + 1]
    head, separator, _ = truncated.rpartition(" ")
    return head if separator else text[:max_length]
