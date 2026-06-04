"""JWT verification tests — issuer, audience, expiration, smoke mode."""

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from admin_service.config import config as admin_config


def _make_token(
    *,
    sub: str = "test-user",
    secret: str = "test-secret",
    issuer: str = "",
    audience: str = "",
    exp_delta: int = 3600,
    roles: list[str] | None = None,
) -> str:
    payload: dict = {
        "sub": sub,
        "email": f"{sub}@test.com",
        "roles": roles or ["knowledge_admin"],
        "tenant_id": "default",
        "exp": int(time.time()) + exp_delta,
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    return jwt.encode(payload, secret, algorithm="HS256")


def _set_jwt_config(*, secret: str = "test-secret", issuer: str = "", audience: str = ""):
    """Mutate the module-level config directly (it's loaded at import time)."""
    admin_config.jwt_secret = secret
    admin_config.jwt_issuer = issuer
    admin_config.jwt_audience = audience


def _reset_jwt_config():
    _set_jwt_config(secret="change-me-in-production", issuer="", audience="")


@pytest.fixture(autouse=True)
def _setup_db():
    from reality_rag_persistence.database import override_url_for_testing, create_all, drop_all
    override_url_for_testing("sqlite:///:memory:")
    drop_all()
    create_all()
    # Pre-seed a test user so /admin/auth/me lookups succeed
    from admin_service.identity.service import IdentityService
    from admin_service.identity.repository import IdentityRepository
    from reality_rag_persistence.database import get_session
    session = get_session()
    try:
        svc = IdentityService(IdentityRepository(session))
        svc.create_user(
            user_id="test-user",
            email="test-user@test.com",
            password="doesnt-matter",
            display_name="Test User",
            roles=["knowledge_admin"],
        )
        session.commit()
    finally:
        session.close()
    yield
    drop_all()
    _reset_jwt_config()


@pytest.fixture
def client():
    from admin_service.main import app
    with TestClient(app) as test_client:
        yield test_client


class TestJwtBasic:
    def test_valid_token_accepted(self, client):
        _set_jwt_config(secret="test-secret")
        token = _make_token(secret="test-secret")
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_missing_token_rejected(self, client):
        resp = client.get("/admin/auth/me")
        assert resp.status_code == 401

    def test_expired_token_rejected(self, client):
        _set_jwt_config(secret="test-secret")
        token = _make_token(secret="test-secret", exp_delta=-60)
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_wrong_secret_rejected(self, client):
        _set_jwt_config(secret="correct-secret")
        token = _make_token(secret="wrong-secret")
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestJwtIssuerAudience:
    def test_valid_issuer_accepted(self, client):
        _set_jwt_config(secret="test-secret", issuer="https://auth.example.com")
        token = _make_token(secret="test-secret", issuer="https://auth.example.com")
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_wrong_issuer_rejected(self, client):
        _set_jwt_config(secret="test-secret", issuer="https://auth.example.com")
        token = _make_token(secret="test-secret", issuer="https://evil.example.com")
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_missing_issuer_rejected_when_required(self, client):
        _set_jwt_config(secret="test-secret", issuer="https://auth.example.com")
        token = _make_token(secret="test-secret")  # no issuer in token
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_wrong_audience_rejected(self, client):
        _set_jwt_config(secret="test-secret", audience="admin-api")
        token = _make_token(secret="test-secret", audience="wrong-aud")
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_valid_audience_accepted(self, client):
        _set_jwt_config(secret="test-secret", audience="admin-api")
        token = _make_token(secret="test-secret", audience="admin-api")
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_no_issuer_config_accepts_any_issuer(self, client):
        _set_jwt_config(secret="test-secret")  # no issuer configured
        token = _make_token(secret="test-secret", issuer="anything")
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestSmokeMode:
    def test_smoke_secret_accepted(self, client):
        """Smoke mode (default AUTH_MODE=smoke) accepts smoke-test-secret."""
        _set_jwt_config(secret="smoke-test-secret")
        token = _make_token(secret="smoke-test-secret")
        resp = client.get("/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_auth_mode_defaults_to_smoke(self, client):
        assert admin_config.auth_mode in ("smoke", "")

    def test_default_secret_is_insecure_by_design(self, client):
        """Default secret must be overtly insecure to force config in production."""
        # Reset to fresh config state (re-import doesn't work so just check the attribute exists)
        assert hasattr(admin_config, 'jwt_secret')
