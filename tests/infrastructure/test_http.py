import re

import httpx
import pytest
import respx
from pydantic import BaseModel

from app.application.ports import PublicationError
from app.infrastructure.access_checker import HttpAccessChecker
from app.infrastructure.http import send_for_model

URL = "https://platform.test/api"


class Created(BaseModel):
    id: int


@respx.mock
async def test_parses_successful_response(client: httpx.AsyncClient) -> None:
    respx.post(URL).respond(201, json={"id": 7, "extra": "ignored"})

    created = await send_for_model(client, client.build_request("POST", URL), Created)

    assert created == Created(id=7)


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, {"error": "invalid token"}, "Authentication failed (HTTP 401): invalid token"),
        (403, {"message": "forbidden"}, "Authentication failed (HTTP 403): forbidden"),
        (429, {}, "Rate limit exceeded (HTTP 429)"),
        (503, {"detail": "maintenance"}, "Platform is unavailable (HTTP 503): maintenance"),
        (
            400,
            {"description": "Bad Request: chat not found"},
            "Request rejected (HTTP 400): Bad Request: chat not found",
        ),
    ],
)
@respx.mock
async def test_describes_http_failures(
    client: httpx.AsyncClient, status: int, body: dict[str, str], expected: str
) -> None:
    respx.post(URL).respond(status, json=body)

    with pytest.raises(PublicationError, match=f"^{re.escape(expected)}$"):
        await send_for_model(client, client.build_request("POST", URL), Created)


@respx.mock
async def test_reports_plain_text_failure(client: httpx.AsyncClient) -> None:
    respx.post(URL).respond(400, text="  bad input  ")

    with pytest.raises(PublicationError, match=r"bad input$"):
        await send_for_model(client, client.build_request("POST", URL), Created)


@respx.mock
async def test_reports_network_errors(client: httpx.AsyncClient) -> None:
    respx.post(URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(PublicationError, match="Network error: ConnectError"):
        await send_for_model(client, client.build_request("POST", URL), Created)


@respx.mock
async def test_reports_timeouts(client: httpx.AsyncClient) -> None:
    respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(PublicationError, match="did not respond in time"):
        await send_for_model(client, client.build_request("POST", URL), Created)


@respx.mock
async def test_reports_unexpected_payload(client: httpx.AsyncClient) -> None:
    respx.post(URL).respond(200, json={"unexpected": True})

    with pytest.raises(PublicationError, match="Unexpected response format"):
        await send_for_model(client, client.build_request("POST", URL), Created)


@pytest.mark.parametrize(("status", "expected"), [(200, True), (404, False), (403, False)])
@respx.mock
async def test_access_checker_follows_redirects_and_checks_status(
    client: httpx.AsyncClient, status: int, expected: bool
) -> None:
    respx.get("https://site.test/short").respond(
        302, headers={"Location": "https://site.test/post"}
    )
    respx.get("https://site.test/post").respond(status)
    checker = HttpAccessChecker(client, httpx.Timeout(1))

    assert await checker.is_public("https://site.test/short") is expected


@respx.mock
async def test_access_checker_treats_network_errors_as_not_public(
    client: httpx.AsyncClient,
) -> None:
    respx.get("https://site.test/post").mock(side_effect=httpx.ConnectError("refused"))

    assert (
        await HttpAccessChecker(client, httpx.Timeout(1)).is_public("https://site.test/post")
        is False
    )
