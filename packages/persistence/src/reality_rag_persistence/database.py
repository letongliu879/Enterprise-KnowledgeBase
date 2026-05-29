"""SQLAlchemy engine and session factory.

Supports both PostgreSQL (production) and SQLite (testing/dev fallback).
Configure via DATABASE_URL environment variable.

Engine is created lazily — the module can be imported without a
database driver installed (tests can call override_url_for_testing
before the first session is requested).
"""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
SessionLocal: sessionmaker | None = None
_override_url: str | None = None


def _resolve_database_url() -> str:
    if _override_url:
        return _override_url
    return os.getenv(
        "DATABASE_URL",
        "postgresql://reality:reality@127.0.0.1:5432/reality_rag",
    )


def _get_engine() -> Engine:
    global _engine, SessionLocal
    if _engine is None:
        database_url = _resolve_database_url()
        try:
            _engine = create_engine(database_url, echo=False)
        except (ImportError, ModuleNotFoundError) as e:
            if database_url.startswith("postgresql"):
                raise RuntimeError(
                    f"PostgreSQL driver (psycopg2) not installed but DATABASE_URL={database_url}. "
                    "Install psycopg2, or set DATABASE_URL=sqlite:///:memory: for local dev."
                ) from e
            raise
        SessionLocal = sessionmaker(bind=_engine)
    return _engine


def get_session() -> Session:
    """Return a new SQLAlchemy session. Caller is responsible for closing."""
    if SessionLocal is None:
        _get_engine()
    return SessionLocal()


def _ensure_column_exists(table_name: str, column_name: str, column_type: str) -> None:
    """Add a column to an existing table if it doesn't exist (dev-only schema sync)."""
    from sqlalchemy import inspect, text
    engine = _get_engine()
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns(table_name)}
    if column_name in columns:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def create_all() -> None:
    """Create all tables. For dev/seed usage only — not for production migrations."""
    from .models import Base
    Base.metadata.create_all(bind=_get_engine())
    # Sync columns added after initial table creation
    _ensure_column_exists("workbench_upload_sessions", "access_scope_json", "JSON")


def drop_all() -> None:
    """Drop all tables. Dev tool only."""
    from .models import Base
    Base.metadata.drop_all(bind=_get_engine())


def override_url_for_testing(url: str) -> None:
    """Override DATABASE_URL for tests (e.g. sqlite:///:memory:).

    Uses StaticPool so every session shares the same :memory: database
    even across threads (e.g. TestClient async requests).
    """
    global _engine, SessionLocal, _override_url
    _override_url = url
    if url.startswith("sqlite") or url.startswith("sqlite3"):
        from sqlalchemy.pool import StaticPool
        _engine = create_engine(
            url, echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        _engine = create_engine(url, echo=False)
    SessionLocal = sessionmaker(bind=_engine)
