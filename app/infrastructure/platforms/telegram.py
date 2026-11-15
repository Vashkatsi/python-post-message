from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, ClassVar, Literal

import httpx2
from pydantic import BaseModel, BeforeValidator, HttpUrl, PositiveInt, SecretStr, StringConstraints

from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.http import send_for_model


def _without_at_sign(value: object) -> object:
    match value:
        case str():
            return value.strip().removeprefix("@")
        case _:
            return value


type ChannelUsername = Annotated[
    str,
    BeforeValidator(_without_at_sign),
    StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]{3,31}$"),
]


class TelegramSettings(BaseModel):
    base_url: HttpUrl = HttpUrl("https://api.telegram.org")
    bot_token: SecretStr
    channel_username: ChannelUsername


class _Chat(BaseModel):
    username: str | None = None


class _SentMessage(BaseModel):
    message_id: PositiveInt
    date: datetime
    chat: _Chat


class _SendMessageResponse(BaseModel):
    ok: Literal[True]
    result: _SentMessage


@dataclass(frozen=True, slots=True)
class TelegramPublisher:
    name: ClassVar[str] = "Telegram"

    client: httpx2.AsyncClient
    settings: TelegramSettings

    async def publish(self, message: Message) -> PublishedPost:
        request = self.client.build_request(
            "POST",
            httpx2.URL(str(self.settings.base_url)).join(
                f"/bot{self.settings.bot_token.get_secret_value()}/sendMessage"
            ),
            json={
                "chat_id": f"@{self.settings.channel_username}",
                "text": message.text,
                "link_preview_options": {"url": message.cta_url},
            },
        )
        response = await send_for_model(self.client, request, _SendMessageResponse)
        sent_message = response.result
        username = sent_message.chat.username or self.settings.channel_username
        return PublishedPost(
            url=f"https://t.me/{username}/{sent_message.message_id}",
            published_at=sent_message.date,
        )
