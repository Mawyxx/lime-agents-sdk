from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx
import pytest

from lime_agents import AgentProfile, LimeAgent
from lime_agents._errors import ApiError, AuthenticationError


def _solve_for_test(challenge: str, difficulty: int) -> str:
    threshold = 2 ** (256 - difficulty)
    nonce = 0
    while nonce < 1_000_000:
        candidate = str(nonce)
        digest = hashlib.sha256(f"{challenge}{candidate}".encode()).hexdigest()
        if int(digest, 16) < threshold:
            return candidate
        nonce += 1
    raise RuntimeError("test pow failed")


def _envelope_ok(data: dict[str, Any]) -> bytes:
    return json.dumps({"ok": True, "data": data}).encode()


@pytest.mark.asyncio
async def test_login_full_flow() -> None:
    challenge = "sdk-test-challenge"
    difficulty = 8
    expected_nonce = _solve_for_test(challenge, difficulty)
    seen: list[tuple[str, str, dict[str, Any] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, str(request.url), body))
        if request.method == "GET":
            return httpx.Response(
                200,
                content=_envelope_ok(
                    {
                        "request_id": "lr_test",
                        "status": "PENDING",
                        "pow_challenge": challenge,
                        "pow_difficulty": difficulty,
                        "expires_at": "2026-06-10T12:00:00+00:00",
                    },
                ),
            )
        return httpx.Response(
            200,
            content=_envelope_ok(
                {
                    "request_id": "lr_test",
                    "site_id": "site_1",
                    "status": "DELIVERED",
                    "expires_at": "2026-06-10T12:00:00+00:00",
                    "approved_agent_id": "agent_1",
                },
            ),
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    agent = LimeAgent(
        agent_token="at_secret",
        base_url="http://mock/api/v1",
        http_client=http_client,
        pow_timeout=5.0,
    )

    result = await agent.login("lr_test")
    await agent.aclose()

    assert result.request_id == "lr_test"
    assert result.site_id == "site_1"
    assert result.status == "DELIVERED"
    assert result.approved_agent_id == "agent_1"

    assert seen[0][0] == "GET"
    assert seen[0][1].endswith("/auth/requests/lr_test")
    assert seen[1][0] == "POST"
    assert seen[1][1].endswith("/modules/agent-login/requests/lr_test/approve")
    assert seen[1][2] == {"pow_nonce": expected_nonce}


@pytest.mark.asyncio
async def test_get_profile_parses_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Agent-Token"] == "at_secret"
        return httpx.Response(
            200,
            content=_envelope_ok(
                {
                    "agent_id": "agent_1",
                    "owner_id": "owner_1",
                    "display_name": "Bot",
                    "avatar_url": None,
                    "description": "helper",
                    "owner_kyc_level": 0,
                    "agent_reputation": 10,
                },
            ),
        )

    transport = httpx.MockTransport(handler)
    agent = LimeAgent(
        agent_token="at_secret",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=transport),
    )
    profile = await agent.get_profile()
    await agent.aclose()

    assert profile.agent_id == "agent_1"
    assert profile.owner_id == "owner_1"
    assert profile.display_name == "Bot"
    assert profile.avatar_url is None
    assert profile.description == "helper"
    assert profile.owner_kyc_level == 0
    assert profile.agent_reputation == 10


@pytest.mark.asyncio
async def test_get_profile_accepts_user_id_alias() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_envelope_ok(
                {
                    "agent_id": "agent_1",
                    "user_id": "user_1",
                    "display_name": "Bot",
                    "avatar_url": None,
                    "description": None,
                    "user_kyc_level": 3,
                    "agent_reputation": 0,
                },
            ),
        )

    transport = httpx.MockTransport(handler)
    agent = LimeAgent(
        agent_token="at_secret",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=transport),
    )
    profile = await agent.get_profile()
    await agent.aclose()

    assert profile.owner_id == "user_1"
    assert profile.owner_kyc_level == 3


def test_agent_profile_from_api_requires_owner_or_user_id() -> None:
    with pytest.raises(KeyError, match="owner_id"):
        AgentProfile.from_api({"agent_id": "a1"})


def test_missing_token_raises() -> None:
    old = os.environ.pop("LIME_AGENT_TOKEN", None)
    try:
        with pytest.raises(AuthenticationError, match="Agent token is required"):
            LimeAgent()
    finally:
        if old is not None:
            os.environ["LIME_AGENT_TOKEN"] = old


def test_reads_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIME_AGENT_TOKEN", "at_from_env")
    agent = LimeAgent()
    assert agent._client._agent_token == "at_from_env"  # noqa: SLF001


def test_reads_base_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIME_AGENT_TOKEN", "at_x")
    monkeypatch.setenv("LIME_API_BASE", "http://custom/api/v1")
    agent = LimeAgent()
    assert agent._client._base_url == "http://custom/api/v1"  # noqa: SLF001


@pytest.mark.asyncio
async def test_context_manager() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_envelope_ok(
                {
                    "agent_id": "a",
                    "owner_id": "o",
                    "display_name": None,
                    "avatar_url": None,
                    "description": None,
                    "owner_kyc_level": 0,
                    "agent_reputation": 0,
                },
            ),
        )

    transport = httpx.MockTransport(handler)
    async with LimeAgent(
        agent_token="at_x",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=transport),
    ) as agent:
        profile = await agent.get_profile()
    assert profile.agent_id == "a"


@pytest.mark.asyncio
async def test_login_empty_request_id_raises() -> None:
    async with LimeAgent(agent_token="at_x", base_url="http://mock/api/v1") as agent:
        with pytest.raises(ApiError) as exc:
            await agent.login("   ")
    assert exc.value.code == "INVALID_REQUEST_ID"
    assert exc.value.http_status == 400


@pytest.mark.asyncio
async def test_login_strips_request_id() -> None:
    challenge = "strip-challenge"
    difficulty = 8
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if request.method == "GET":
            return httpx.Response(
                200,
                content=_envelope_ok(
                    {
                        "request_id": "lr_trimmed",
                        "status": "PENDING",
                        "pow_challenge": challenge,
                        "pow_difficulty": difficulty,
                        "expires_at": "2026-06-10T12:00:00+00:00",
                    },
                ),
            )
        return httpx.Response(
            200,
            content=_envelope_ok(
                {
                    "request_id": "lr_trimmed",
                    "site_id": "site_1",
                    "status": "DELIVERED",
                    "expires_at": "2026-06-10T12:00:00+00:00",
                    "approved_agent_id": "agent_1",
                },
            ),
        )

    transport = httpx.MockTransport(handler)
    agent = LimeAgent(
        agent_token="at_secret",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=transport),
        pow_timeout=5.0,
    )
    await agent.login("  lr_trimmed  ")
    await agent.aclose()

    assert seen_urls[0].endswith("/auth/requests/lr_trimmed")
    assert seen_urls[1].endswith("/modules/agent-login/requests/lr_trimmed/approve")


@pytest.mark.asyncio
async def test_login_public_get_has_no_agent_token() -> None:
    challenge = "header-challenge"
    difficulty = 8
    public_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            public_headers.update(dict(request.headers))
            return httpx.Response(
                200,
                content=_envelope_ok(
                    {
                        "request_id": "lr_hdr",
                        "status": "PENDING",
                        "pow_challenge": challenge,
                        "pow_difficulty": difficulty,
                        "expires_at": "2026-06-10T12:00:00+00:00",
                    },
                ),
            )
        assert request.headers.get("X-Agent-Token") == "at_secret"
        return httpx.Response(
            200,
            content=_envelope_ok(
                {
                    "request_id": "lr_hdr",
                    "site_id": "site_1",
                    "status": "DELIVERED",
                    "expires_at": "2026-06-10T12:00:00+00:00",
                    "approved_agent_id": "agent_1",
                },
            ),
        )

    transport = httpx.MockTransport(handler)
    agent = LimeAgent(
        agent_token="at_secret",
        base_url="http://mock/api/v1",
        http_client=httpx.AsyncClient(transport=transport),
        pow_timeout=5.0,
    )
    await agent.login("lr_hdr")
    await agent.aclose()

    assert "x-agent-token" not in {k.lower() for k in public_headers}
