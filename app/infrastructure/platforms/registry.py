import httpx

from app.application.ports import Publisher
from app.config import Settings


def build_publishers(settings: Settings, client: httpx.AsyncClient) -> list[Publisher]:
    return []
