"""Auth routes for workbench."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser

router = APIRouter(prefix="/workbench/auth")


@router.get("/me")
def get_me(user: CurrentUser = Depends(require_auth)) -> dict:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "roles": user.roles,
        "tenant_id": user.tenant_id,
        "allowed_collections": user.allowed_collections,
        "display_name": user.display_name,
    }
