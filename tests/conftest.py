import httpx2

httpx2.alias_httpx()

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient() as http_client:
        yield http_client
