"""Shared test fixtures for document-service tests."""

import tempfile

import pytest

import reality_rag_persistence.database as db
from reality_rag_persistence.database import get_session
from reality_rag_persistence.seed import seed


@pytest.fixture(autouse=True)
def _setup_database():
    db.override_url_for_testing("sqlite:///:memory:")
    db.create_all()
    session = get_session()
    try:
        seed(session=session)
    finally:
        session.close()
    yield
    db.drop_all()


@pytest.fixture(autouse=True)
def _setup_staging_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("DOCUMENT_STAGING_DIR", tmp)
        monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", tmp)
        yield
