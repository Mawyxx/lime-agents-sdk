from __future__ import annotations

import hashlib
import time

from lime_agents._errors import PowTimeoutError


def _is_valid_pow(challenge: str, nonce: str, difficulty: int) -> bool:
    digest_hex = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
    threshold = 2 ** (256 - difficulty)
    return bool(int(digest_hex, 16) < threshold)


def solve(challenge: str, difficulty: int, *, max_timeout: float = 10.0) -> str:
    """Find a nonce satisfying the LIME PoW policy."""
    if difficulty <= 0:
        return "0"

    deadline = time.monotonic() + max_timeout
    nonce = 0
    while time.monotonic() < deadline:
        candidate = str(nonce)
        if _is_valid_pow(challenge, candidate, difficulty):
            return candidate
        nonce += 1

    raise PowTimeoutError(
        f"PoW not solved within {max_timeout}s (difficulty={difficulty})",
    )
