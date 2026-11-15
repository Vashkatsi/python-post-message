from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import httpx2
from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.routes import router
from app.application.posting_service import PostingService
from app.config import Settings, get_settings
from app.infrastructure.access_checker import HttpAccessChecker
from app.infrastructure.clock import SystemClock
from app.infrastructure.platforms.registry import build_publishers


class AppState(TypedDict):
    posting_service: PostingService


def build_posting_service(settings: Settings, client: httpx2.AsyncClient) -> PostingService:
    clock = SystemClock()
    return PostingService(
        publishers=build_publishers(settings, client, clock),
        access_checker=HttpAccessChecker(
            client, httpx2.Timeout(settings.access_check_timeout_seconds)
        ),
        clock=clock,
        publish_timeout_seconds=settings.publish_timeout_seconds,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[AppState]:
    settings = get_settings()
    async with httpx2.AsyncClient(
        timeout=httpx2.Timeout(settings.http_timeout_seconds),
        transport=httpx2.AsyncHTTPTransport(retries=1),
        headers={"User-Agent": "automated-posting/0.1"},
    ) as client:
        yield {"posting_service": build_posting_service(settings, client)}


def create_app() -> FastAPI:
    application = FastAPI(
        title="Automated Multi-Platform Posting",
        version="0.1.0",
        summary="Publishes one short message with a CTA link to several platforms at once",
        lifespan=lifespan,
    )
    register_error_handlers(application)
    application.include_router(router)
    return application


app = create_app()
