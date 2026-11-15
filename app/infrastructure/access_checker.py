import httpx


class HttpAccessChecker:
    def __init__(self, client: httpx.AsyncClient, timeout: httpx.Timeout) -> None:
        self._client = client
        self._timeout = timeout

    async def is_public(self, url: str) -> bool:
        try:
            async with self._client.stream(
                "GET", url, follow_redirects=True, timeout=self._timeout
            ) as response:
                return response.is_success
        except httpx.HTTPError:
            return False
