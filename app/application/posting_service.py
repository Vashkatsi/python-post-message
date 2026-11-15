import asyncio
from collections.abc import Sequence
from datetime import UTC

from app.application.ports import AccessChecker, Clock, PublicationError, Publisher
from app.domain.message import Message
from app.domain.publication import (
    PublicationFailed,
    PublicationReport,
    PublicationResult,
    PublicationSucceeded,
)


class PostingService:
    def __init__(
        self,
        publishers: Sequence[Publisher],
        access_checker: AccessChecker,
        clock: Clock,
        publish_timeout_seconds: float,
    ) -> None:
        self._publishers = tuple(publishers)
        self._access_checker = access_checker
        self._clock = clock
        self._publish_timeout_seconds = publish_timeout_seconds

    async def post(self, message: Message) -> PublicationReport:
        async with asyncio.TaskGroup() as task_group:
            tasks = [
                task_group.create_task(self._publish_with_isolation(publisher, message))
                for publisher in self._publishers
            ]
        return PublicationReport(results=tuple(task.result() for task in tasks))

    async def _publish_with_isolation(
        self, publisher: Publisher, message: Message
    ) -> PublicationResult:
        try:
            async with asyncio.timeout(self._publish_timeout_seconds):
                post = await publisher.publish(message)
        except PublicationError as error:
            return PublicationFailed(platform=publisher.name, error=str(error))
        except TimeoutError:
            return PublicationFailed(
                platform=publisher.name,
                error=f"Timed out after {self._publish_timeout_seconds:g} seconds",
            )
        except Exception as error:
            return PublicationFailed(
                platform=publisher.name, error=f"Unexpected error: {type(error).__name__}"
            )
        return PublicationSucceeded(
            platform=publisher.name,
            posted_url=post.url,
            public_access=await self._access_checker.is_public(post.url),
            published_at=(post.published_at or self._clock.now()).astimezone(UTC),
        )
