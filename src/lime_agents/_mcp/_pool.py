from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, TypeVar
from urllib.parse import urlparse

from anyio import BrokenResourceError
from mcp.types import ServerCapabilities

from lime_agents._errors import McpAuthenticationError
from lime_agents._mcp._transport import McpTransportHandle

if TYPE_CHECKING:
    from mcp import ClientSession

    from lime_agents._oauth import _McpTokenIssuer

T = TypeVar("T")

logger = logging.getLogger("lime.agents.mcp")


class _NullAsyncContext(AbstractAsyncContextManager[None]):
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


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
        self.connect_lock = asyncio.Lock()
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
        serialize_per_url: bool = True,
    ) -> None:
        self._token_issuer = token_issuer
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._serialize_per_url = serialize_per_url
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
        lock_ctx = entry.lock if self._serialize_per_url else _NullAsyncContext()

        async with lock_ctx:
            return await self._execute_operation(entry, operation, retry_on_auth=retry_on_auth)

    async def get_server_capabilities(self, server_url: str) -> ServerCapabilities:
        if self._closed:
            raise RuntimeError("MCP session pool is closed")

        normalized = self._normalize_url(server_url)
        entry = await self._get_entry(normalized)
        lock_ctx = entry.lock if self._serialize_per_url else _NullAsyncContext()

        async with lock_ctx:
            async with entry.connect_lock:
                await entry.transport.ensure_open()
            caps = entry.transport.server_capabilities
            return caps if caps is not None else ServerCapabilities()

    @asynccontextmanager
    async def session(self, server_url: str) -> AsyncIterator[ClientSession]:
        if self._closed:
            raise RuntimeError("MCP session pool is closed")

        normalized = self._normalize_url(server_url)
        entry = await self._get_entry(normalized)
        async with entry.lock:
            async with entry.connect_lock:
                mcp_session = await entry.transport.ensure_open()
            try:
                yield mcp_session
            finally:
                pass

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
        await asyncio.sleep(0.15)

        for entry in entries:
            try:
                async with entry.lock:
                    await entry.transport.close()
            except BaseException as exc:
                if McpSessionPool._is_shutdown_noise(exc):
                    continue
                logger.warning("MCP pool close error: %s", exc)

    async def _execute_operation(
        self,
        entry: _ServerEntry,
        operation: Callable[[ClientSession], Awaitable[T]],
        *,
        retry_on_auth: bool,
    ) -> T:
        last_exc: BaseException | None = None
        for attempt in range(2):
            try:
                async with entry.connect_lock:
                    session = await entry.transport.ensure_open()
                return await operation(session)
            except Exception as exc:
                last_exc = exc
                if attempt == 0 and self._is_broken_session(exc):
                    async with entry.connect_lock:
                        await entry.transport.close()
                    continue
                if not retry_on_auth or not self._is_auth_failure(exc):
                    raise
                await self._refresh_after_auth_failure(entry)
                async with entry.connect_lock:
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
        if last_exc is None:  # pragma: no cover
            raise RuntimeError("MCP operation failed without exception")
        raise last_exc  # pragma: no cover

    async def _refresh_after_auth_failure(self, entry: _ServerEntry) -> None:
        await self._token_issuer.invalidate_and_refresh()
        async with self._pool_lock:
            entries = list(self._entries.values())
        for pool_entry in entries:
            if pool_entry is entry:
                continue
            async with pool_entry.lock:
                await pool_entry.transport.close()
        async with entry.connect_lock:
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
    def _exception_group_members(exc: BaseException) -> tuple[BaseException, ...] | None:
        members = getattr(exc, "exceptions", None)
        if members is not None and type(exc).__name__ == "ExceptionGroup":
            return tuple(members)
        return None

    @staticmethod
    def _is_broken_session(exc: BaseException) -> bool:
        if isinstance(exc, BrokenResourceError | asyncio.CancelledError):
            return True
        group = McpSessionPool._exception_group_members(exc)
        if group is not None:
            return any(McpSessionPool._is_broken_session(sub) for sub in group)
        message = str(exc).lower()
        return "brokenresource" in message or "cancel scope" in message

    @staticmethod
    def _is_shutdown_noise(exc: BaseException) -> bool:
        if isinstance(exc, asyncio.CancelledError | BrokenResourceError):
            return True
        group = McpSessionPool._exception_group_members(exc)
        if group is not None:
            return all(McpSessionPool._is_shutdown_noise(sub) for sub in group)
        message = str(exc).lower()
        return (
            "cancel scope" in message
            or "cancelled via cancel scope" in message
            or "session termination failed" in message
            or "generator exit" in message
        )

    @staticmethod
    def _is_auth_failure(exc: BaseException) -> bool:
        status = getattr(exc, "status", None)
        if status == 401:
            return True
        message = str(exc).lower()
        return "401" in message or "unauthorized" in message or "invalid_token" in message
