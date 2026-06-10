from __future__ import annotations

import hashlib

import pytest

from lime_agents._errors import PowTimeoutError
from lime_agents._pow import solve


def _verify_pow(challenge: str, nonce: str, difficulty: int) -> bool:
    if difficulty <= 0:
        return True
    digest_hex = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
    threshold = 2 ** (256 - difficulty)
    return int(digest_hex, 16) < threshold


def test_solve_finds_valid_nonce() -> None:
    challenge = "test-challenge-abc"
    difficulty = 8
    nonce = solve(challenge, difficulty, max_timeout=5.0)
    assert _verify_pow(challenge, nonce, difficulty)


def test_solve_zero_difficulty_returns_zero() -> None:
    assert solve("any-challenge", 0) == "0"
    assert solve("any-challenge", -1) == "0"


def test_solve_timeout_raises() -> None:
    with pytest.raises(PowTimeoutError, match="PoW not solved"):
        solve("impossible-challenge-fixed", 32, max_timeout=0.01)
