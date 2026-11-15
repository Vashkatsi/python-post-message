from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

import httpx2
from pydantic import BaseModel, Field, RootModel, SecretStr

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.http import send_for_model

_CREATE_PAGE_URL = "https://api.telegra.ph/createPage"

type _ContentNode = str | dict[str, object]


class TelegraphSettings(BaseModel):
    access_token: SecretStr
    author_name: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class _Page(BaseModel):
    url: str


class _PageCreated(BaseModel):
    ok: Literal[True]
    result: _Page


class _PageRejected(BaseModel):
    ok: Literal[False]
    error: str


class _CreatePageResponse(
    RootModel[Annotated[_PageCreated | _PageRejected, Field(discriminator="ok")]]
):
    pass


@dataclass(frozen=True, slots=True)
class TelegraphPublisher:
    name: ClassVar[str] = "Telegraph"

    client: httpx2.AsyncClient
    settings: TelegraphSettings

    async def publish(self, message: Message) -> PublishedPost:
        request = self.client.build_request(
            "POST", _CREATE_PAGE_URL, json=self._page_payload(message)
        )
        response = await send_for_model(self.client, request, _CreatePageResponse)
        match response.root:
            case _PageRejected(error=error):
                raise PublicationError(_describe_rejection(error))
            case _PageCreated(result=page):
                return PublishedPost(url=page.url)

    def _page_payload(self, message: Message) -> dict[str, object]:
        payload: dict[str, object] = {
            "access_token": self.settings.access_token.get_secret_value(),
            "title": message.headline,
            "content": _build_content(message),
            "return_content": False,
        }
        if self.settings.author_name is None:
            return payload
        return payload | {"author_name": self.settings.author_name}


def _build_content(message: Message) -> list[_ContentNode]:
    text_before, link, text_after = message.text.partition(message.cta_url)
    link_node: _ContentNode = {"tag": "a", "attrs": {"href": link}, "children": [link]}
    children = [node for node in (text_before, link_node, text_after) if node]
    return [{"tag": "p", "children": children}]


def _describe_rejection(error: str) -> str:
    match error:
        case "ACCESS_TOKEN_INVALID":
            return f"Authentication failed: {error}"
        case rate_limit if rate_limit.startswith("FLOOD_WAIT_"):
            return f"Rate limit exceeded: {error}"
        case _:
            return f"Request rejected: {error}"
