from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

from lime_agents._errors import ApiError, AuthenticationError, LimeError, RateLimitError

logger = logging.getLogger("lime")

_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_AUTH_CODES = frozenset(
    {
        "MISSING_AGENT_TOKEN",
        "INVALID_AGENT_TOKEN",
    },
)


class LimeClient:
    """Internal HTTP client with envelope parsing and retries."""

    def __init__(
        self,
        *,
        agent_token: str,
        base_url: str,
        timeout: float,
        max_retries: int,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._agent_token = agent_token
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        # Keep one source of truth for auth headers in this class.
        if "X-Agent-Token" in self._client.headers:
            self._client.headers.pop("X-Agent-Token")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_public(self, path: str) -> dict[str, Any]:
        return await self._request("GET", path, authenticated=False)

    async def get(self, path: str) -> dict[str, Any]:
        return await self._request("GET", path, authenticated=True)

    async def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, authenticated=True, json_body=body)

    async def post_raw(self, path: str, body: dict[str, Any]) -> httpx.Response:
        """POST JSON body and return the raw response (OAuth token — no LIME envelope)."""
        return await self._request_raw("POST", path, authenticated=True, json_body=body)

    async def _request_raw(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers: dict[str, str] = {"Accept": "application/json"}
        if authenticated:
            headers["X-Agent-Token"] = self._agent_token
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        attempt = 0
        while True:
            try:
                response = await self._send(method, url, headers=headers, json_body=json_body)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt >= self._max_retries:
                    raise LimeError(str(exc)) from exc
                await self._backoff(attempt, method, path)
                attempt += 1
                continue

            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                logger.warning(
                    "Retrying %s %s after HTTP %s (attempt %s)",
                    method,
                    path,
                    response.status_code,
                    attempt + 1,
                )
                await self._backoff(attempt, method, path)
                attempt += 1
                continue

            return response

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers: dict[str, str] = {"Accept": "application/json"}
        if authenticated:
            headers["X-Agent-Token"] = self._agent_token
            headers["Content-Type"] = "application/json"

        attempt = 0
        while True:
            try:
                response = await self._send(method, url, headers=headers, json_body=json_body)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt >= self._max_retries:
                    raise LimeError(str(exc)) from exc
                await self._backoff(attempt, method, path)
                attempt += 1
                continue

            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                logger.warning(
                    "Retrying %s %s after HTTP %s (attempt %s)",
                    method,
                    path,
                    response.status_code,
                    attempt + 1,
                )
                await self._backoff(attempt, method, path)
                attempt += 1
                continue

            return self._parse_envelope(response)

    async def _send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, Any] | None,
    ) -> httpx.Response:
        logger.debug("%s %s", method, url)
        if method == "GET":
            return await self._client.get(url, headers=headers)
        return await self._client.post(url, headers=headers, json=json_body)

    async def _backoff(self, attempt: int, method: str, path: str) -> None:
        delay = (2**attempt) * 0.25 + random.uniform(0, 0.1)
        logger.warning("Backing off %.2fs before retry %s %s", delay, method, path)
        await asyncio.sleep(delay)

    def _parse_envelope(self, response: httpx.Response) -> dict[str, Any]:
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

        if payload.get("ok") is True:
            data = payload.get("data")
            if not isinstance(data, dict):
                raise LimeError("Success envelope missing data object", http_status=status)
            return data

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

        if status == 401 or code in _AUTH_CODES:
            raise AuthenticationError(message, code=code, http_status=status, detail=detail_dict)

        raise ApiError(code, message, http_status=status, detail=detail_dict)
