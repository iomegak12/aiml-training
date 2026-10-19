"""Structured errors as RFC 9457 Problem Details (application/problem+json).

Every error body has: type, title, status, detail, instance, plus the extensions
`code` (stable machine-readable error code) and `request_id`.
"""

import logging
from http import HTTPStatus
from typing import Any

import openai
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"

logger = logging.getLogger("api")


class ApiError(Exception):
    """An error with a known HTTP status and error code, returned as Problem Details."""

    def __init__(self, status: int, code: str, detail: str, **extensions: Any) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.extensions = extensions


def problem_body(
    status: int,
    code: str,
    detail: str,
    *,
    instance: str | None = None,
    request_id: str | None = None,
    **extensions: Any,
) -> dict[str, Any]:
    return {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
        "request_id": request_id,
        **extensions,
    }


def problem_response(
    status: int,
    code: str,
    detail: str,
    *,
    instance: str | None = None,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
    **extensions: Any,
) -> JSONResponse:
    body = problem_body(status, code, detail, instance=instance, request_id=request_id, **extensions)
    return JSONResponse(jsonable_encoder(body), status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers)


def problem_from_exception(exc: Exception) -> tuple[int, str, str, dict[str, Any]]:
    """Map an exception to (status, code, detail, extensions)."""
    if isinstance(exc, ApiError):
        return exc.status, exc.code, exc.detail, exc.extensions
    if isinstance(exc, openai.AuthenticationError):
        return 502, "UPSTREAM_AUTH_ERROR", "OpenAI rejected the API key. Check OPENAI_API_KEY.", {}
    if isinstance(exc, openai.RateLimitError):
        return 502, "UPSTREAM_RATE_LIMITED", "OpenAI rate limit or quota exceeded. Try again later.", {}
    if isinstance(exc, openai.APIStatusError):
        return 502, "UPSTREAM_ERROR", f"OpenAI API error (HTTP {exc.status_code}).", {}
    if isinstance(exc, openai.APIError):
        return 502, "UPSTREAM_UNAVAILABLE", "Could not reach the OpenAI API.", {}
    return 500, "INTERNAL_ERROR", "An unexpected error occurred. See the server logs for the request_id.", {}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def _api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    status, code, detail, extensions = problem_from_exception(exc)
    if not isinstance(exc, ApiError):  # expected API errors are already in the access log
        logger.error("Request failed: %s", exc, exc_info=exc)
    return problem_response(
        status, code, detail, instance=request.url.path, request_id=_request_id(request), **extensions
    )


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return problem_response(
        exc.status_code,
        HTTPStatus(exc.status_code).name,
        str(exc.detail),
        instance=request.url.path,
        request_id=_request_id(request),
        headers=getattr(exc, "headers", None),
    )


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return problem_response(
        422,
        "VALIDATION_ERROR",
        "The request is invalid. See 'errors' for details.",
        instance=request.url.path,
        request_id=_request_id(request),
        errors=errors,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(openai.APIError, _api_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    # Any other exception is turned into a 500 problem by RequestContextMiddleware.
