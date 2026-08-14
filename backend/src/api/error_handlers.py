"""Global exception handlers that wrap all errors in the `ApiError` envelope.

Every error response produced by the API follows the structure defined
by `src.schemas.common.ApiError`:

    {
        "code": "VALIDATION_ERROR",
        "message": "...",
        "details": [{"field": "...", "message": "...", "code": "..."}],
        "request_id": "..."
    }

This keeps frontend error handling and client SDKs simple.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.schemas.common import ApiError, ErrorDetail

_VALIDATION_ERROR = "VALIDATION_ERROR"
_NOT_FOUND = "NOT_FOUND"
_CONFLICT = "CONFLICT"
_UNAUTHENTICATED = "UNAUTHENTICATED"
_FORBIDDEN = "FORBIDDEN"
_INTERNAL = "INTERNAL_ERROR"
_SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    body = ApiError(
        code=code,
        message=message,
        details=details,
        request_id=request_id,
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=status_code, content=body)


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # Map common HTTP status codes to our standard codes
    status_code_to_code = {
        status.HTTP_400_BAD_REQUEST: _VALIDATION_ERROR,
        status.HTTP_401_UNAUTHORIZED: _UNAUTHENTICATED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
        status.HTTP_409_CONFLICT: _CONFLICT,
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT",
        status.HTTP_503_SERVICE_UNAVAILABLE: _SERVICE_UNAVAILABLE,
    }
    code = status_code_to_code.get(exc.status_code, _INTERNAL)
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"

    headers = getattr(exc, "headers", None)
    response = _error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        request_id=_request_id(request),
    )
    if headers:
        for k, v in headers.items():
            response.headers[k] = v
    return response


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details: list[ErrorDetail] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        # Skip the first element ("body", "query", "path") for a cleaner field path
        field_path = (
            ".".join(str(x) for x in loc[1:]) if len(loc) > 1 else str(loc[0]) if loc else ""
        )
        details.append(
            ErrorDetail(
                field=field_path or "<root>",
                message=str(err.get("msg", "invalid")),
                code=str(err.get("type", "invalid")),
            )
        )
    return _error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        code=_VALIDATION_ERROR,
        message="Request validation failed",
        request_id=_request_id(request),
        details=details,
    )


async def _integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    # Map PostgreSQL constraint-violation errors to 409 Conflict / 400 Bad Request.
    orig = getattr(exc, "orig", None)
    orig_message = str(orig) if orig else str(exc)
    # Heuristic: unique violations map to 409, check constraints to 400
    if "duplicate key" in orig_message.lower() or "unique constraint" in orig_message.lower():
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=_CONFLICT,
            message="Resource already exists or violates a uniqueness constraint",
            request_id=_request_id(request),
        )
    if "violates check constraint" in orig_message.lower():
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=_VALIDATION_ERROR,
            message="Request violates a database check constraint",
            request_id=_request_id(request),
        )
    # Fallback
    return _error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        code=_VALIDATION_ERROR,
        message="Database integrity violation",
        request_id=_request_id(request),
    )


async def _sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=_INTERNAL,
        message="A database error occurred",
        request_id=_request_id(request),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=_INTERNAL,
        message="An unexpected error occurred",
        request_id=_request_id(request),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Install all global exception handlers on the FastAPI app."""
    # Cover both FastAPI and Starlette HTTPException (404s from the router are
    # raised as StarletteHTTPException which does not inherit FastAPI's version).
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, _integrity_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, _sqlalchemy_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_exception_handler)


__all__ = ["register_error_handlers"]
