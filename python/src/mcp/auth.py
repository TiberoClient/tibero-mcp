"""Static API-key authentication for the Streamable HTTP endpoint.

Remote MCP clients differ in what they can send: some let the user configure
request headers, others only take a URL. The same key is therefore accepted in
any of three places:

- ``Authorization: Bearer <key>``
- ``X-API-Key: <key>``
- a leading path segment: ``/<key>/mcp`` (stripped before routing)

The path form puts the key in URLs, so access logs must never print raw paths;
``RequestLogMiddleware`` logs a redacted path instead.
"""

from __future__ import annotations

import hmac
import json
import time
from typing import Any, Awaitable, Callable

from loguru import logger

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

PUBLIC_PATHS = frozenset({"/healthz"})


def _matches(candidate: str, keys: tuple[str, ...]) -> bool:
    # Compare against every key so timing does not reveal which one matched.
    found = False
    for key in keys:
        found |= hmac.compare_digest(candidate.encode(), key.encode())
    return found


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


class ApiKeyMiddleware:
    def __init__(self, app: ASGIApp, keys: list[str]):
        if not keys:
            raise ValueError("ApiKeyMiddleware requires at least one key")
        self.app = app
        self.keys = tuple(keys)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        path_key, rest = self._split_path_key(scope["path"])
        if path_key is not None:
            scope = dict(scope, path=rest, raw_path=rest.encode())
            await self.app(scope, receive, send)
            return

        if self._header_key_ok(scope):
            await self.app(scope, receive, send)
            return

        await self._reject(send)

    def _split_path_key(self, path: str) -> tuple[str | None, str]:
        segment, sep, rest = path.lstrip("/").partition("/")
        if sep and _matches(segment, self.keys):
            return segment, "/" + rest
        return None, path

    def _header_key_ok(self, scope: Scope) -> bool:
        authorization = _header(scope, b"authorization")
        if authorization and authorization[:7].lower() == "bearer ":
            if _matches(authorization[7:].strip(), self.keys):
                return True
        api_key = _header(scope, b"x-api-key")
        return bool(api_key) and _matches(api_key.strip(), self.keys)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = json.dumps({"error": "unauthorized", "error_description": "Missing or invalid API key"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})


class RequestLogMiddleware:
    """Access log that never prints a key carried in the path.

    Sits outside ApiKeyMiddleware, so the path it sees may still contain the key.
    """

    def __init__(self, app: ASGIApp, keys: list[str]):
        self.app = app
        self.keys = tuple(keys)

    def _redact(self, path: str) -> str:
        segment, sep, rest = path.lstrip("/").partition("/")
        if sep and _matches(segment, self.keys):
            return "/<key>/" + rest
        return path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.monotonic()
        status = 500

        async def capture(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            client = _header(scope, b"x-real-ip") or (scope.get("client") or ("-",))[0]
            logger.info(
                f'{client} "{scope["method"]} {self._redact(scope["path"])}" {status} '
                f"{(time.monotonic() - started) * 1000:.0f}ms"
            )
