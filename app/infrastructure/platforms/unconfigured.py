from dataclasses import dataclass

from app.application.ports import PublicationError
from app.domain.message import Message
from app.domain.publication import PublishedPost


@dataclass(frozen=True, slots=True)
class UnconfiguredPublisher:
    name: str
    required_settings: tuple[str, ...]

    async def publish(self, message: Message) -> PublishedPost:
        raise PublicationError(f"Not configured, set {', '.join(self.required_settings)}")
