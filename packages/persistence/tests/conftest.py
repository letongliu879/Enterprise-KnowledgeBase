"""Tests for Reality-RAG Persistence package.

Uses SQLite :memory: for fast, isolated repository tests.
"""

import pytest
from sqlalchemy.orm import Session

from reality_rag_persistence.database import (
    create_all,
    drop_all,
    get_session,
    override_url_for_testing,
)


@pytest.fixture(autouse=True)
def _setup_database():
    """Reset database to SQLite in-memory before each test."""
    override_url_for_testing("sqlite:///:memory:")
    create_all()
    yield
    drop_all()


@pytest.fixture
def session() -> Session:
    s = get_session()
    yield s
    s.close()
