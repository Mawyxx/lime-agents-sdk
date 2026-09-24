from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import ServerCapabilities

from lime_agents._domain import extract_and_normalize_domain

if TYPE_CHECKING:
    from lime_agents._oauth import _McpTokenIssuer

logger = logging.getLogger("lime.agents.mcp")


def _validate_url_policy(url: str) -> None:
    """Validate an absolute MCP URL host against the reserved-host policy."""
    extract_and_normalize_domain(url)


async def _guard_response_url(response: httpx.Response) -> None:
    """Re-validate the final response URL against the target host policy.

    Redirects are disabled (``follow_redirects=False``); this hook keeps the
    guarantee fail-closed if a future change or the MCP transport ever follows
    one: a response from a reserved/special-use host raises ``ValueError``.
    """
    _validate_url_policy(str(response.url))


class McpTransportHandle:
    """Owns httpx + streamable HTTP + ClientSession for one MCP server URL."""

    def __init__(
        self,
        server_url: str,
        domain: str,
        token_issuer: _McpTokenIssuer,
        *,
        connect_timeout: float = 30.0,
        read_timeout: float = 300.0,
    ) -> None:
        self._server_url = server_url
        self._domain = domain
        self._token_issuer = token_issuer
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._stack = AsyncExitStack()
        self._http_client: httpx.AsyncClient | None = None
        self._session: ClientSession | None = None
        self._token_generation = -1
        self._server_capabilities: ServerCapabilities | None = None

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCP session is not open")
        return self._session

    @property
    def server_capabilities(self) -> ServerCapabilities | None:
        return self._server_capabilities

    async def ensure_open(self) -> ClientSession:
        token = await self._token_issuer.get_access_token(self._domain)
        if (
            self._session is not None
            and self._token_generation == self._token_issuer.generation_for(self._domain)
        ):
            return self._session
        await self.close()
        return await self._open(token.access_token)

    async def _open(self, access_token: str) -> ClientSession:
        _validate_url_policy(self._server_url)
        self._stack = AsyncExitStack()
        self._server_capabilities = None
        timeout = httpx.Timeout(self._connect_timeout, read=self._read_timeout)
        self._http_client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            event_hooks={"response": [_guard_response_url]},
        )
        await self._stack.enter_async_context(self._http_client)
        transport = await self._stack.enter_async_context(
            streamable_http_client(self._server_url, http_client=self._http_client),
        )
        read_stream, write_stream, _get_session_id = transport
        session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        init_result = await session.initialize()
        self._server_capabilities = init_result.capabilities
        self._session = session
        self._token_generation = self._token_issuer.generation_for(self._domain)
        return session

    async def close(self) -> None:
        self._session = None
        self._http_client = None
        self._token_generation = -1
        self._server_capabilities = None
        try:
            await self._stack.aclose()
        except Exception as exc:
            logger.warning("MCP transport close error: %s", exc)
        self._stack = AsyncExitStack()
