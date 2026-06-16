"""Live integration tests against LIME API (production or staging).

Run: LIME_INTEGRATION=1 pytest tests/integration -v
"""

from __future__ import annotations

import os

import httpx
import pytest

from lime_agents import ApiError, LimeAgent
from lime_agents._errors import LimeError

from .bootstrap import DEFAULT_BASE_URL, ensure_tokens

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("LIME_API_BASE", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture
async def tokens() -> tuple[str, str]:
    return await ensure_tokens(BASE_URL)


@pytest.fixture
async def site_token(tokens: tuple[str, str]) -> str:
    return tokens[1]


@pytest.fixture
async def agent_token(tokens: tuple[str, str]) -> str:
    return tokens[0]


async def _create_login_request(site_token: str) -> str:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        response = await client.post(
            "/modules/agent-login/requests",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Site-Token": site_token,
            },
            json={},
        )
        body = response.json()
        assert response.status_code in (200, 201), body
        assert body.get("ok") is True
        return str(body["data"]["login_request_id"])


async def _get_request_status(site_token: str, request_id: str) -> str:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        response = await client.get(
            f"/modules/agent-login/requests/{request_id}",
            headers={
                "Accept": "application/json",
                "X-Site-Token": site_token,
            },
        )
        body = response.json()
        assert response.status_code == 200, body
        assert body.get("ok") is True
        return str(body["data"]["status"])


@pytest.mark.asyncio
async def test_full_cycle_login_and_profile(agent_token: str, site_token: str) -> None:
    request_id = await _create_login_request(site_token)

    async with LimeAgent(agent_token=agent_token, base_url=BASE_URL) as agent:
        result = await agent.login(request_id)
        assert result.status in {"APPROVED", "DELIVERED"}
        assert result.request_id == request_id

        profile = await agent.get_profile()
        assert profile.agent_id.strip()
        assert profile.owner_id.strip()
        if profile.display_name is not None:
            assert profile.display_name.strip()

    site_status = await _get_request_status(site_token, request_id)
    assert site_status in {"APPROVED", "DELIVERED"}


@pytest.mark.asyncio
async def test_pow_rejects_before_approve(agent_token: str, site_token: str) -> None:
    """Invalid PoW must fail before approve gate; challenge stays for retry."""
    request_id = await _create_login_request(site_token)
    approve_path = f"/modules/agent-login/requests/{request_id}/approve"
    agent_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Agent-Token": agent_token,
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        missing = await client.post(approve_path, headers=agent_headers, json={})
        missing_body = missing.json()
        assert missing.status_code == 400
        assert missing_body["error"]["code"] == "MISSING_POW_NONCE"

        invalid = await client.post(
            approve_path,
            headers=agent_headers,
            json={"pow_nonce": "definitely-invalid-nonce"},
        )
        invalid_body = invalid.json()
        assert invalid.status_code == 400
        assert invalid_body["error"]["code"] == "INVALID_POW"

        assert await _get_request_status(site_token, request_id) == "PENDING"

        challenge = await client.get(f"/auth/requests/{request_id}")
        challenge_body = challenge.json()
        assert challenge.status_code == 200
        assert challenge_body["data"]["pow_challenge"]
        assert challenge_body["data"]["pow_difficulty"] is not None


@pytest.mark.asyncio
async def test_invalid_request_id_raises(agent_token: str) -> None:
    invalid_id = "00000000-0000-4000-8000-000000000099"
    async with LimeAgent(agent_token=agent_token, base_url=BASE_URL) as agent:
        with pytest.raises((ApiError, LimeError)) as exc_info:
            await agent.login(invalid_id)
        err = exc_info.value
        if isinstance(err, ApiError):
            assert err.http_status == 404
            assert err.code == "SITE_LOGIN_REQUEST_NOT_FOUND"
