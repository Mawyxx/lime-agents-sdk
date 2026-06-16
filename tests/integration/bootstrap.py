"""Provision or load integration tokens for live API tests."""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

TOKENS_FILE = Path(__file__).with_name(".tokens.env")
DEFAULT_BASE_URL = "https://lime.pics/api/v1"

# Bootstrapped on production for PoW verify (scripts/pow_prod_bootstrap_verify.py).
_PROD_VERIFY_SITE_TOKEN = "pow-prod-verify-site-token-v1"
_PROD_VERIFY_AGENT_TOKEN = "pow-prod-verify-agent-token-v1"


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def save_tokens(agent_token: str, site_token: str) -> None:
    TOKENS_FILE.write_text(
        f"LIME_AGENT_TOKEN={agent_token}\nLIME_SITE_TOKEN={site_token}\n",
        encoding="utf-8",
    )


def load_tokens_from_file() -> tuple[str, str] | None:
    if not TOKENS_FILE.exists():
        return None
    data = _parse_env_file(TOKENS_FILE)
    agent = data.get("LIME_AGENT_TOKEN", "").strip()
    site = data.get("LIME_SITE_TOKEN", "").strip()
    if agent and site:
        return agent, site
    return None


async def bootstrap_tokens_via_register(
    base_url: str,
    *,
    turnstile_token: str = "XXXX.DUMMY.TOKEN.XXXX",
) -> tuple[str, str]:
    """Register owner, site, and agent via public API (requires valid Turnstile on prod)."""
    suffix = str(int(time.time()))
    email = f"sdk-integration-{suffix}@example.com"
    password = "SdkIntegration1!Aa"
    cookie_jar = httpx.Cookies()

    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        timeout=60.0,
        cookies=cookie_jar,
    ) as client:
        reg = await client.post(
            "/foundation/users/register",
            json={
                "email": email,
                "password": password,
                "turnstile_token": turnstile_token,
            },
        )
        if reg.status_code != 201:
            raise RuntimeError(
                f"owner register failed HTTP {reg.status_code}: {reg.text[:300]}",
            )

        verify_code = os.getenv("LIME_INTEGRATION_VERIFY_CODE", "").strip()
        if not verify_code:
            raise RuntimeError(
                "Set LIME_INTEGRATION_VERIFY_CODE after register, or provide tokens in env",
            )

        verify = await client.post(
            "/foundation/users/register/verify",
            json={"email": email, "code": verify_code},
        )
        if verify.status_code not in (200, 201):
            raise RuntimeError(f"verify failed HTTP {verify.status_code}: {verify.text[:300]}")

        login = await client.post(
            "/foundation/users/login",
            json={"email": email, "password": password},
        )
        if login.status_code != 200:
            raise RuntimeError(f"login failed HTTP {login.status_code}: {login.text[:300]}")

        csrf = cookie_jar.get("lime_csrf", "")
        session_headers = {"X-CSRF-Token": csrf} if csrf else {}

        site_resp = await client.post(
            "/foundation/sites/register",
            json={"display_name": f"SDK Integration {suffix}"},
            headers=session_headers,
        )
        if site_resp.status_code != 201:
            raise RuntimeError(f"site register failed HTTP {site_resp.status_code}")
        site_body = site_resp.json()
        site_token = str(site_body["data"]["site_token"])

        agent_resp = await client.post(
            "/core/agents/register",
            json={
                "display_name": f"SDK Agent {suffix}",
                "description": "lime-agents-sdk integration",
            },
            headers=session_headers,
        )
        if agent_resp.status_code != 201:
            raise RuntimeError(f"agent register failed HTTP {agent_resp.status_code}")
        agent_body = agent_resp.json()
        agent_token = str(agent_body["data"]["agent_token"])

    return agent_token, site_token


async def ensure_tokens(base_url: str) -> tuple[str, str]:
    """Resolve agent and site tokens from env, cache file, bootstrap, or prod fixtures."""
    agent = os.getenv("LIME_AGENT_TOKEN", "").strip()
    site = os.getenv("LIME_SITE_TOKEN", "").strip()
    if agent and site:
        return agent, site

    cached = load_tokens_from_file()
    if cached:
        return cached

    if os.getenv("LIME_INTEGRATION_BOOTSTRAP_REGISTER") == "1":
        tokens = await bootstrap_tokens_via_register(base_url)
        save_tokens(*tokens)
        return tokens

    if "lime.pics" in base_url:
        tokens = (_PROD_VERIFY_AGENT_TOKEN, _PROD_VERIFY_SITE_TOKEN)
        save_tokens(*tokens)
        return tokens

    raise RuntimeError(
        "Set LIME_AGENT_TOKEN and LIME_SITE_TOKEN, or LIME_INTEGRATION_BOOTSTRAP_REGISTER=1",
    )
