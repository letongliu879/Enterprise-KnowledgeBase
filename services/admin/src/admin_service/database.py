"""Admin database initialization."""

from reality_rag_persistence.database import create_all, override_url_for_testing


__all__ = ["init_database", "override_url_for_testing"]


def init_database() -> None:
    create_all()
