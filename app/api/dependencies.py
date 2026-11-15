from typing import Annotated, cast

from fastapi import Depends, Request

from app.application.posting_service import PostingService


def get_posting_service(request: Request) -> PostingService:
    return cast(PostingService, request.state.posting_service)


PostingServiceDep = Annotated[PostingService, Depends(get_posting_service)]
