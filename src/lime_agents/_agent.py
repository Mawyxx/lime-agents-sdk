from __future__ import annotations

import asyncio
import os
from types import TracebackType
from typing import Any, Literal, cast

import httpx

from lime_agents._client import LimeClient
from lime_agents._errors import ApiError, AuthenticationError
from lime_agents._mcp._pool import McpSessionPool
from lime_agents._oauth import _McpTokenIssuer
from lime_agents._pow import solve
from lime_agents._types import AgentProfile, ApprovalResult, McpAccessToken

_DEFAULT_BASE_URL = "https://lime.pics/api/v1"


class LimeAgent:
    """Async client for LIME agent workers."""

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
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
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
        if self._mcp_pool is not None:
            await self._mcp_pool.aclose()
            self._mcp_pool = None
        await self._client.aclose()

    async def login(self, request_id: str) -> ApprovalResult:
        """Complete the full login approval flow for one request_id."""
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

    async def get_mcp_access_token(self, *, force_refresh: bool = False) -> McpAccessToken:
        """Issue a short-lived MCP JWT via POST /modules/oauth/token (X-Agent-Token only)."""
        return await self._oauth.get_access_token(force_refresh=force_refresh)

    def _get_mcp_pool(self) -> McpSessionPool:
        if self._mcp_pool is None:
            self._mcp_pool = McpSessionPool(
                self._oauth,
                read_timeout=self._mcp_read_timeout,
            )
        return self._mcp_pool

    async def list_tools(self, server_url: str) -> list[Any]:
        result = await self._get_mcp_pool().run(
            server_url,
            lambda session: session.list_tools(),
        )
        return list(result.tools)

    async def call_tool(
        self,
        server_url: str,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        return await self._get_mcp_pool().run(
            server_url,
            lambda session: session.call_tool(name, arguments or {}),
            retry_on_auth=True,
        )

    async def list_resources(self, server_url: str) -> list[Any]:
        result = await self._get_mcp_pool().run(
            server_url,
            lambda session: session.list_resources(),
        )
        return list(result.resources)

    async def list_resource_templates(self, server_url: str) -> list[Any]:
        result = await self._get_mcp_pool().run(
            server_url,
            lambda session: session.list_resource_templates(),
        )
        return list(result.resourceTemplates)

    async def list_prompts(self, server_url: str) -> list[Any]:
        result = await self._get_mcp_pool().run(
            server_url,
            lambda session: session.list_prompts(),
        )
        return list(result.prompts)

    async def read_resource(self, server_url: str, uri: str) -> Any:
        return await self._get_mcp_pool().run(
            server_url,
            lambda session: session.read_resource(cast(Any, uri)),
        )

    async def get_prompt(
        self,
        server_url: str,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        return await self._get_mcp_pool().run(
            server_url,
            lambda session: session.get_prompt(name, arguments or {}),
        )

    async def set_logging_level(
        self,
        server_url: str,
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
            server_url,
            lambda session: session.set_logging_level(level),
        )

    async def send_ping(self, server_url: str) -> None:
        await self._get_mcp_pool().run(
            server_url,
            lambda session: session.send_ping(),
        )

    async def get_server_capabilities(self, server_url: str) -> dict[str, Any]:
        async def _fetch(session: Any) -> dict[str, Any]:
            capabilities = await session.get_server_capabilities()
            if capabilities is None:
                return {}
            if hasattr(capabilities, "model_dump"):
                dumped = capabilities.model_dump(exclude_none=True)
                return dumped if isinstance(dumped, dict) else {}
            return {}

        return await self._get_mcp_pool().run(server_url, _fetch)

    async def send_progress_notification(
        self,
        server_url: str,
        progress_token: str,
        progress: float,
        total: float | None = None,
    ) -> None:
        await self._get_mcp_pool().run(
            server_url,
            lambda session: session.send_progress_notification(
                progress_token,
                progress,
                total,
            ),
        )
