from __future__ import annotations

import asyncio
import os
from types import TracebackType

import httpx

from lime_agents._client import LimeClient
from lime_agents._errors import AuthenticationError
from lime_agents._pow import solve
from lime_agents._types import AgentProfile, ApprovalResult

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
        self._client = LimeClient(
            agent_token=resolved_token,
            base_url=resolved_base,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )

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
        await self._client.aclose()

    async def approve(self, request_id: str) -> ApprovalResult:
        """Fetch PoW challenge, solve it, and approve the login request."""
        challenge_data = await self._client.get_public(f"/auth/requests/{request_id}")
        pow_challenge = str(challenge_data["pow_challenge"])
        pow_difficulty = int(challenge_data["pow_difficulty"])

        pow_nonce = await asyncio.to_thread(
            solve,
            pow_challenge,
            pow_difficulty,
            max_timeout=self._pow_timeout,
        )

        approve_data = await self._client.post(
            f"/modules/agent-login/requests/{request_id}/approve",
            {"pow_nonce": pow_nonce},
        )
        return ApprovalResult.from_api(approve_data)

    async def get_profile(self) -> AgentProfile:
        """Return the authenticated agent's Core profile."""
        profile_data = await self._client.get("/core/agents/me/profile")
        return AgentProfile.from_api(profile_data)
