from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas import FieldError, ValidationErrorResponse


async def _handle_validation_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    body = ValidationErrorResponse(detail=[_field_error(issue) for issue in error.errors()])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=jsonable_encoder(body)
    )


def _field_error(issue: Mapping[str, Any]) -> FieldError:
    if issue["type"] == "json_invalid":
        return FieldError(field="body", message=f"Invalid JSON at position {issue['loc'][-1]}")
    return FieldError(field=_field_name(issue["loc"]), message=issue["msg"])


def _field_name(location: tuple[int | str, ...]) -> str:
    path = [str(part) for part in location if part != "body"]
    return ".".join(path) or "body"


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
