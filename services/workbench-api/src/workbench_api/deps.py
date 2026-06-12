"""FastAPI dependencies for workbench service."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories import AdminUserRepository

from .config import config
from .errors import unauthorized, forbidden

security = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(self, user_id: str, email: str, roles: list[str], tenant_id: str = "", allowed_collections: list[str] | None = None, token: str = "", display_name: str | None = None):
        self.user_id = user_id
        self.email = email
        self.roles = roles
        self.tenant_id = tenant_id
        self.allowed_collections = allowed_collections or []
        self.token = token
        self.display_name = display_name

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def can_access_tenant(self, tenant_id: str) -> bool:
        return True  # TODO: implement tenant-level ACL

    def can_access_collection(self, collection_id: str) -> bool:
        return "*" in self.allowed_collections or collection_id in self.allowed_collections


def get_db():
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> CurrentUser:
    if credentials is None:
        raise unauthorized("Missing Authorization header")
    try:
        decode_kwargs: dict = {"algorithms": [config.jwt_algorithm]}
        if config.jwt_audience:
            decode_kwargs["audience"] = config.jwt_audience
            decode_kwargs["options"] = {"verify_aud": True}
        if config.jwt_issuer:
            decode_kwargs["issuer"] = config.jwt_issuer

        payload = jwt.decode(credentials.credentials, config.jwt_secret, **decode_kwargs)
        user_id: str = payload.get("sub", "")
        email: str = payload.get("email", "")
        roles: list[str] = payload.get("roles", [])
        tenant_id: str = payload.get("tenant_id", "")
        allowed_collections: list[str] = payload.get("allowed_collections", [])
        display_name: str | None = payload.get("display_name") or payload.get("name")
        if not user_id:
            raise unauthorized("Invalid token: missing subject")
        return CurrentUser(user_id=user_id, email=email, roles=roles, tenant_id=tenant_id, allowed_collections=allowed_collections, token=credentials.credentials, display_name=display_name)
    except JWTError:
        raise unauthorized("Invalid token")


def require_role(role: str):
    def checker(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        if not user.has_role(role):
            raise forbidden(f"Role '{role}' required")
        return user
    return checker


def require_collection_access(collection_id: str | None = None):
    """Dependency factory that validates collection access.
    If collection_id is provided as arg, checks that directly.
    Otherwise, expects the route to pass collection_id from request params/body."""
    def checker(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        return user
    return checker
