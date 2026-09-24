from __future__ import annotations

import hashlib
import time

from lime_agents._errors import PowTimeoutError

# R-14 domain separation: servers verify SHA-256(b"lime:pow:v1\0" || challenge || 0x00 || nonce).
# NOTE: the published PyPI lime-agents-sdk still solves the legacy SHA-256(challenge+nonce)
# formula until an external release of github.com/Mawyxx/lime-agents-sdk ships.
_POW_DOMAIN_PREFIX = b"lime:pow:v1\0"
_POW_FIELD_SEPARATOR = b"\0"


def _is_valid_pow(challenge: str, nonce: str, difficulty: int) -> bool:
    digest_hex = hashlib.sha256(
        _POW_DOMAIN_PREFIX + challenge.encode() + _POW_FIELD_SEPARATOR + nonce.encode()
    ).hexdigest()
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
