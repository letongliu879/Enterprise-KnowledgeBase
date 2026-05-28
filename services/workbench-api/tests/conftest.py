"""Test fixtures for workbench-api."""

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from reality_rag_persistence.database import override_url_for_testing, create_all, drop_all

from workbench_api.main import app
from workbench_api.config import config


@pytest.fixture(autouse=True)
def _setup_db():
    override_url_for_testing("sqlite:///:memory:")
    drop_all()
    create_all()
    yield
    drop_all()


@pytest.fixture
def client():
    return TestClient(app)


def _make_token(user_id: str, email: str, roles: list[str], tenant_id: str = "tenant_acme", allowed_collections: list[str] | None = None) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "roles": roles,
        "tenant_id": tenant_id,
        "allowed_collections": allowed_collections or ["col_default"],
    }
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)


@pytest.fixture
def uploader_token():
    return _make_token("user-001", "uploader@example.com", ["uploader"])


@pytest.fixture
def chunk_editor_token():
    return _make_token("user-002", "editor@example.com", ["uploader", "chunk_editor"])


@pytest.fixture
def reviewer_token():
    return _make_token("user-003", "reviewer@example.com", ["reviewer"])


@pytest.fixture
def admin_token():
    return _make_token("user-004", "admin@example.com", ["platform_admin"])


@pytest.fixture
def db_session():
    from reality_rag_persistence.database import get_session
    session = get_session()
    try:
        yield session
    finally:
        session.commit()
        session.close()
