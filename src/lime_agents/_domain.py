"""MCP target domain extraction for Zero-Touch OAuth (ADR 0081).

Keep the normalize algorithm in sync with ADR 0081 / monorepo
``srcN/modules/oauth/domain/mcp_domain.py``, with one intentional delta:
strip ``:port`` instead of rejecting, so Zero-Touch URLs with ports still
mint JWTs (LIME token API rejects ports server-side).
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def extract_and_normalize_domain(target: str) -> str:
    """Extract a portless DNS hostname from ``target`` for token/cache keys.

    Accepts bare hostnames or URL-ish strings. Strips ``http(s)://``, path after
    the first ``/``, and ``:port``. Rejects empty input, userinfo, and IP literals.

    Raises:
        ValueError: When ``target`` is empty or not a valid DNS hostname.
    """
    if not isinstance(target, str):
        raise ValueError("target must be a non-empty string")

    value = target.strip()
    if not value:
        raise ValueError("target must be a non-empty string")

    lower = value.lower()
    if lower.startswith("https://"):
        value = value[8:]
    elif lower.startswith("http://"):
        value = value[7:]

    if "/" in value:
        value = value.split("/", 1)[0]

    value = value.strip().lower()
    if not value:
        raise ValueError("target must contain a valid DNS hostname")

    if "@" in value:
        raise ValueError("target must not include userinfo")

    if value.startswith("[") and "]" in value:
        raise ValueError("target must not be an IP address")

    if ":" in value:
        host, _, port = value.partition(":")
        if not port.isdigit():
            raise ValueError("target must contain a valid DNS hostname")
        value = host

    if not value:
        raise ValueError("target must contain a valid DNS hostname")

    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise ValueError("target must not be an IP address")

    if not _HOSTNAME_RE.match(value):
        raise ValueError("target must contain a valid DNS hostname")

    return value


def resolve_mcp_http_url(target: str) -> str:
    """Resolve ``target`` to an MCP streamable-HTTP URL (port/path may be kept).

    Bare hostnames become ``https://{host}/mcp``. Full ``http(s)`` URLs are
    normalized (strip whitespace / trailing slash) and validated.
    """
    if not isinstance(target, str):
        raise ValueError("target must be a non-empty string")

    raw = target.strip()
    if not raw:
        raise ValueError("target must be a non-empty string")

    # Validate domain extractability first (rejects IPs / userinfo / empty).
    _ = extract_and_normalize_domain(raw)

    lower = raw.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        normalized = raw.rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("target must be an http(s) URL or hostname")
        return normalized

    host = raw.split("/", 1)[0].strip().lower()
    if ":" in host:
        # Keep port on the MCP HTTP URL; domain extract already validated digits.
        return f"https://{host}/mcp"
    return f"https://{host}/mcp"
