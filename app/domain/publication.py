from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PublishedPost:
    url: str
    published_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PublicationSucceeded:
    platform: str
    posted_url: str
    public_access: bool
    published_at: datetime


@dataclass(frozen=True, slots=True)
class PublicationFailed:
    platform: str
    error: str


type PublicationResult = PublicationSucceeded | PublicationFailed


@dataclass(frozen=True, slots=True)
class PublicationReport:
    results: tuple[PublicationResult, ...]

    @property
    def has_any_success(self) -> bool:
        return any(isinstance(result, PublicationSucceeded) for result in self.results)
