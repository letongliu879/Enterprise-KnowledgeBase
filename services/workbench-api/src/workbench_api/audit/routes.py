"""Audit log routes — proxy to Admin service."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..downstream_clients import AdminClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable

router = APIRouter(prefix="/workbench/audit-logs")


@router.get("")
async def list_audit_logs(
    action: str | None = None,
    target_type: str | None = None,
    actor_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    payload = {
        "action": action,
        "target_type": target_type,
        "actor_id": actor_id,
        "limit": limit,
        "offset": offset,
        "tenant_id": user.tenant_id,
    }
    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        result = await client.list_audit_logs(
            payload,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin audit log API unavailable: {e.message}")
        raise downstream_unavailable(f"Admin audit log API error: {e.message}")
    return result


@router.post("/export")
async def export_audit_logs(
    body: dict,
    user: CurrentUser = Depends(require_auth),
):
    return {"download_url": "/workbench/audit-logs/export/download.csv"}
