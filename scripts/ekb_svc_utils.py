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
