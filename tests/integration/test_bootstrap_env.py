"""Env-based resolution of prod verify tokens (no committed literals)."""

from __future__ import annotations

from pathlib import Path

import pytest

from . import bootstrap
from .bootstrap import (
    PROD_VERIFY_AGENT_TOKEN_ENV,
    PROD_VERIFY_SITE_TOKEN_ENV,
    TokensUnavailable,
    ensure_tokens,
)

_PROD_BASE_URL = "https://lime.pics/api/v1"


def _clear_token_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(bootstrap, "TOKENS_FILE", tmp_path / ".tokens.env")
    for name in (
        "LIME_AGENT_TOKEN",
        "LIME_SITE_TOKEN",
        "LIME_INTEGRATION_BOOTSTRAP_REGISTER",
        PROD_VERIFY_AGENT_TOKEN_ENV,
        PROD_VERIFY_SITE_TOKEN_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


async def test_prod_verify_tokens_are_read_from_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_token_env(monkeypatch, tmp_path)
    monkeypatch.setenv(PROD_VERIFY_AGENT_TOKEN_ENV, "agent-token-from-env")
    monkeypatch.setenv(PROD_VERIFY_SITE_TOKEN_ENV, "site-token-from-env")

    tokens = await ensure_tokens(_PROD_BASE_URL)

    assert tokens == ("agent-token-from-env", "site-token-from-env")


async def test_prod_verify_tokens_unavailable_without_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_token_env(monkeypatch, tmp_path)

    with pytest.raises(TokensUnavailable):
        await ensure_tokens(_PROD_BASE_URL)
