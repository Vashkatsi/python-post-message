import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, ClassVar

import httpx2
from pydantic import BaseModel, Field, HttpUrl, SecretStr

from app.application.ports import Clock, PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost
from app.infrastructure.http import send_for_model

_POST_COLLECTION = "app.bsky.feed.post"
_LINK_FEATURE = "app.bsky.richtext.facet#link"
_SESSION_REUSE_PERIOD = timedelta(minutes=60)


class BlueskySettings(BaseModel):
    handle: str
    app_password: SecretStr
    service_url: HttpUrl = HttpUrl("https://bsky.social")


class _Session(BaseModel):
    did: str
    handle: str
    access_jwt: Annotated[SecretStr, Field(alias="accessJwt")]


class _CreatedRecord(BaseModel):
    uri: Annotated[str, Field(pattern=r"^at://[^/]+/app\.bsky\.feed\.post/[^/]+$")]

    @property
    def record_key(self) -> str:
        return self.uri.rpartition("/")[2]


@dataclass(frozen=True, slots=True)
class _CachedSession:
    session: _Session
    expires_at: datetime


@dataclass(slots=True)
class BlueskySessionCache:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    entry: _CachedSession | None = None


@dataclass(frozen=True, slots=True)
class BlueskyPublisher:
    name: ClassVar[str] = "Bluesky"

    client: httpx2.AsyncClient
    settings: BlueskySettings
    clock: Clock
    session_cache: BlueskySessionCache = field(default_factory=BlueskySessionCache)

    async def publish(self, message: Message) -> PublishedPost:
        session = await self._current_session()
        created_at = self.clock.now()
        try:
            record = await self._create_post(session, message, created_at)
        except PublicationError:
            await self._forget_session()
            raise
        return PublishedPost(
            url=f"https://bsky.app/profile/{session.handle}/post/{record.record_key}",
            published_at=created_at,
        )

    async def _current_session(self) -> _Session:
        async with self.session_cache.lock:
            now = self.clock.now()
            cached = self.session_cache.entry
            if cached is not None and now < cached.expires_at:
                return cached.session
            session = await self._create_session()
            self.session_cache.entry = _CachedSession(session, now + _SESSION_REUSE_PERIOD)
            return session

    async def _forget_session(self) -> None:
        async with self.session_cache.lock:
            self.session_cache.entry = None

    async def _create_session(self) -> _Session:
        request = self.client.build_request(
            "POST",
            self._xrpc_url("com.atproto.server.createSession"),
            json={
                "identifier": self.settings.handle,
                "password": self.settings.app_password.get_secret_value(),
            },
        )
        return await send_for_model(self.client, request, _Session)

    async def _create_post(
        self, session: _Session, message: Message, created_at: datetime
    ) -> _CreatedRecord:
        request = self.client.build_request(
            "POST",
            self._xrpc_url("com.atproto.repo.createRecord"),
            headers={"Authorization": f"Bearer {session.access_jwt.get_secret_value()}"},
            json={
                "repo": session.did,
                "collection": _POST_COLLECTION,
                "record": {
                    "$type": _POST_COLLECTION,
                    "text": message.text,
                    "createdAt": _format_timestamp(created_at),
                    "facets": [_link_facet(message)],
                },
            },
        )
        return await send_for_model(self.client, request, _CreatedRecord)

    def _xrpc_url(self, method: str) -> httpx2.URL:
        return httpx2.URL(str(self.settings.service_url)).join(f"/xrpc/{method}")


def _link_facet(message: Message) -> dict[str, object]:
    byte_start = len(message.text[: message.text.index(message.cta_url)].encode())
    return {
        "index": {"byteStart": byte_start, "byteEnd": byte_start + len(message.cta_url.encode())},
        "features": [{"$type": _LINK_FEATURE, "uri": message.cta_url}],
    }


def _format_timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
