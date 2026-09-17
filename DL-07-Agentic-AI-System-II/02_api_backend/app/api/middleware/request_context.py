"""Request id / correlation id, access log, and last-resort error handling.

This is the outermost application middleware, so every response (including CORS
preflight and unexpected 500s) carries X-Request-ID and X-Correlation-ID.
"""

from __future__ import annotations

import json
import time

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.problem import PROBLEM_MEDIA_TYPE, problem_body
from app.core.errors import ErrorCode
from app.core.ids import accept_client_id, correlation_id_var, new_id, request_id_var
from app.core.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"

log = get_logger("app.access")

# Probes are called constantly; logging them only adds noise.
_QUIET_PATHS = frozenset({"/health", "/ready", "/metrics"})


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, *, type_base_url: str) -> None:
        self.app = app
        self.type_base_url = type_base_url

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = accept_client_id(headers.get(REQUEST_ID_HEADER)) or str(new_id())
        correlation_id = accept_client_id(headers.get(CORRELATION_ID_HEADER)) or request_id
        request_id_var.set(request_id)
        correlation_id_var.set(correlation_id)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, correlation_id=correlation_id)

        path: str = scope.get("path", "")
        method: str = scope.get("method", "WS")
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_ids(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                out = MutableHeaders(scope=message)
                out[REQUEST_ID_HEADER] = request_id
                out[CORRELATION_ID_HEADER] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_ids)
        except Exception as exc:
            log.exception("unhandled_exception", error_type=type(exc).__name__)
            if scope["type"] != "http" or response_started:
                raise
            await self._send_internal_error(path, request_id, correlation_id, send)
            status_code = 500
        finally:
            if path not in _QUIET_PATHS:
                log.info(
                    "http_request",
                    method=method,
                    path=path,  # query strings are never logged
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )

    async def _send_internal_error(
        self, path: str, request_id: str, correlation_id: str, send: Send
    ) -> None:
        body = json.dumps(
            problem_body(ErrorCode.INTERNAL_ERROR, instance=path, type_base_url=self.type_base_url)
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", PROBLEM_MEDIA_TYPE.encode()),
                    (b"content-length", str(len(body)).encode()),
                    (REQUEST_ID_HEADER.lower().encode(), request_id.encode()),
                    (CORRELATION_ID_HEADER.lower().encode(), correlation_id.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
