from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar
from urllib.parse import urlparse

from lime_agents._errors import McpAuthenticationError
from lime_agents._mcp._deps import require_mcp
from lime_agents._mcp._transport import McpTransportHandle

if TYPE_CHECKING:
    from mcp import ClientSession

    from lime_agents._oauth import _McpTokenIssuer

T = TypeVar("T")

_MCP_IMPORT_MESSAGE = "MCP support requires: pip install lime-agents-sdk[mcp]"


class _ServerEntry:
    def __init__(
        self,
        url: str,
        token_issuer: _McpTokenIssuer,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> None:
        self.url = url
        self.lock = asyncio.Lock()
        self.transport = McpTransportHandle(
            url,
            token_issuer,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )


class McpSessionPool:
    """Per-server_url MCP session pool with shared OAuth token issuer."""

    def __init__(
        self,
        token_issuer: _McpTokenIssuer,
        *,
        connect_timeout: float = 30.0,
        read_timeout: float = 300.0,
    ) -> None:
        require_mcp()
        self._token_issuer = token_issuer
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._entries: dict[str, _ServerEntry] = {}
        self._pool_lock = asyncio.Lock()
        self._closed = False

    async def run(
        self,
        server_url: str,
        operation: Callable[[ClientSession], Awaitable[T]],
        *,
        retry_on_auth: bool = False,
    ) -> T:
        if self._closed:
            raise RuntimeError("MCP session pool is closed")

        normalized = self._normalize_url(server_url)
        entry = await self._get_entry(normalized)

        async with entry.lock:
            try:
                session = await entry.transport.ensure_open()
                return await operation(session)
            except Exception as exc:
                if not retry_on_auth or not self._is_auth_failure(exc):
                    raise
                await self._refresh_after_auth_failure(entry)
                session = await entry.transport.ensure_open()
                try:
                    return await operation(session)
                except Exception as retry_exc:
                    if self._is_auth_failure(retry_exc):
                        raise McpAuthenticationError(
                            "MCP access token rejected by resource server",
                            code="MCP_AUTH_FAILED",
                        ) from retry_exc
                    raise

    async def refresh_all_tokens(self) -> None:
        await self._token_issuer.invalidate_and_refresh()
        async with self._pool_lock:
            entries = list(self._entries.values())
        for entry in entries:
            async with entry.lock:
                await entry.transport.close()

    async def aclose(self) -> None:
        self._closed = True
        async with self._pool_lock:
            entries = list(self._entries.values())
            self._entries.clear()
        for entry in entries:
            async with entry.lock:
                await entry.transport.close()

    async def _refresh_after_auth_failure(self, entry: _ServerEntry) -> None:
        await self._token_issuer.invalidate_and_refresh()
        async with self._pool_lock:
            entries = list(self._entries.values())
        for pool_entry in entries:
            if pool_entry is entry:
                continue
            async with pool_entry.lock:
                await pool_entry.transport.close()
        await entry.transport.close()

    async def _get_entry(self, normalized_url: str) -> _ServerEntry:
        async with self._pool_lock:
            entry = self._entries.get(normalized_url)
            if entry is None:
                entry = _ServerEntry(
                    normalized_url,
                    self._token_issuer,
                    connect_timeout=self._connect_timeout,
                    read_timeout=self._read_timeout,
                )
                self._entries[normalized_url] = entry
            return entry

    @staticmethod
    def _normalize_url(server_url: str) -> str:
        normalized = server_url.strip().rstrip("/")
        if not normalized:
            raise ValueError("server_url must be a non-empty string")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("server_url must be an http(s) URL")
        return normalized

    @staticmethod
    def _is_auth_failure(exc: BaseException) -> bool:
        status = getattr(exc, "status", None)
        if status == 401:
            return True
        message = str(exc).lower()
        return "401" in message or "unauthorized" in message or "invalid_token" in message
