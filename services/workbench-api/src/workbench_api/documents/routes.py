"""Document workspace and lifecycle proxy routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..chunk_edits.repository import ChunkEditRepository
from ..deps import CurrentUser, get_db, require_auth
from ..downstream_clients import AdminClient, ApprovalClient, IndexingClient, IntakeClient
from ..downstream_clients.errors import DownstreamError
from ..errors import conflict, downstream_not_implemented, downstream_unavailable, forbidden, not_found
from ..projections.repository import (
    AgentReviewProjectionRepository,
    DocumentProjectionRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)
from ..workspace.models import WorkspaceDetailView
from ..workspace.service import WorkspaceService
from .models import (
    BatchDocumentActionItemResult,
    BatchDocumentActionRequest,
    BatchDocumentActionResult,
    DocumentLifecycleActionRequest,
    DocumentShareRequest,
    DocumentShareResponse,
)

router = APIRouter()


def _get_workspace_service(session: Session = Depends(get_db)) -> WorkspaceService:
    return WorkspaceService(
        task_repo=TaskProjectionRepository(session),
        ticket_repo=TicketProjectionRepository(session),
        document_repo=DocumentProjectionRepository(session),
        agent_review_repo=AgentReviewProjectionRepository(session),
        chunk_edit_repo=ChunkEditRepository(session),
        intake_client=IntakeClient(),
        approval_client=ApprovalClient(),
        indexing_client=IndexingClient(),
    )


def _require_document_admin(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    if user.has_role("knowledge_admin") or user.has_role("platform_admin"):
        return user
    raise forbidden("Knowledge admin or platform admin role required")


def _admin_headers(user: CurrentUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


def _map_context_error(result: dict) -> Exception:
    if result.get("error") == "document_not_found":
        return not_found("Document not found")
    if result.get("error") == "collection_access_denied":
        return forbidden("Collection access denied")
    return conflict("Document lifecycle context could not be resolved")


def _map_downstream_error(error: DownstreamError, action: str, *, doc_id: str) -> Exception:
    if error.status_code == 404:
        return not_found(f"Document {doc_id} not found")
    if error.status_code == 409:
        return conflict(f"{action} failed: {error.message}")
    if error.status_code == 501:
        return downstream_not_implemented(f"{action} is not implemented downstream")
    return downstream_unavailable(f"{action} failed: {error.message}")


async def _run_document_action(
    *,
    doc_id: str,
    action: str,
    request: DocumentLifecycleActionRequest,
    user: CurrentUser,
    workspace_service: WorkspaceService,
    admin_client: AdminClient,
) -> dict:
    context = workspace_service.resolve_document_action_context(doc_id, user)
    if context.get("error"):
        raise _map_context_error(context)

    final_doc_id = str(context["final_doc_id"] or "")
    collection_id = str(context["collection_id"] or "")
    tenant_id = str(context["tenant_id"] or "")
    parse_snapshot_id = context.get("parse_snapshot_id")
    document_view = context.get("document")
    if not final_doc_id or not collection_id or not tenant_id:
        raise conflict("Document lifecycle context is incomplete")

    can_archive, can_retract, can_reindex = workspace_service._can_manage_document_lifecycle(  # noqa: SLF001
        user,
        document_view=document_view,
    )
    if action == "archive" and not can_archive:
        raise conflict("Document is not eligible for archive")
    if action == "retract" and not can_retract:
        raise conflict("Document is not eligible for retract")
    if action == "reindex" and not can_reindex:
        raise conflict("Document is not eligible for reindex")

    payload = {
        "command_id": f"wb_{action}_{uuid.uuid4().hex[:12]}",
        "trace_id": f"trc_{uuid.uuid4().hex[:16]}",
        "idempotency_key": f"{action}:{final_doc_id}",
        "actor": user.user_id,
        "reason": request.reason,
    }
    if action == "reindex":
        if not parse_snapshot_id:
            raise conflict("Document does not have a parse snapshot and cannot be reindexed")
        payload.update(
            {
                "collection_id": collection_id,
                "tenant_id": tenant_id,
                "parse_snapshot_id": str(parse_snapshot_id),
                "index_profile_id": request.index_profile_id or "ragflow",
                "idempotency_key": f"{action}:{final_doc_id}:{uuid.uuid4().hex[:12]}",
            }
        )

    try:
        if action == "archive":
            return await admin_client.archive_document(final_doc_id, payload, headers=_admin_headers(user))
        if action == "retract":
            return await admin_client.retract_document(final_doc_id, payload, headers=_admin_headers(user))
        if action == "reindex":
            return await admin_client.reindex_document(final_doc_id, payload, headers=_admin_headers(user))
    except DownstreamError as error:
        raise _map_downstream_error(error, action, doc_id=doc_id) from error

    raise conflict(f"Unsupported document action: {action}")


async def _run_document_action_best_effort(
    *,
    doc_id: str,
    action: str,
    request: DocumentLifecycleActionRequest,
    user: CurrentUser,
    workspace_service: WorkspaceService,
    admin_client: AdminClient,
) -> BatchDocumentActionItemResult:
    try:
        result = await _run_document_action(
            doc_id=doc_id,
            action=action,
            request=request,
            user=user,
            workspace_service=workspace_service,
            admin_client=admin_client,
        )
        return BatchDocumentActionItemResult(
            doc_id=doc_id,
            success=bool(result.get("success", True)),
            previous_state=result.get("previous_state"),
            new_state=result.get("new_state"),
            job_id=result.get("job_id"),
        )
    except Exception as error:  # noqa: BLE001
        if hasattr(error, "detail") and isinstance(getattr(error, "detail"), dict):
            detail = getattr(error, "detail")
            return BatchDocumentActionItemResult(
                doc_id=doc_id,
                success=False,
                error_code=str(detail.get("error_code") or detail.get("code") or "ERROR"),
                error_message=str(detail.get("message") or "Request failed"),
            )
        return BatchDocumentActionItemResult(
            doc_id=doc_id,
            success=False,
            error_code="ERROR",
            error_message=str(error),
        )


@router.get("/workbench/documents/{doc_id}/workspace", response_model=WorkspaceDetailView)
async def get_document_workspace(
    doc_id: str,
    service: WorkspaceService = Depends(_get_workspace_service),
    user: CurrentUser = Depends(require_auth),
):
    trace_id = f"trc_{uuid.uuid4().hex[:16]}"
    result = await service.get_document_workspace(doc_id, user, trace_id)
    if result.get("error") == "document_not_found":
        raise not_found("Document not found")
    if result.get("error") == "collection_access_denied":
        raise forbidden("Collection access denied")
    return result


@router.post("/workbench/documents/batch/archive", response_model=BatchDocumentActionResult)
async def batch_archive_documents(
    req: BatchDocumentActionRequest,
    service: WorkspaceService = Depends(_get_workspace_service),
    user: CurrentUser = Depends(_require_document_admin),
):
    admin_client = AdminClient()
    items = []
    action_request = DocumentLifecycleActionRequest(reason=req.reason)
    for doc_id in req.doc_ids:
        items.append(
            await _run_document_action_best_effort(
                doc_id=doc_id,
                action="archive",
                request=action_request,
                user=user,
                workspace_service=service,
                admin_client=admin_client,
            )
        )
    succeeded = sum(1 for item in items if item.success)
    return BatchDocumentActionResult(
        total=len(items),
        succeeded=succeeded,
        failed=len(items) - succeeded,
        items=items,
    )


@router.post("/workbench/documents/batch/retract", response_model=BatchDocumentActionResult)
async def batch_retract_documents(
    req: BatchDocumentActionRequest,
    service: WorkspaceService = Depends(_get_workspace_service),
    user: CurrentUser = Depends(_require_document_admin),
):
    admin_client = AdminClient()
    items = []
    action_request = DocumentLifecycleActionRequest(reason=req.reason)
    for doc_id in req.doc_ids:
        items.append(
            await _run_document_action_best_effort(
                doc_id=doc_id,
                action="retract",
                request=action_request,
                user=user,
                workspace_service=service,
                admin_client=admin_client,
            )
        )
    succeeded = sum(1 for item in items if item.success)
    return BatchDocumentActionResult(
        total=len(items),
        succeeded=succeeded,
        failed=len(items) - succeeded,
        items=items,
    )


@router.post("/workbench/documents/batch/reindex", response_model=BatchDocumentActionResult)
async def batch_reindex_documents(
    req: BatchDocumentActionRequest,
    service: WorkspaceService = Depends(_get_workspace_service),
    user: CurrentUser = Depends(_require_document_admin),
):
    admin_client = AdminClient()
    items = []
    action_request = DocumentLifecycleActionRequest(
        reason=req.reason,
        index_profile_id=req.index_profile_id,
    )
    for doc_id in req.doc_ids:
        items.append(
            await _run_document_action_best_effort(
                doc_id=doc_id,
                action="reindex",
                request=action_request,
                user=user,
                workspace_service=service,
                admin_client=admin_client,
            )
        )
    succeeded = sum(1 for item in items if item.success)
    return BatchDocumentActionResult(
        total=len(items),
        succeeded=succeeded,
        failed=len(items) - succeeded,
        items=items,
    )


@router.post("/workbench/documents/{doc_id}/archive")
async def archive_document(
    doc_id: str,
    req: DocumentLifecycleActionRequest,
    service: WorkspaceService = Depends(_get_workspace_service),
    user: CurrentUser = Depends(_require_document_admin),
):
    return await _run_document_action(
        doc_id=doc_id,
        action="archive",
        request=req,
        user=user,
        workspace_service=service,
        admin_client=AdminClient(),
    )


@router.post("/workbench/documents/{doc_id}/retract")
async def retract_document(
    doc_id: str,
    req: DocumentLifecycleActionRequest,
    service: WorkspaceService = Depends(_get_workspace_service),
    user: CurrentUser = Depends(_require_document_admin),
):
    return await _run_document_action(
        doc_id=doc_id,
        action="retract",
        request=req,
        user=user,
        workspace_service=service,
        admin_client=AdminClient(),
    )


@router.post("/workbench/documents/{doc_id}/reindex")
async def reindex_document(
    doc_id: str,
    req: DocumentLifecycleActionRequest,
    service: WorkspaceService = Depends(_get_workspace_service),
    user: CurrentUser = Depends(_require_document_admin),
):
    return await _run_document_action(
        doc_id=doc_id,
        action="reindex",
        request=req,
        user=user,
        workspace_service=service,
        admin_client=AdminClient(),
    )


@router.post("/workbench/documents/{doc_id}/share", response_model=DocumentShareResponse)
async def share_document(
    doc_id: str,
    req: DocumentShareRequest,
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    import uuid
    from datetime import datetime, timedelta, timezone

    repo = DocumentProjectionRepository(session)
    doc = repo.get(doc_id)
    if doc is None:
        raise not_found("Document not found")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours)
    share_id = f"shr_{uuid.uuid4().hex}"
    share_url = f"http://localhost:8000/share/{share_id}"

    return DocumentShareResponse(
        share_url=share_url,
        expires_at=expires_at.isoformat(),
    )
