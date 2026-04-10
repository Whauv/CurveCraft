"""API exception and middleware tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


def _load_exception_components() -> tuple:
    """Load exception components, skipping cleanly if FastAPI is unavailable."""
    try:
        from fastapi import HTTPException

        from fixed_income.api.exceptions import http_exception_handler, unhandled_exception_handler
    except Exception as exc:  # pragma: no cover - local broken env fallback
        pytest.skip(f"FastAPI installation is incomplete in this environment: {exc}")

    return HTTPException, http_exception_handler, unhandled_exception_handler


class DummyRequest:
    """Minimal request stub for exception handler tests."""

    def __init__(self) -> None:
        self.method = "GET"
        self.url = SimpleNamespace(path="/test")
        self.state = SimpleNamespace(request_id="req-123")


def test_http_exception_handler_returns_request_id() -> None:
    """Structured HTTP errors should include the request id."""
    HTTPException, http_exception_handler, _ = _load_exception_components()
    response = asyncio.run(http_exception_handler(DummyRequest(), HTTPException(status_code=400, detail="bad input")))
    assert response.status_code == 400
    assert b'"request_id":"req-123"' in response.body


def test_unhandled_exception_handler_returns_internal_error() -> None:
    """Unhandled errors should be masked behind a 500 payload."""
    _, _, unhandled_exception_handler = _load_exception_components()
    response = asyncio.run(unhandled_exception_handler(DummyRequest(), RuntimeError("boom")))
    assert response.status_code == 500
    assert b"Internal server error." in response.body
