from typing import Annotated

from fastapi import APIRouter, Body, Response, status

from app.api.dependencies import PostingServiceDep
from app.api.schemas import (
    EXAMPLE_MESSAGE,
    PostingRequest,
    PostingResponse,
    ValidationErrorResponse,
)

router = APIRouter(tags=["posting"])


@router.post(
    "/posting",
    summary="Publish a message to every configured platform",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ValidationErrorResponse,
            "description": "The message failed validation",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": PostingResponse,
            "description": "No platform published the message",
        },
    },
)
async def create_posting(
    posting: Annotated[
        PostingRequest,
        Body(
            openapi_examples={
                "valid": {"summary": "Valid message", "value": {"message": EXAMPLE_MESSAGE}},
                "two_links": {
                    "summary": "Rejected: two links",
                    "value": {"message": "Visit https://a.example and https://b.example"},
                },
            }
        ),
    ],
    service: PostingServiceDep,
    response: Response,
) -> PostingResponse:
    report = await service.post(posting.message)
    if not report.has_any_success:
        response.status_code = status.HTTP_502_BAD_GATEWAY
    return PostingResponse.from_report(report)
