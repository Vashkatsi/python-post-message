import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from app.application.ports import PublicationError
from app.application.posting_service import PostingService
from app.domain.message import Message
from app.domain.publication import PublicationFailed, PublicationSucceeded, PublishedPost

NOW = datetime(2026, 11, 15, 10, 30, tzinfo=UTC)
MESSAGE = Message("Grow your visibility https://example.com")


@dataclass(frozen=True)
class FixedClock:
    def now(self) -> datetime:
        return NOW


@dataclass(frozen=True)
class AccessCheckerStub:
    public_urls: frozenset[str]

    async def is_public(self, url: str) -> bool:
        return url in self.public_urls


@dataclass(frozen=True)
class PublisherStub:
    name: str
    post: PublishedPost | None = None
    error: Exception | None = None
    delay_seconds: float = 0

    async def publish(self, message: Message) -> PublishedPost:
        await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        assert self.post is not None
        return self.post


def build_service(
    *publishers: PublisherStub, public_urls: frozenset[str] = frozenset()
) -> PostingService:
    return PostingService(
        publishers=publishers,
        access_checker=AccessCheckerStub(public_urls),
        clock=FixedClock(),
        publish_timeout_seconds=0.05,
    )


async def test_reports_every_platform_in_registration_order() -> None:
    service = build_service(
        PublisherStub("Alpha", post=PublishedPost("https://alpha.test/1")),
        PublisherStub("Beta", error=PublicationError("Authentication failed")),
    )

    report = await service.post(MESSAGE)

    assert report.results == (
        PublicationSucceeded("Alpha", "https://alpha.test/1", False, NOW),
        PublicationFailed("Beta", "Authentication failed"),
    )
    assert report.has_any_success


async def test_uses_platform_timestamp_converted_to_utc() -> None:
    kyiv = timezone(timedelta(hours=2))
    published_at = datetime(2026, 11, 15, 12, 0, tzinfo=kyiv)
    service = build_service(
        PublisherStub("Alpha", post=PublishedPost("https://alpha.test/1", published_at)),
        public_urls=frozenset({"https://alpha.test/1"}),
    )

    report = await service.post(MESSAGE)

    assert report.results == (
        PublicationSucceeded(
            "Alpha", "https://alpha.test/1", True, datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
        ),
    )


async def test_isolates_timeouts_and_unexpected_errors() -> None:
    service = build_service(
        PublisherStub("Slow", post=PublishedPost("https://slow.test/1"), delay_seconds=1),
        PublisherStub("Broken", error=KeyError("id")),
        PublisherStub("Healthy", post=PublishedPost("https://healthy.test/1")),
    )

    report = await service.post(MESSAGE)

    assert report.results == (
        PublicationFailed("Slow", "Timed out after 0.05 seconds"),
        PublicationFailed("Broken", "Unexpected error: KeyError"),
        PublicationSucceeded("Healthy", "https://healthy.test/1", False, NOW),
    )


async def test_publishes_concurrently() -> None:
    publishers = [
        PublisherStub(f"P{index}", post=PublishedPost(f"https://p{index}.test"), delay_seconds=0.03)
        for index in range(5)
    ]

    async with asyncio.timeout(0.045):
        report = await build_service(*publishers).post(MESSAGE)

    assert len(report.results) == 5


async def test_reports_no_success_when_all_platforms_fail() -> None:
    service = build_service(PublisherStub("Alpha", error=PublicationError("Rejected")))

    report = await service.post(MESSAGE)

    assert not report.has_any_success
