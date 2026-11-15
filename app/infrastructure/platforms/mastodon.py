from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

import httpx2
from pydantic import BaseModel, HttpUrl, SecretStr

from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.http import send_for_model


class MastodonSettings(BaseModel):
    base_url: HttpUrl = HttpUrl("https://mastodon.social")
    access_token: SecretStr


class _Status(BaseModel):
    url: str | None
    uri: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MastodonPublisher:
    name: ClassVar[str] = "Mastodon"

    client: httpx2.AsyncClient
    settings: MastodonSettings

    async def publish(self, message: Message) -> PublishedPost:
        request = self.client.build_request(
            "POST",
            httpx2.URL(str(self.settings.base_url)).join("/api/v1/statuses"),
            headers={
                "Authorization": f"Bearer {self.settings.access_token.get_secret_value()}",
                "Idempotency-Key": message.fingerprint,
            },
            json={"status": message.text, "visibility": "public"},
        )
        status = await send_for_model(self.client, request, _Status)
        return PublishedPost(url=status.url or status.uri, published_at=status.created_at)
