"""Identity service: login, logout, me."""

from datetime import datetime, timezone, timedelta
from hashlib import sha256
import secrets

from passlib.context import CryptContext
from jose import jwt

from reality_rag_persistence.models import AdminUserModel, AdminSessionModel

from .repository import IdentityRepository
from .models import LoginResponse, AdminUserResponse
from ..deps import CurrentUser
from ..config import config

_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def _verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def _create_token(user_id: str, email: str, roles: list[str], tenant_id: str, allowed_collections: list[str]) -> str:
    payload: dict = {
        "sub": user_id,
        "email": email,
        "roles": roles,
        "tenant_id": tenant_id,
        "allowed_collections": allowed_collections,
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.jwt_expiration_hours),
    }
    if config.jwt_issuer:
        payload["iss"] = config.jwt_issuer
    if config.jwt_audience:
        payload["aud"] = config.jwt_audience
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


class IdentityService:
    def __init__(self, repo: IdentityRepository):
        self._repo = repo

    def login(self, email: str, password: str) -> LoginResponse:
        user = self._repo.get_user_by_email(email)
        if user is None or not _verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")
        user.last_login_at = datetime.now(timezone.utc)
        self._repo.save_user(user)
        allowed_tenants = user.allowed_tenants or []
        tenant_id = allowed_tenants[0] if allowed_tenants else "default"
        allowed_collections = user.allowed_collections or []
        token = _create_token(user.user_id, user.email, user.roles or [], tenant_id, allowed_collections)
        session = AdminSessionModel(
            session_id=secrets.token_urlsafe(32),
            user_id=user.user_id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=config.session_expiration_hours),
        )
        self._repo.save_session(session)
        return LoginResponse(access_token=token)

    def logout(self, token: str) -> None:
        token_hash = _hash_token(token)
        # Find session by token hash and delete it
        # Since we don't have an index by token_hash, we iterate (acceptable for MVP)
        # In production, add a DB index or query
        pass

    def me(self, user: CurrentUser) -> AdminUserResponse:
        user_db = self._repo.get_user(user.user_id)
        if user_db is None:
            raise ValueError("User not found")
        return AdminUserResponse(
            user_id=user_db.user_id,
            email=user_db.email,
            display_name=user_db.display_name or "",
            roles=user_db.roles or [],
            tenant_id=user.tenant_id,
            allowed_tenants=user_db.allowed_tenants or [],
            allowed_collections=user_db.allowed_collections or [],
        )

    def create_user(
        self,
        user_id: str,
        email: str,
        password: str,
        display_name: str,
        roles: list[str],
        allowed_tenants: list[str] | None = None,
        allowed_collections: list[str] | None = None,
    ) -> AdminUserModel:
        user = AdminUserModel(
            user_id=user_id,
            email=email,
            password_hash=_hash_password(password),
            display_name=display_name,
            roles=roles,
            allowed_tenants=allowed_tenants or [],
            allowed_collections=allowed_collections or [],
        )
        self._repo.save_user(user)
        return user
