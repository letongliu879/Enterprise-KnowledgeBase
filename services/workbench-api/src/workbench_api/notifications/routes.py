"""Notification routes — local in-memory store for workbench notifications."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..errors import not_found

router = APIRouter(prefix="/workbench/notifications")

# In-memory store: tenant_id -> list of notification dicts
_store: dict[str, list[dict]] = {}
_counter: int = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("")
async def list_notifications(user: CurrentUser = Depends(require_auth)):
    tenant = user.tenant_id
    items = _store.get(tenant, [])
    unread_count = sum(1 for n in items if not n["is_read"])
    return {"items": items, "total": len(items), "unread_count": unread_count}


@router.patch("/{notification_id}/read")
async def mark_read(notification_id: str, user: CurrentUser = Depends(require_auth)):
    tenant = user.tenant_id
    items = _store.get(tenant, [])
    for n in items:
        if n["notification_id"] == notification_id:
            n["is_read"] = True
            n["read_at"] = _now()
            return {"notification_id": notification_id, "is_read": True}
    raise not_found(f"Notification not found: {notification_id}")


@router.post("/read-all")
async def read_all(user: CurrentUser = Depends(require_auth)):
    tenant = user.tenant_id
    items = _store.get(tenant, [])
    count = 0
    for n in items:
        if not n["is_read"]:
            n["is_read"] = True
            n["read_at"] = _now()
            count += 1
    return {"count": count}


@router.get("/unread-count")
async def unread_count(user: CurrentUser = Depends(require_auth)):
    tenant = user.tenant_id
    items = _store.get(tenant, [])
    count = sum(1 for n in items if not n["is_read"])
    return {"count": count}
