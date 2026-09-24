"""MCP target domain extraction for Zero-Touch OAuth (ADR 0081).

Host policy (parity with monorepo
``srcN/modules/oauth/domain/mcp_domain.py``):

- Only strict RFC 1123 DNS hostnames are accepted.
- IP literals are rejected in every common encoding: ``ipaddress`` rejects
  dotted-quad/v6, and a numeric/hex-only label scan rejects abbreviated and
  obfuscated forms (``127.1``, ``2130706433``, ``0x7f000001``, ``0177.0.0.1``).
- Reserved / special-use names are rejected: ``localhost``, ``*.local``,
  ``*.internal``, ``*.intranet``, ``*.corp``, ``*.home``, ``*.lan``, cloud
  metadata (``metadata.google.internal``), ``kubernetes*``, and wildcard DNS
  services that encode an IP in the name (``nip.io`` / ``sslip.io`` / ``xip.io``
  / ``traefik.me`` / ``localtest.me`` / ``lvh.me``).
- Host validation is syntactic and deterministic: no DNS resolution happens in
  the trust decision (no network, no TOCTOU).

One intentional delta from Core: strip ``:port`` instead of rejecting, so
Zero-Touch URLs with ports still mint JWTs (LIME token API rejects ports
server-side).
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

_NUMERIC_LABEL_RE = re.compile(r"^(?:0[xX][0-9a-fA-F]+|[0-9]+)$")

_RESERVED_EXACT = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata",
        "kubernetes",
        "kubernetes.default",
        "kubernetes.default.svc",
        "nip.io",
        "sslip.io",
        "xip.io",
        "traefik.me",
        "localtest.me",
        "lvh.me",
    }
)

_RESERVED_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".intranet",
    ".corp",
    ".home",
    ".lan",
    ".nip.io",
    ".sslip.io",
    ".xip.io",
    ".traefik.me",
    ".localtest.me",
    ".lvh.me",
)


def _is_reserved_hostname(host: str) -> bool:
    if host in _RESERVED_EXACT:
        return True
    return any(host.endswith(suffix) for suffix in _RESERVED_SUFFIXES)


def _is_ip_literal_obfuscation(host: str) -> bool:
    """True when every dot-separated label is decimal/octal/hex.

    Catches forms that ``ipaddress`` correctly refuses but down-stack HTTP
    clients may still resolve (``127.1``, ``2130706433``, ``0x7f.0.0.1``).
    """
    return all(_NUMERIC_LABEL_RE.match(label) for label in host.split("."))


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

    if _is_ip_literal_obfuscation(value):
        raise ValueError("target must not be an IP address")

    if not _HOSTNAME_RE.match(value):
        raise ValueError("target must contain a valid DNS hostname")

    if _is_reserved_hostname(value):
        raise ValueError("target must not be a reserved or special-use hostname")

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
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:  # pragma: no cover
            raise ValueError("target must be an http(s) URL or hostname")
        return normalized

    host = raw.split("/", 1)[0].strip().lower()
    if ":" in host:
        # Keep port on the MCP HTTP URL; domain extract already validated digits.
        return f"https://{host}/mcp"
    return f"https://{host}/mcp"
