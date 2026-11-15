import httpx2


class HttpAccessChecker:
    def __init__(self, client: httpx2.AsyncClient, timeout: httpx2.Timeout) -> None:
        self._client = client
        self._timeout = timeout

    async def is_public(self, url: str) -> bool:
        try:
            async with self._client.stream(
                "GET", url, follow_redirects=True, timeout=self._timeout
            ) as response:
                return response.is_success
        except httpx2.HTTPError, httpx2.InvalidURL:
            return False
