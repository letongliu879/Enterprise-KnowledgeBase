"""Thin wrapper around persistence database."""

from reality_rag_persistence.database import create_all, drop_all, override_url_for_testing


__all__ = ["create_all", "drop_all", "override_url_for_testing"]
