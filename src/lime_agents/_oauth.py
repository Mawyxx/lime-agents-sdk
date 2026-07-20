from __future__ import annotations

import asyncio
import time
from typing import Any, NoReturn

import httpx

from lime_agents._client import LimeClient
from lime_agents._errors import (
    ApiError,
    AuthenticationError,
    LimeError,
    OAuthCapabilityError,
    RateLimitError,
)
from lime_agents._types import McpAccessToken

_OAUTH_TOKEN_PATH = "/modules/oauth/token"
_RFC6749_KEYS = frozenset({"access_token", "token_type", "expires_in"})


class _McpTokenIssuer:
    """Issues and caches MCP access tokens per normalized domain (ADR 0081 v11).

    Uses **lazy refresh**: no background timer. On each ``get_access_token(domain)``
    call the per-domain cache is returned while valid; when
    ``expires_in - refresh_skew`` is reached the next caller fetches a new JWT
    under that domain's lock (single-flight).
    """

    def __init__(self, client: LimeClient, *, refresh_skew: float = 30.0) -> None:
        self._client = client
        self._refresh_skew = refresh_skew
        self._cached: dict[str, McpAccessToken] = {}
        self._generations: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    def generation_for(self, domain: str) -> int:
        return self._generations.get(domain, 0)

    def invalidate(self, domain: str) -> None:
        """Drop the cached token for ``domain`` only."""
        self._cached.pop(domain, None)

    async def get_access_token(
        self,
        domain: str,
        *,
        force_refresh: bool = False,
    ) -> McpAccessToken:
        if not force_refresh:
            cached = self._cached.get(domain)
            if cached is not None and not self._is_expired(cached):
                return cached

        lock = await self._lock_for(domain)
        async with lock:
            if not force_refresh:
                cached = self._cached.get(domain)
                if cached is not None and not self._is_expired(cached):
                    return cached
            token = await self._issue_token(domain)
            self._cached[domain] = token
            self._generations[domain] = self._generations.get(domain, 0) + 1
            return token

    async def invalidate_and_refresh(self, domain: str) -> McpAccessToken:
        self.invalidate(domain)
        return await self.get_access_token(domain, force_refresh=True)

    async def invalidate_all(self) -> None:
        """Drop every cached domain token (e.g. agent shutdown / full refresh)."""
        self._cached.clear()

    def _is_expired(self, token: McpAccessToken) -> bool:
        elapsed = time.monotonic() - token.issued_at
        return elapsed >= (token.expires_in - self._refresh_skew)

    async def _lock_for(self, domain: str) -> asyncio.Lock:
        lock = self._locks.get(domain)
        if lock is not None:
            return lock
        async with self._meta_lock:
            lock = self._locks.get(domain)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[domain] = lock
            return lock

    async def _issue_token(self, domain: str) -> McpAccessToken:
        response = await self._client.post_raw(
            _OAUTH_TOKEN_PATH,
            {"domain": domain},
        )
        if response.status_code == 200:
            return self._parse_success(response)
        self._raise_token_error(response)

    def _parse_success(self, response: httpx.Response) -> McpAccessToken:
        status = response.status_code
        try:
            body = response.json()
        except ValueError as exc:
            raise LimeError(
                f"Invalid JSON response (HTTP {status})",
                http_status=status,
            ) from exc

        if not isinstance(body, dict):
            raise LimeError(f"Unexpected token response shape (HTTP {status})", http_status=status)

        if set(body.keys()) != _RFC6749_KEYS:
            raise ApiError(
                "INVALID_TOKEN_RESPONSE",
                "Token response must contain access_token, token_type, expires_in only",
                http_status=status,
            )

        token_type = str(body["token_type"])
        if token_type != "Bearer":
            raise ApiError(
                "INVALID_TOKEN_RESPONSE",
                "token_type must be Bearer",
                http_status=status,
            )

        cache_control = response.headers.get("cache-control", "").lower()
        if cache_control != "no-store":
            raise ApiError(
                "INVALID_TOKEN_RESPONSE",
                "expected Cache-Control: no-store",
                http_status=status,
            )

        access_token = str(body["access_token"])
        if access_token.count(".") != 2:
            raise ApiError(
                "INVALID_TOKEN_RESPONSE",
                "access_token must be a JWT",
                http_status=status,
            )

        expires_in = int(body["expires_in"])
        return McpAccessToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=expires_in,
            issued_at=time.monotonic(),
        )

    def _raise_token_error(self, response: httpx.Response) -> NoReturn:
        status = response.status_code
        try:
            payload = response.json()
        except ValueError as exc:
            raise LimeError(
                f"Invalid JSON response (HTTP {status})",
                http_status=status,
            ) from exc

        if not isinstance(payload, dict):
            raise LimeError(f"Unexpected response shape (HTTP {status})", http_status=status)

        if isinstance(payload.get("error"), str):
            self._raise_rfc6749_error(status, payload)
        self._raise_envelope_error(status, payload)

    def _raise_rfc6749_error(self, status: int, payload: dict[str, Any]) -> NoReturn:
        error = str(payload.get("error", "unknown_error"))
        description = str(payload.get("error_description", error))

        if status == 401 or error == "invalid_client":
            raise AuthenticationError(
                description,
                code=error,
                http_status=status,
            )

        if status == 400 or error == "invalid_request":
            raise ApiError(error, description, http_status=status)

        if status == 429:
            raise RateLimitError(description, code=error, http_status=status)

        raise ApiError(error, description, http_status=status)

    def _raise_envelope_error(self, status: int, payload: dict[str, Any]) -> NoReturn:
        if payload.get("ok") is True:
            raise LimeError(
                f"Unexpected success on token endpoint (HTTP {status})",
                http_status=status,
            )

        error = payload.get("error")
        if not isinstance(error, dict):
            raise LimeError(
                f"Error envelope missing error object (HTTP {status})",
                http_status=status,
            )

        code = str(error.get("code", "UNKNOWN_ERROR"))
        message = str(error.get("message", "Unknown error"))
        detail = error.get("detail")
        detail_dict = detail if isinstance(detail, dict) else None

        if status == 429 or code == "RATE_LIMIT_EXCEEDED":
            raise RateLimitError(message, code=code, http_status=status, detail=detail_dict)

        if code == "OAUTH_CAPABILITY_DENIED":
            raise OAuthCapabilityError(
                code,
                message,
                http_status=status,
                detail=detail_dict,
            )

        if status == 401:
            raise AuthenticationError(message, code=code, http_status=status, detail=detail_dict)

        raise ApiError(code, message, http_status=status, detail=detail_dict)
