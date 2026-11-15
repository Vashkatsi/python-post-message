import httpx
from pydantic import BaseModel, ValidationError

from app.application.ports import PublicationError

_DETAIL_KEYS = ("error_description", "description", "message", "error", "detail")
_MAX_DETAIL_LENGTH = 300


async def send_for_model[ModelT: BaseModel](
    client: httpx.AsyncClient, request: httpx.Request, model: type[ModelT]
) -> ModelT:
    try:
        response = await client.send(request)
    except httpx.TimeoutException as error:
        raise PublicationError("Platform did not respond in time") from error
    except httpx.TransportError as error:
        raise PublicationError(f"Network error: {type(error).__name__}") from error
    if not response.is_success:
        raise PublicationError(describe_failure(response))
    try:
        return model.model_validate_json(response.content)
    except ValidationError as error:
        raise PublicationError("Unexpected response format from platform") from error


def describe_failure(response: httpx.Response) -> str:
    detail = _extract_detail(response)
    match response.status_code:
        case httpx.codes.UNAUTHORIZED | httpx.codes.FORBIDDEN:
            summary = "Authentication failed"
        case httpx.codes.TOO_MANY_REQUESTS:
            summary = "Rate limit exceeded"
        case status if status >= httpx.codes.INTERNAL_SERVER_ERROR:
            summary = "Platform is unavailable"
        case _:
            summary = "Request rejected"
    suffix = f": {detail}" if detail else ""
    return f"{summary} (HTTP {response.status_code}){suffix}"


def _extract_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:_MAX_DETAIL_LENGTH]
    if isinstance(payload, dict):
        for key in _DETAIL_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value[:_MAX_DETAIL_LENGTH]
    return ""
