"""API exception handlers and observability helpers."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def request_logging_middleware(request: Request, call_next):
    """Log each request with a generated request id and latency."""
    request_id = uuid4().hex[:12]
    start = time.perf_counter()
    request.state.request_id = request_id
    logger.info("request_started request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_finished request_id=%s method=%s path=%s status_code=%s latency_ms=%.3f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return a structured HTTP exception payload."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(
        "http_exception request_id=%s method=%s path=%s status_code=%s detail=%s",
        request_id,
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": str(exc.detail),
            "request_id": request_id,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a structured internal-error payload."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "unhandled_exception request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error.",
            "request_id": request_id,
        },
    )


def configure_exception_handlers(app: FastAPI) -> None:
    """Attach middleware and handlers to the FastAPI app."""
    app.middleware("http")(request_logging_middleware)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
