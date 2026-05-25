"""Shared test fixtures for ingestion-worker tests."""

import tempfile

import pytest

import reality_rag_persistence.database as db
from reality_rag_persistence.database import get_session
from reality_rag_persistence.seed import seed


@pytest.fixture(autouse=True)
def _setup_database():
    db.override_url_for_testing("sqlite:///:memory:")
    db.create_all()
    _session = get_session()
    try:
        seed(session=_session)
    finally:
        _session.close()
    yield
    db.drop_all()


@pytest.fixture(autouse=True)
def _setup_sidecar_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", tmp)
        yield
