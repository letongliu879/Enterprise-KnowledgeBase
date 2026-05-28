"""Auth routes for admin service."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .service import IdentityService
from .repository import IdentityRepository
from .models import LoginRequest, LoginResponse, AdminUserResponse
from ..deps import get_db, require_auth, CurrentUser
from ..errors import unauthorized, not_found

router = APIRouter(prefix="/admin/auth")


def _get_identity_service(session: Session = Depends(get_db)) -> IdentityService:
    return IdentityService(IdentityRepository(session))


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, service: IdentityService = Depends(_get_identity_service)):
    try:
        return service.login(req.email, req.password)
    except ValueError as e:
        raise unauthorized(str(e))


@router.post("/logout")
def logout(request: Request, user: CurrentUser = Depends(require_auth)):
    # Extract token from Authorization header and invalidate session
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # TODO: invalidate session by token hash
    return {"message": "Logged out"}


@router.get("/me", response_model=AdminUserResponse)
def me(user: CurrentUser = Depends(require_auth), service: IdentityService = Depends(_get_identity_service)):
    try:
        return service.me(user.user_id)
    except ValueError as e:
        raise not_found(str(e))
