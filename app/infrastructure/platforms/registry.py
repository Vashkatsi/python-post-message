import httpx2

from app.application.ports import Publisher
from app.config import Settings


def build_publishers(settings: Settings, client: httpx2.AsyncClient) -> list[Publisher]:
    return []
