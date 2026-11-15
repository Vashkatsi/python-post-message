from datetime import datetime
from typing import Protocol

from app.domain.message import Message
from app.domain.publication import PublishedPost


class PublicationError(Exception):
    pass


class Publisher(Protocol):
    @property
    def name(self) -> str: ...

    async def publish(self, message: Message) -> PublishedPost: ...


class AccessChecker(Protocol):
    async def is_public(self, url: str) -> bool: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
