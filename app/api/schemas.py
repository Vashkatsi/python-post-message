import datetime as dt
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, PlainValidator, WithJsonSchema
from pydantic_core import PydanticCustomError

from app.domain.message import MAX_MESSAGE_LENGTH, InvalidMessageError, Message
from app.domain.publication import (
    PublicationFailed,
    PublicationReport,
    PublicationResult,
    PublicationSucceeded,
)

EXAMPLE_MESSAGE = (
    "Check out our latest business platform and grow your online visibility. https://example.com"
)


def _parse_message(value: object) -> Message:
    if not isinstance(value, str):
        raise PydanticCustomError("string_type", "Message must be a string")
    try:
        return Message(value)
    except InvalidMessageError as error:
        raise PydanticCustomError("invalid_message", "{reason}", {"reason": str(error)}) from error


type MessageText = Annotated[
    Message,
    PlainValidator(_parse_message),
    PlainSerializer(lambda message: message.text, return_type=str),
    WithJsonSchema(
        {
            "type": "string",
            "maxLength": MAX_MESSAGE_LENGTH,
            "description": "Up to 200 characters with exactly one http(s) CTA link",
            "examples": [EXAMPLE_MESSAGE],
        }
    ),
]


class PostingRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    message: MessageText


class PublicationStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class PlatformResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    platform: str
    status: PublicationStatus
    posted_url: str | None
    public_access: bool
    date: dt.date | None = Field(description="Posting date in UTC")
    time: dt.time | None = Field(description="Posting time in UTC")
    error: str | None

    @classmethod
    def from_domain(cls, result: PublicationResult) -> Self:
        match result:
            case PublicationSucceeded(platform, posted_url, public_access, published_at):
                return cls(
                    platform=platform,
                    status=PublicationStatus.SUCCESS,
                    posted_url=posted_url,
                    public_access=public_access,
                    date=published_at.date(),
                    time=published_at.time().replace(microsecond=0),
                    error=None,
                )
            case PublicationFailed(platform, error):
                return cls(
                    platform=platform,
                    status=PublicationStatus.FAILED,
                    posted_url=None,
                    public_access=False,
                    date=None,
                    time=None,
                    error=error,
                )


class PostingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    success: bool = Field(description="True when at least one platform published the message")
    results: list[PlatformResult]

    @classmethod
    def from_report(cls, report: PublicationReport) -> Self:
        return cls(
            success=report.has_any_success,
            results=[PlatformResult.from_domain(result) for result in report.results],
        )


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    detail: list[FieldError]
