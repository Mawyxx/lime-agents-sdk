from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any, Literal, cast

import httpx
from mcp import ClientSession
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    ServerCapabilities,
    Tool,
)

from lime_agents._client import LimeClient
from lime_agents._domain import extract_and_normalize_domain
from lime_agents._errors import ApiError, AuthenticationError
from lime_agents._mcp._pool import McpSessionPool
from lime_agents._oauth import _McpTokenIssuer
from lime_agents._pow import solve
from lime_agents._types import AgentProfile, ApprovalResult, McpAccessToken

_DEFAULT_BASE_URL = "https://lime.pics/api/v1"
_MCP_RETRY_ON_AUTH = True


class LimeAgent:
    """Async client for LIME agent workers.

    Wraps site-login approve (PoW + ``X-Agent-Token``) and MCP OAuth client calls to
    external resource servers. Pass a required ``target`` (URL or hostname); the SDK
    extracts the domain, issues a JWT via ``POST /oauth/token`` with JSON
    ``{"domain"}``, and caches per domain. Tokens use **lazy refresh** (no background
    task). Use ``get_mcp_access_token(target)`` only when you need the raw JWT string.

    See `LIME platform docs <https://lime.pics/docs#guide-agentSdk>`_ for HTTP details.
    """

    def __init__(
        self,
        *,
        agent_token: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        pow_timeout: float = 10.0,
        mcp_token_refresh_skew: float = 30.0,
        mcp_read_timeout: float = 300.0,
        serialize_mcp_per_url: bool = True,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create an agent client.

        Args:
            agent_token: Opaque agent secret (default from ``LIME_AGENT_TOKEN`` env).
            base_url: API root including ``/api/v1`` (default ``LIME_API_BASE``).
            timeout: HTTP timeout seconds for LIME platform calls.
            max_retries: Retries on transient 408/429/5xx for **LIME platform** HTTP only.
            pow_timeout: Max seconds to solve PoW before ``PowTimeoutError``.
            mcp_token_refresh_skew: Treat MCP JWT as expired this many seconds before
                ``expires_in``; lazy refresh runs on the next MCP call (not in background).
            mcp_read_timeout: MCP streamable HTTP read timeout seconds.
            serialize_mcp_per_url: Serialize MCP calls per resolved MCP URL when True.
            http_client: Injectable ``httpx.AsyncClient`` for tests.

        Raises:
            AuthenticationError: When no agent token is configured.
        """
        resolved_token = (agent_token or os.getenv("LIME_AGENT_TOKEN") or "").strip()
        if not resolved_token:
            raise AuthenticationError(
                "Agent token is required. Pass agent_token= or set LIME_AGENT_TOKEN.",
            )

        resolved_base = (
            base_url
            or os.getenv("LIME_API_BASE")
            or _DEFAULT_BASE_URL
        ).rstrip("/")

        self._pow_timeout = pow_timeout
        self._mcp_read_timeout = mcp_read_timeout
        self._serialize_mcp_per_url = serialize_mcp_per_url
        self._client = LimeClient(
            agent_token=resolved_token,
            base_url=resolved_base,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )
        self._oauth = _McpTokenIssuer(self._client, refresh_skew=mcp_token_refresh_skew)
        self._mcp_pool: McpSessionPool | None = None

    async def __aenter__(self) -> LimeAgent:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close MCP sessions and the underlying HTTP client.

        Called automatically when using ``async with LimeAgent()``.
        Safe to call multiple times.
        """
        if self._mcp_pool is not None:
            await self._mcp_pool.aclose()
            self._mcp_pool = None
        await self._client.aclose()

    async def login(self, request_id: str) -> ApprovalResult:
        """Complete site-login approve for one ``request_id``.

        Fetches PoW challenge, solves it, and posts approve with ``X-Agent-Token``.
        The site backend receives the passport JWT separately via SSE.

        Args:
            request_id: Login request id from the site backend (``login_request_id``).

        Returns:
            ``ApprovalResult`` with status and optional ``approved_agent_id``.

        Raises:
            ApiError: Invalid request id or approve rejected by API.
            PowTimeoutError: PoW not solved within ``pow_timeout``.
        """
        normalized_request_id = request_id.strip()
        if not normalized_request_id:
            raise ApiError(
                "INVALID_REQUEST_ID",
                "request_id must be a non-empty string",
                http_status=400,
            )
        challenge_data = await self._client.get_public(
            f"/auth/requests/{normalized_request_id}"
        )
        pow_challenge = str(challenge_data["pow_challenge"])
        pow_difficulty = int(challenge_data["pow_difficulty"])

        pow_nonce = await asyncio.to_thread(
            solve,
            pow_challenge,
            pow_difficulty,
            max_timeout=self._pow_timeout,
        )

        approve_data = await self._client.post(
            f"/modules/agent-login/requests/{normalized_request_id}/approve",
            {"pow_nonce": pow_nonce},
        )
        return ApprovalResult.from_api(approve_data)

    async def get_profile(self) -> AgentProfile:
        """Return the authenticated agent's Core profile."""
        profile_data = await self._client.get("/core/agents/me/profile")
        return AgentProfile.from_api(profile_data)

    async def get_mcp_access_token(
        self,
        target: str,
        *,
        force_refresh: bool = False,
    ) -> McpAccessToken:
        """Return a cached MCP OAuth JWT for the domain extracted from ``target``.

        Args:
            target: MCP URL or hostname (domain is extracted; port stripped for the key).
            force_refresh: When True, bypass cache and request a new token.

        Returns:
            ``McpAccessToken`` with ``access_token``, ``expires_in``, and ``issued_at``.

        Raises:
            ValueError: When ``target`` is empty or not a valid DNS hostname.

        Note:
            Prefer ``list_tools`` / ``call_tool`` for normal MCP usage. Lazy refresh
            happens automatically on those methods when the cache is near expiry.
            This method is for integrators who need the raw JWT (custom HTTP, debugging).
        """
        domain = extract_and_normalize_domain(target)
        return await self._oauth.get_access_token(domain, force_refresh=force_refresh)

    def _get_mcp_pool(self) -> McpSessionPool:
        if self._mcp_pool is None:
            self._mcp_pool = McpSessionPool(
                self._oauth,
                read_timeout=self._mcp_read_timeout,
                serialize_per_url=self._serialize_mcp_per_url,
            )
        return self._mcp_pool

    @asynccontextmanager
    async def mcp_session(self, target: str) -> AsyncIterator[ClientSession]:
        """Low-level MCP session for custom protocol calls.

        Args:
            target: MCP URL or hostname (resolved to streamable HTTP; OAuth domain extracted).

        Yields:
            Initialized ``ClientSession`` with OAuth already applied.

        Note:
            Prefer ``list_tools`` / ``call_tool`` for normal usage.
        """
        async with self._get_mcp_pool().session(target) as session:
            yield session

    async def list_tools(self, target: str) -> list[Tool]:
        """List tools on an external MCP resource server.

        OAuth JWT is fetched lazily on this call (and refreshed when within
        ``mcp_token_refresh_skew`` of expiry).

        Args:
            target: MCP URL or hostname (e.g. ``https://host/mcp`` or ``host.example``).

        Returns:
            List of ``Tool`` models (not a wrapper with ``.tools`` attribute).
        """
        result = await self._get_mcp_pool().run(
            target,
            lambda session: session.list_tools(),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )
        return list(result.tools)

    async def call_tool(
        self,
        target: str,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> CallToolResult:
        """Invoke a tool on an external MCP resource server.

        Args:
            target: MCP URL or hostname.
            name: Tool name from ``list_tools``.
            arguments: JSON-serializable tool arguments.

        Returns:
            ``CallToolResult`` from the MCP protocol.
        """
        return await self._get_mcp_pool().run(
            target,
            lambda session: session.call_tool(name, arguments or {}),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )

    async def list_resources(self, target: str) -> list[Resource]:
        """List static resources on an external MCP server.

        Args:
            target: MCP URL or hostname.

        Returns:
            List of ``Resource`` models.
        """
        result = await self._get_mcp_pool().run(
            target,
            lambda session: session.list_resources(),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )
        return list(result.resources)

    async def list_resource_templates(self, target: str) -> list[ResourceTemplate]:
        """List resource templates on an external MCP server."""
        result = await self._get_mcp_pool().run(
            target,
            lambda session: session.list_resource_templates(),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )
        return list(result.resourceTemplates)

    async def list_prompts(self, target: str) -> list[Prompt]:
        """List prompt templates on an external MCP server.

        Args:
            target: MCP URL or hostname.

        Returns:
            List of ``Prompt`` models.
        """
        result = await self._get_mcp_pool().run(
            target,
            lambda session: session.list_prompts(),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )
        return list(result.prompts)

    async def read_resource(self, target: str, uri: str) -> ReadResourceResult:
        """Read one resource by URI from an external MCP server.

        Args:
            target: MCP URL or hostname.
            uri: Resource URI from ``list_resources``.

        Returns:
            ``ReadResourceResult`` with resource contents.
        """
        return await self._get_mcp_pool().run(
            target,
            lambda session: session.read_resource(cast(Any, uri)),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )

    async def get_prompt(
        self,
        target: str,
        name: str,
        arguments: dict[str, str] | None = None,
    ) -> GetPromptResult:
        """Fetch a rendered prompt from an external MCP server.

        Args:
            target: MCP URL or hostname.
            name: Prompt name from ``list_prompts``.
            arguments: Template arguments accepted by the prompt.

        Returns:
            ``GetPromptResult`` with message list.
        """
        return await self._get_mcp_pool().run(
            target,
            lambda session: session.get_prompt(name, arguments or {}),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )

    async def set_logging_level(
        self,
        target: str,
        level: Literal[
            "debug",
            "info",
            "notice",
            "warning",
            "error",
            "critical",
            "alert",
            "emergency",
        ],
    ) -> None:
        await self._get_mcp_pool().run(
            target,
            lambda session: session.set_logging_level(level),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )

    async def send_ping(self, target: str) -> None:
        await self._get_mcp_pool().run(
            target,
            lambda session: session.send_ping(),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )

    async def get_server_capabilities(self, target: str) -> ServerCapabilities:
        """Return cached server capabilities from the MCP session initialize handshake."""
        return await self._get_mcp_pool().get_server_capabilities(target)

    async def send_progress_notification(
        self,
        target: str,
        progress_token: str,
        progress: float,
        total: float | None = None,
    ) -> None:
        await self._get_mcp_pool().run(
            target,
            lambda session: session.send_progress_notification(
                progress_token,
                progress,
                total,
            ),
            retry_on_auth=_MCP_RETRY_ON_AUTH,
        )
