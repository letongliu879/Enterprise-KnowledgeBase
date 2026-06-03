"""Pytest fixtures for admin service tests."""

import pytest
from fastapi.testclient import TestClient

from reality_rag_persistence.database import override_url_for_testing, create_all, drop_all
from admin_service.identity.service import IdentityService
from admin_service.identity.repository import IdentityRepository


@pytest.fixture(autouse=True)
def _setup_db():
    override_url_for_testing("sqlite:///:memory:")
    drop_all()
    create_all()
    yield
    drop_all()


@pytest.fixture
def client():
    from admin_service.main import app
    return TestClient(app)


@pytest.fixture
def db_session():
    from reality_rag_persistence.database import get_session
    session = get_session()
    try:
        yield session
    finally:
        session.commit()
        session.close()


@pytest.fixture
def identity_service(db_session):
    return IdentityService(IdentityRepository(db_session))


@pytest.fixture
def admin_user(identity_service):
    user = identity_service.create_user(
        user_id="admin-1",
        email="admin@example.com",
        password="secret123",
        display_name="Admin User",
        roles=["platform_admin"],
        allowed_tenants=["tenant_admin"],
        allowed_collections=["col_default", "col_ops"],
    )
    return user


@pytest.fixture
def knowledge_admin(identity_service):
    user = identity_service.create_user(
        user_id="kadmin-1",
        email="kadmin@example.com",
        password="secret123",
        display_name="Knowledge Admin",
        roles=["knowledge_admin"],
        allowed_tenants=["tenant_admin"],
        allowed_collections=["col_default"],
    )
    return user


@pytest.fixture
def viewer_user(identity_service):
    user = identity_service.create_user(
        user_id="viewer-1",
        email="viewer@example.com",
        password="secret123",
        display_name="Viewer",
        roles=["auditor"],
        allowed_tenants=["tenant_admin"],
        allowed_collections=["col_default"],
    )
    return user


@pytest.fixture
def admin_token(client, admin_user):
    resp = client.post("/admin/auth/login", json={
        "email": "admin@example.com",
        "password": "secret123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def knowledge_admin_token(client, knowledge_admin):
    resp = client.post("/admin/auth/login", json={
        "email": "kadmin@example.com",
        "password": "secret123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def viewer_token(client, viewer_user):
    resp = client.post("/admin/auth/login", json={
        "email": "viewer@example.com",
        "password": "secret123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]
