# Backend Missing API Endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 19 missing REST API endpoints across workbench-api and admin-service, prioritized by P0-P3.

**Architecture:** workbench-api acts as FastAPI proxy layer — most new endpoints delegate to downstream services (admin, intake, approval, indexing) or read from SQL projections. Admin service is the control plane that owns collections, profiles, API keys, audit logs.

**Tech Stack:** FastAPI, Python 3.12+, SQLAlchemy, httpx, pytest + respx (mock downstream), jose (JWT)

---

## File Structure

### New files to create:
- `services/workbench-api/src/workbench_api/tickets/comments_routes.py` — Comment CRUD proxy
- `services/workbench-api/src/workbench_api/tickets/transfer_routes.py` — Transfer proxy
- `services/workbench-api/src/workbench_api/documents/share_routes.py` — Share link proxy
- `services/workbench-api/src/workbench_api/dashboard/routes.py` — Dashboard aggregation
- `services/workbench-api/src/workbench_api/notifications/routes.py` — Notification proxy
- `services/workbench-api/src/workbench_api/trash/routes.py` — Trash proxy

### Existing files to modify:
- `services/workbench-api/src/workbench_api/main.py` — Register new routers
- `services/workbench-api/src/workbench_api/collections/routes.py` — Add PATCH/DELETE/GET by id
- `services/workbench-api/src/workbench_api/task_projection/routes.py` — Add POST cancel
- `services/workbench-api/src/workbench_api/parse_snapshot/routes.py` — GET source already exists (verified)
- `services/workbench-api/src/workbench_api/documents/routes.py` — Add share endpoint
- `services/workbench-api/src/workbench_api/retrieval_profiles/routes.py` — Add full CRUD
- `services/workbench-api/src/workbench_api/parser_selection/routes.py` — Add full CRUD
- `services/workbench-api/src/workbench_api/downstream_clients/clients.py` — Add new client methods
- `services/workbench-api/src/workbench_api/auth/routes.py` — Add display_name
- `services/workbench-api/src/workbench_api/health/routes.py` — ingestion status already exists

### Test files:
- `services/workbench-api/tests/test_task_cancel.py`
- `services/workbench-api/tests/test_ticket_comments.py`
- `services/workbench-api/tests/test_ticket_transfer.py`
- `services/workbench-api/tests/test_collection_detail.py`
- `services/workbench-api/tests/test_document_share.py`
- `services/workbench-api/tests/test_dashboard.py`
- `services/workbench-api/tests/test_notifications.py`
- `services/workbench-api/tests/test_trash.py`
- Plus modifications to existing test files

---

## Task 1: POST /workbench/tasks/{id}/cancel — Cancel upload task

**Files:**
- Modify: `services/workbench-api/src/workbench_api/task_projection/routes.py`
- Test: `services/workbench-api/tests/test_task_cancel.py` (new)

**RED — Write failing test:**
```python
# tests/test_task_cancel.py
def test_cancel_task_success(client, uploader_token, db_session):
    from reality_rag_persistence.models import WorkbenchTaskProjectionModel
    from datetime import datetime, timezone, timedelta
    
    proj = WorkbenchTaskProjectionModel(
        upload_id="upload_cancel_001",
        tenant_id="tenant_acme",
        user_id="user-001",
        collection_id="col_default",
        filename="test.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        source_file_id="sf_cancel_001",
        overall_status="uploading",
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        projection_updated_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    db_session.commit()
    
    resp = client.post(
        "/workbench/tasks/upload_cancel_001/cancel",
        headers={"Authorization": f"Bearer {uploader_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cancelled"
    assert data["task_id"] == "upload_cancel_001"


def test_cancel_task_not_found(client, uploader_token):
    resp = client.post(
        "/workbench/tasks/nonexistent/cancel",
        headers={"Authorization": f"Bearer {uploader_token}"},
    )
    assert resp.status_code == 404


def test_cancel_task_already_final(client, uploader_token, db_session):
    from reality_rag_persistence.models import WorkbenchTaskProjectionModel
    from datetime import datetime, timezone, timedelta
    
    proj = WorkbenchTaskProjectionModel(
        upload_id="upload_final_001",
        tenant_id="tenant_acme",
        user_id="user-001",
        collection_id="col_default",
        filename="test.docx",
        overall_status="completed",
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        projection_updated_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    db_session.commit()
    
    resp = client.post(
        "/workbench/tasks/upload_final_001/cancel",
        headers={"Authorization": f"Bearer {uploader_token}"},
    )
    assert resp.status_code == 409
```

**Verify RED:**
```bash
cd services/workbench-api && uv run pytest tests/test_task_cancel.py -v --tb=short
# Expected: FAIL — 404 (route doesn't exist yet)
```

**GREEN — Minimal implementation in task_projection/routes.py:**
```python
@router.post("/{upload_id}/cancel")
async def cancel_task(
    upload_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Cancel an in-progress upload task."""
    repo = TaskProjectionRepository(db)
    proj = repo.get_by_upload_id(upload_id)
    if proj is None:
        raise not_found("Task not found")
    if proj.tenant_id != user.tenant_id:
        raise not_found("Task not found")
    
    terminal_states = {"completed", "cancelled", "failed", "archived", "retracted"}
    if _correct_status(proj) in terminal_states:
        raise conflict("Task is already in a terminal state and cannot be cancelled")
    
    projector = ProjectionProjector(db)
    from datetime import datetime, timezone
    projector.record_and_apply({
        "event_id": f"cancel_{upload_id}_{uuid.uuid4().hex[:8]}",
        "event_type": "TASK_CANCELLED",
        "tenant_id": proj.tenant_id,
        "collection_id": proj.collection_id,
        "aggregate_type": "task",
        "aggregate_id": upload_id,
        "aggregate_version": proj.version + 1,
        "occurred_at": datetime.now(timezone.utc),
        "payload": {
            "projection_id": upload_id,
            "overall_status": "cancelled",
        },
        "trace_id": upload_id,
    })
    db.commit()
    return {"status": "cancelled", "task_id": upload_id}
```

Also add `conflict` to imports at top of file:
```python
from ..errors import not_found, conflict
```
Also add `datetime` and `uuid` (uuid already imported):
```python
from datetime import datetime, timezone
```

**Verify GREEN:**
```bash
cd services/workbench-api && uv run pytest tests/test_task_cancel.py -v --tb=short
# Expected: 3 PASSED
```

---

## Task 2: Ticket Comments CRUD — GET/POST /tickets/{id}/comments + PATCH/DELETE /comments/{id}

**Files:**
- Create: `services/workbench-api/src/workbench_api/tickets/comments_routes.py`
- Modify: `services/workbench-api/src/workbench_api/main.py` — register comments router
- Test: `services/workbench-api/tests/test_ticket_comments.py` (new)

**RED — Write failing tests:**
```python
# tests/test_ticket_comments.py
def test_list_ticket_comments_empty(client, reviewer_token):
    resp = client.get(
        "/workbench/tickets/ticket_comment_001/comments",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_create_ticket_comment(client, reviewer_token, db_session):
    from reality_rag_persistence.models import WorkbenchTicketProjectionModel
    from datetime import datetime, timezone
    
    proj = WorkbenchTicketProjectionModel(
        ticket_id="ticket_comment_002",
        tenant_id="tenant_acme",
        collection_id="col_default",
        state="pending",
        created_at=datetime.now(timezone.utc),
        projection_updated_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    db_session.commit()
    
    resp = client.post(
        "/workbench/tickets/ticket_comment_002/comments",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"content": "This is a test comment"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "This is a test comment"
    assert data["ticket_id"] == "ticket_comment_002"
    assert data["author_id"] == "user-003"


def test_update_own_comment(client, reviewer_token, db_session):
    from reality_rag_persistence.models import WorkbenchTicketProjectionModel, TicketCommentModel
    from datetime import datetime, timezone
    
    ticket_proj = WorkbenchTicketProjectionModel(
        ticket_id="ticket_comment_003",
        tenant_id="tenant_acme",
        collection_id="col_default",
        state="pending",
        created_at=datetime.now(timezone.utc),
        projection_updated_at=datetime.now(timezone.utc),
    )
    db_session.add(ticket_proj)
    
    comment = TicketCommentModel(
        comment_id="comment_003",
        ticket_id="ticket_comment_003",
        tenant_id="tenant_acme",
        author_id="user-003",
        author_email="reviewer@example.com",
        content="Original content",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(comment)
    db_session.commit()
    
    resp = client.patch(
        "/workbench/comments/comment_003",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"content": "Updated content"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated content"


def test_delete_own_comment(client, reviewer_token, db_session):
    from reality_rag_persistence.models import TicketCommentModel
    from datetime import datetime, timezone
    
    comment = TicketCommentModel(
        comment_id="comment_004",
        ticket_id="ticket_comment_004",
        tenant_id="tenant_acme",
        author_id="user-003",
        author_email="reviewer@example.com",
        content="To be deleted",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(comment)
    db_session.commit()
    
    resp = client.delete(
        "/workbench/comments/comment_004",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 204


def test_update_others_comment_forbidden(client, uploader_token, db_session):
    from reality_rag_persistence.models import TicketCommentModel
    from datetime import datetime, timezone
    
    comment = TicketCommentModel(
        comment_id="comment_005",
        ticket_id="ticket_comment_005",
        tenant_id="tenant_acme",
        author_id="other-user",
        author_email="other@example.com",
        content="Someone else's comment",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(comment)
    db_session.commit()
    
    resp = client.patch(
        "/workbench/comments/comment_005",
        headers={"Authorization": f"Bearer {uploader_token}"},
        json={"content": "Hacked!"},
    )
    assert resp.status_code == 403


def test_create_comment_empty_content(client, reviewer_token):
    resp = client.post(
        "/workbench/tickets/ticket_comment_006/comments",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"content": ""},
    )
    assert resp.status_code == 400
```

**Verify RED:**
```bash
cd services/workbench-api && uv run pytest tests/test_ticket_comments.py -v --tb=short
# Expected: FAIL — 404 (route doesn't exist)
```

**GREEN — Create comments_routes.py:**
```python
"""Ticket comment routes — CRUD for comments on review tickets."""

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..errors import not_found, forbidden, bad_request
from ..projections.repository import TicketProjectionRepository

router = APIRouter()


class CreateCommentRequest(BaseModel):
    content: str = Field(min_length=1)


class UpdateCommentRequest(BaseModel):
    content: str = Field(min_length=1)


@router.get("/workbench/tickets/{ticket_id}/comments")
def list_comments(
    ticket_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    from reality_rag_persistence.models import TicketCommentModel
    
    ticket_repo = TicketProjectionRepository(db)
    ticket = ticket_repo.get(ticket_id)
    if not ticket or not user.can_access_collection(ticket.collection_id):
        return {"items": [], "total": 0}
    
    comments = db.query(TicketCommentModel).filter(
        TicketCommentModel.ticket_id == ticket_id,
        TicketCommentModel.tenant_id == user.tenant_id,
    ).order_by(TicketCommentModel.created_at).all()
    
    return {
        "items": [
            {
                "comment_id": c.comment_id,
                "ticket_id": c.ticket_id,
                "author_id": c.author_id,
                "author_name": c.author_name,
                "author_email": c.author_email,
                "content": c.content,
                "mentions": c.mentions,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in comments
        ],
        "total": len(comments),
    }


@router.post("/workbench/tickets/{ticket_id}/comments", status_code=201)
def create_comment(
    ticket_id: str,
    req: CreateCommentRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    if not req.content.strip():
        raise bad_request("Comment content must not be empty")
    
    from reality_rag_persistence.models import TicketCommentModel
    
    ticket_repo = TicketProjectionRepository(db)
    ticket = ticket_repo.get(ticket_id)
    if not ticket or not user.can_access_collection(ticket.collection_id):
        return {"items": [], "total": 0}
    
    comment_id = f"cmt_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)
    comment = TicketCommentModel(
        comment_id=comment_id,
        ticket_id=ticket_id,
        tenant_id=user.tenant_id,
        author_id=user.user_id,
        author_email=user.email,
        author_name=user.email.split("@")[0] if user.email else None,
        content=req.content,
        mentions=[],
        created_at=now,
        updated_at=now,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return {
        "comment_id": comment.comment_id,
        "ticket_id": comment.ticket_id,
        "author_id": comment.author_id,
        "author_name": comment.author_name,
        "author_email": comment.author_email,
        "content": comment.content,
        "mentions": comment.mentions,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
    }


@router.patch("/workbench/comments/{comment_id}")
def update_comment(
    comment_id: str,
    req: UpdateCommentRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    from reality_rag_persistence.models import TicketCommentModel
    
    comment = db.query(TicketCommentModel).filter(
        TicketCommentModel.comment_id == comment_id,
        TicketCommentModel.tenant_id == user.tenant_id,
    ).first()
    
    if not comment:
        raise not_found("Comment not found")
    if comment.author_id != user.user_id:
        raise forbidden("Cannot edit another user's comment")
    if not req.content.strip():
        raise bad_request("Comment content must not be empty")
    
    comment.content = req.content
    comment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)
    
    return {
        "comment_id": comment.comment_id,
        "ticket_id": comment.ticket_id,
        "author_id": comment.author_id,
        "author_name": comment.author_name,
        "author_email": comment.author_email,
        "content": comment.content,
        "mentions": comment.mentions,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
    }


@router.delete("/workbench/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    from reality_rag_persistence.models import TicketCommentModel
    
    comment = db.query(TicketCommentModel).filter(
        TicketCommentModel.comment_id == comment_id,
        TicketCommentModel.tenant_id == user.tenant_id,
    ).first()
    
    if not comment:
        raise not_found("Comment not found")
    if comment.author_id != user.user_id:
        raise forbidden("Cannot delete another user's comment")
    
    db.delete(comment)
    db.commit()
```

Modify `main.py` to include comments router:
```python
from .tickets.comments_routes import router as ticket_comments_router
# ... in create_app():
application.include_router(ticket_comments_router)
```

**Verify GREEN:**
```bash
cd services/workbench-api && uv run pytest tests/test_ticket_comments.py -v --tb=short
# Expected: 6 PASSED
```

---

## Task 3: POST /workbench/tickets/{id}/transfer — Ticket transfer

**Files:**
- Create: `services/workbench-api/src/workbench_api/tickets/transfer_routes.py`
- Modify: `services/workbench-api/src/workbench_api/main.py` — register transfer router
- Test: `services/workbench-api/tests/test_ticket_transfer.py` (new)

**RED — Write failing test:**
```python
# tests/test_ticket_transfer.py
def test_transfer_ticket_success(client, reviewer_token, db_session):
    from reality_rag_persistence.models import WorkbenchTicketProjectionModel
    from datetime import datetime, timezone
    
    proj = WorkbenchTicketProjectionModel(
        ticket_id="ticket_transfer_001",
        tenant_id="tenant_acme",
        collection_id="col_default",
        state="pending",
        assignee_user_id=None,
        created_at=datetime.now(timezone.utc),
        projection_updated_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    db_session.commit()
    
    resp = client.post(
        "/workbench/tickets/ticket_transfer_001/transfer",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"assignee_user_id": "user-new", "reason": "Please review"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["assignee_user_id"] == "user-new"


def test_transfer_self_forbidden(client, reviewer_token, db_session):
    from reality_rag_persistence.models import WorkbenchTicketProjectionModel
    from datetime import datetime, timezone
    
    proj = WorkbenchTicketProjectionModel(
        ticket_id="ticket_transfer_002",
        tenant_id="tenant_acme",
        collection_id="col_default",
        state="pending",
        created_at=datetime.now(timezone.utc),
        projection_updated_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    db_session.commit()
    
    resp = client.post(
        "/workbench/tickets/ticket_transfer_002/transfer",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"assignee_user_id": "user-003"},
    )
    assert resp.status_code == 400


def test_transfer_ticket_not_found(client, reviewer_token):
    resp = client.post(
        "/workbench/tickets/nonexistent/transfer",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"assignee_user_id": "user-new"},
    )
    assert resp.status_code == 404
```

**Verify RED → GREEN** (same cycle as above)

**GREEN — Minimal transfer_routes.py:**
```python
"""Ticket transfer routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..errors import not_found, bad_request
from ..projections.repository import TicketProjectionRepository

router = APIRouter()


class TransferRequest(BaseModel):
    assignee_user_id: str
    reason: str | None = None


@router.post("/workbench/tickets/{ticket_id}/transfer")
def transfer_ticket(
    ticket_id: str,
    req: TransferRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    repo = TicketProjectionRepository(db)
    proj = repo.get(ticket_id)
    if not proj or not user.can_access_collection(proj.collection_id):
        raise not_found("Ticket not found")
    
    if req.assignee_user_id == user.user_id:
        raise bad_request("Cannot transfer ticket to yourself")
    
    proj.assignee_user_id = req.assignee_user_id
    db.commit()
    
    return {
        "ticket_id": proj.ticket_id,
        "collection_id": proj.collection_id,
        "status": proj.state,
        "assignee_user_id": proj.assignee_user_id,
    }
```

---

## Task 4: PATCH/DELETE/GET collections/:id — Collection detail, edit, delete

**Files:**
- Modify: `services/workbench-api/src/workbench_api/collections/routes.py`
- Test: `services/workbench-api/tests/test_collection_detail.py` (new)

**RED — Write failing test:**
```python
# tests/test_collection_detail.py
@respx.mock
def test_get_collection_detail(client, admin_token):
    respx.get("http://localhost:8005/admin/collections/col_test").respond(
        200, json={"collection_id": "col_test", "name": "Test", "tenant_id": "tenant_acme"}
    )
    resp = client.get(
        "/workbench/collections/col_test",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["collection_id"] == "col_test"


def test_delete_collection(client, admin_token):
    respx.delete("http://localhost:8005/admin/collections/col_del").respond(
        200, json={"status": "deleted", "collection_id": "col_del"}
    )
    resp = client.delete(
        "/workbench/collections/col_del",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@respx.mock
def test_patch_collection(client, admin_token):
    respx.patch("http://localhost:8005/admin/collections/col_upd").respond(
        200, json={"collection_id": "col_upd", "name": "Updated"}
    )
    resp = client.patch(
        "/workbench/collections/col_upd",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"
```

**GREEN — Add routes to collections/routes.py:**
```python
@router.get("/{collection_id}")
async def get_collection(
    collection_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.get_collection(
            collection_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented("Admin collections API unavailable")
        raise
    return result


@router.patch("/{collection_id}")
async def patch_collection(
    collection_id: str,
    req: dict,
    user: CurrentUser = Depends(require_role("knowledge_admin")),
):
    client = AdminClient()
    try:
        result = await client._request("patch", f"/admin/collections/{collection_id}", json=req, headers={"Authorization": f"Bearer {user.token}"})
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented("Admin collections API unavailable")
        raise
    return result


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    user: CurrentUser = Depends(require_role("knowledge_admin")),
):
    client = AdminClient()
    try:
        result = await client._request("delete", f"/admin/collections/{collection_id}", headers={"Authorization": f"Bearer {user.token}"})
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented("Admin collections API unavailable")
        if e.code == "NOT_FOUND":
            raise not_found("Collection not found")
        raise
    return result
```

Also add `patch` and `delete` methods to AdminClient:
```python
async def patch_collection(self, collection_id: str, payload: dict, *, headers: dict | None = None) -> dict:
    return await self._request("patch", f"/admin/collections/{collection_id}", json=payload, headers=headers)

async def delete_collection(self, collection_id: str, *, headers: dict | None = None) -> dict:
    return await self._request("delete", f"/admin/collections/{collection_id}", headers=headers)
```

---

## Task 5: POST /workbench/documents/{id}/share — Share link generation

**Files:**
- Modify: `services/workbench-api/src/workbench_api/documents/routes.py` — Add share endpoint
- Modify: `services/workbench-api/src/workbench_api/downstream_clients/clients.py` — Add share methods
- Test: `services/workbench-api/tests/test_document_share.py` (new)

**RED — Write failing test:**
```python
# tests/test_document_share.py
@respx.mock
def test_share_document(client, admin_token, db_session):
    from reality_rag_persistence.models import WorkbenchDocumentProjectionModel
    from datetime import datetime, timezone
    
    proj = WorkbenchDocumentProjectionModel(
        doc_id="doc_share_001",
        tenant_id="tenant_acme",
        collection_id="col_default",
        filename="test.pdf",
        document_state="ACTIVE",
        projection_updated_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    db_session.commit()
    
    resp = client.post(
        "/workbench/documents/doc_share_001/share",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"expires_in_hours": 168},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "share_url" in data
    assert "expires_at" in data


def test_share_document_not_found(client, admin_token):
    resp = client.post(
        "/workbench/documents/nonexistent/share",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"expires_in_hours": 168},
    )
    assert resp.status_code == 404
```

**GREEN — Add share document post handler to documents/routes.py:**
```python
from .models import (
    ...
    DocumentShareRequest,
    DocumentShareResponse,
)

# Add share endpoint after reindex
@router.post("/workbench/documents/{doc_id}/share")
async def share_document(
    doc_id: str,
    req: DocumentShareRequest,
    user: CurrentUser = Depends(require_auth),
):
    from datetime import datetime, timedelta, timezone
    import uuid
    
    expires_at = datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours or 168)
    share_id = f"shr_{uuid.uuid4().hex[:16]}"
    share_url = f"{config.access_base_url}/share/{share_id}"
    
    return DocumentShareResponse(
        share_url=share_url,
        expires_at=expires_at.isoformat(),
    )
```

Add models:
```python
# documents/models.py
class DocumentShareRequest(BaseModel):
    expires_in_hours: int = 168
    password: str | None = None


class DocumentShareResponse(BaseModel):
    share_url: str
    expires_at: str
```

---

## Task 6: GET /workbench/dashboard — Dashboard aggregation

**Files:**
- Create: `services/workbench-api/src/workbench_api/dashboard/routes.py`
- Modify: `services/workbench-api/src/workbench_api/main.py` — register dashboard router
- Test: `services/workbench-api/tests/test_dashboard.py` (new)

**RED → GREEN** — Dashboard reads from SQL projections:
```python
# dashboard/routes.py
@router.get("/workbench/dashboard")
def get_dashboard(
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    from reality_rag_persistence.models import (
        WorkbenchTaskProjectionModel,
        WorkbenchTicketProjectionModel,
        WorkbenchDocumentProjectionModel,
    )
    import sqlalchemy as sa
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_uploads = db.query(sa.func.count(WorkbenchTaskProjectionModel.upload_id)).filter(
        WorkbenchTaskProjectionModel.tenant_id == user.tenant_id,
        WorkbenchTaskProjectionModel.created_at >= today_start,
    ).scalar() or 0
    
    pending_review = db.query(sa.func.count(WorkbenchTicketProjectionModel.ticket_id)).filter(
        WorkbenchTicketProjectionModel.tenant_id == user.tenant_id,
        WorkbenchTicketProjectionModel.state == "pending",
    ).scalar() or 0
    
    total_docs = db.query(sa.func.count(WorkbenchDocumentProjectionModel.doc_id)).filter(
        WorkbenchDocumentProjectionModel.tenant_id == user.tenant_id,
    ).scalar() or 0
    
    stale_docs = db.query(sa.func.count(WorkbenchDocumentProjectionModel.doc_id)).filter(
        WorkbenchDocumentProjectionModel.tenant_id == user.tenant_id,
        WorkbenchDocumentProjectionModel.is_stale == True,
    ).scalar() or 0
    stale_ratio = round(stale_docs / total_docs, 2) if total_docs > 0 else 0.0
    
    recent_tickets = db.query(WorkbenchTicketProjectionModel).filter(
        WorkbenchTicketProjectionModel.tenant_id == user.tenant_id,
    ).order_by(WorkbenchTicketProjectionModel.created_at.desc()).limit(10).all()
    
    return {
        "stats": {
            "today_uploads": today_uploads,
            "pending_review_count": pending_review,
            "total_documents": total_docs,
            "stale_ratio": stale_ratio,
        },
        "recent_tickets": [
            {
                "ticket_id": t.ticket_id,
                "collection_id": t.collection_id,
                "status": t.state,
                "filename": t.filename,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in recent_tickets
        ],
    }
```
