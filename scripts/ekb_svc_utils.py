"""Utility helpers for ekb-svc.py (extracted for testability)."""

from __future__ import annotations


def _convert_to_jdbc_url(url: str) -> str:
    """Convert SQLAlchemy PostgreSQL URL to JDBC URL for Spring Boot.

    SQLAlchemy: postgresql://user:pass@host:port/db
    JDBC:       jdbc:postgresql://host:port/db

    Note: JDBC URLs should NOT contain user:pass. Spring Boot reads
    DATABASE_USERNAME and DATABASE_PASSWORD separately.
    """
    if url.startswith("jdbc:"):
        return url
    if not url.startswith("postgresql://"):
        return url

    # Strip the scheme
    rest = url[len("postgresql://") :]

    # If there's an auth section (user:pass@), drop it
    if "@" in rest:
        _, rest = rest.split("@", 1)

    return "jdbc:postgresql://" + rest

import os
import socket
import urllib.request
from urllib.parse import urlparse


def _parse_url(url: str) -> tuple[str, str, int | None, str]:
    """Parse a URL into (scheme, host, port, path)."""
    parsed = urlparse(url)
    port = parsed.port
    if port is None:
        default_ports = {"http": 80, "https": 443, "redis": 6379, "postgresql": 5432}
        port = default_ports.get(parsed.scheme)
    return parsed.scheme, parsed.hostname or "", port, parsed.path or "/"


def _probe_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _probe_http(url: str, timeout: float = 2.0) -> bool:
    """Return True if an HTTP GET to url succeeds (2xx or 3xx)."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def _probe_url(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    """Probe a URL and return (ok, human_readable_message)."""
    scheme, host, port, path = _parse_url(url)
    if not host:
        return False, f"URL has no host: {url}"
    if scheme in ("postgresql", "postgres"):
        if port is None:
            port = 5432
        ok = _probe_tcp(host, port, timeout)
        return ok, f"PostgreSQL at {host}:{port}"
    if scheme == "redis":
        if port is None:
            port = 6379
        ok = _probe_tcp(host, port, timeout)
        return ok, f"Redis at {host}:{port}"
    if scheme in ("http", "https"):
        probe_url = url if path and path != "/" else f"{url.rstrip('/')}/"
        ok = _probe_http(probe_url, timeout)
        return ok, f"HTTP endpoint {probe_url}"
    return False, f"Unsupported URL scheme '{scheme}': {url}"


def _validate_required_endpoints() -> list[str]:
    """Validate the infrastructure URLs configured in the environment."""
    required = [
        ("DATABASE_URL", "PostgreSQL"),
        ("OPENSEARCH_BASE_URL", "OpenSearch"),
        ("INDEXING_OPENSEARCH_URL", "OpenSearch (indexing)"),
        ("QDRANT_BASE_URL", "Qdrant"),
        ("INDEXING_QDRANT_URL", "Qdrant (indexing)"),
        ("REDIS_URL", "Redis"),
    ]
    errors: list[str] = []
    for env_var, label in required:
        url = os.environ.get(env_var)
        if not url:
            errors.append(f"{label}: {env_var} is not set")
            continue
        ok, description = _probe_url(url)
        if not ok:
            hint = ""
            if env_var in ("OPENSEARCH_BASE_URL", "INDEXING_OPENSEARCH_URL"):
                hint = (
                    "  docker-compose.yml maps OpenSearch host port 19201 -> container 9201; "
                    "when running services locally, .env must use http://127.0.0.1:19201"
                )
            errors.append(f"{label} ({env_var}={url}) is unreachable.{hint}")
    return errors
