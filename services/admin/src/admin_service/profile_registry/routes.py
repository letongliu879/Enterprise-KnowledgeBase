"""Profile registry routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from reality_rag_contracts import ParserProfile, RetrievalProfileAdmin
from reality_rag_contracts.enums import ProfileState

from ..deps import get_db, require_auth, CurrentUser
from ..errors import not_found, forbidden, conflict
from ..downstream_clients.indexing_client import IndexingClient
from ..downstream_clients.retrieval_client import RetrievalClient
from ..downstream_clients.errors import DownstreamError
from ..ops_audit.service import OpsAuditService
from ..ops_audit.repository import OpsAuditRepository
from .service import ProfileRegistryService, ProfilePublishError
from .repository import ProfileRegistryRepository
from .models import (
    ParserProfileCreateRequest,
    ParserProfileUpdateRequest,
    ParserProfileListResponse,
    RetrievalProfileCreateRequest,
    RetrievalProfileUpdateRequest,
    RetrievalProfileListResponse,
    ProfileStateTransitionRequest,
)

router = APIRouter()


def _get_service(session: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> ProfileRegistryService:
    return ProfileRegistryService(ProfileRegistryRepository(session), actor_id=user.user_id)


def _get_audit_service(session: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> OpsAuditService:
    return OpsAuditService(OpsAuditRepository(session), actor_id=user.user_id)


def _require_knowledge_admin(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    if not user.has_role("knowledge_admin") and not user.has_role("platform_admin"):
        raise forbidden("Knowledge admin or platform admin role required")
    return user


# ── Parser Profiles ──────────────────────────────────────────────────────

@router.get("/admin/parser-profiles", response_model=ParserProfileListResponse)
def list_parser_profiles(
    state: str | None = None,
    service: ProfileRegistryService = Depends(_get_service),
):
    items = service.list_parser_profiles(state)
    return ParserProfileListResponse(items=items, total=len(items))


@router.post("/admin/parser-profiles", response_model=ParserProfile)
def create_parser_profile(
    req: ParserProfileCreateRequest,
    service: ProfileRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    return service.create_parser_profile(req)


@router.get("/admin/parser-profiles/{parser_profile_id}")
def get_parser_profile(
    parser_profile_id: str,
    service: ProfileRegistryService = Depends(_get_service),
):
    result = service.get_parser_profile(parser_profile_id)
    if result is None:
        raise not_found(f"Parser profile {parser_profile_id} not found")
    return result


@router.patch("/admin/parser-profiles/{parser_profile_id}")
def update_parser_profile(
    parser_profile_id: str,
    req: ParserProfileUpdateRequest,
    service: ProfileRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    try:
        result = service.update_parser_profile(parser_profile_id, req)
    except ValueError as e:
        raise conflict(str(e))
    if result is None:
        raise not_found(f"Parser profile {parser_profile_id} not found")
    return result


@router.post("/admin/parser-profiles/{parser_profile_id}/publish")
async def publish_parser_profile(
    parser_profile_id: str,
    service: ProfileRegistryService = Depends(_get_service),
    audit_service: OpsAuditService = Depends(_get_audit_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    profile = service.get_parser_profile(parser_profile_id)
    if profile is None:
        raise not_found(f"Parser profile {parser_profile_id} not found")

    # Call downstream validate
    indexing_client = IndexingClient()
    try:
        validate_payload = {
            "parser_profile_id": parser_profile_id,
            "parser_id": profile.parser_id,
            "parser_config": profile.parser_config,
            "tenant_id": user.tenant_id or "default",
        }
        validate_result = await indexing_client.validate_parser_profile(validate_payload)
    except DownstreamError as e:
        audit_service.log_action(
            action="publish",
            target_type="parser_profile",
            target_id=parser_profile_id,
            before_state=profile.state.value if profile.state else "draft",
            after_state="rejected",
            reason=f"{e.code}: {e.message}",
            tenant_id=user.tenant_id or "default",
        )
        raise conflict(f"Profile validation failed: {e.code}: {e.message}")

    # Check validation result
    if not validate_result.get("valid", False):
        errors = validate_result.get("errors", [])
        error_msg = "; ".join(f"{e.get('code')}: {e.get('message')}" for e in errors)
        audit_service.log_action(
            action="publish",
            target_type="parser_profile",
            target_id=parser_profile_id,
            before_state=profile.state.value if profile.state else "draft",
            after_state="rejected",
            reason=f"VALIDATION_FAILED: {error_msg}",
            tenant_id=user.tenant_id or "default",
        )
        raise conflict(f"Profile validation failed: {error_msg}")

    # Publish with validation result
    result = service.publish_parser_profile(parser_profile_id, validate_result=validate_result)
    if result is None:
        raise not_found(f"Parser profile {parser_profile_id} not found")

    audit_service.log_action(
        action="publish",
        target_type="parser_profile",
        target_id=parser_profile_id,
        before_state=profile.state.value if profile.state else "draft",
        after_state="published",
        reason=f"Validated by {validate_result.get('validator_version', 'unknown')}",
        tenant_id=user.tenant_id or "default",
    )
    return result


@router.post("/admin/parser-profiles/{parser_profile_id}/transition")
def transition_parser_state(
    parser_profile_id: str,
    req: ProfileStateTransitionRequest,
    service: ProfileRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    try:
        target = ProfileState(req.target_state)
    except ValueError:
        raise conflict(f"Invalid target state: {req.target_state}")
    result = service.transition_parser_state(parser_profile_id, target)
    if result is None:
        raise not_found(f"Parser profile {parser_profile_id} not found")
    return result


# ── Retrieval Profiles ───────────────────────────────────────────────────

@router.get("/admin/retrieval-profiles", response_model=RetrievalProfileListResponse)
def list_retrieval_profiles(
    state: str | None = None,
    service: ProfileRegistryService = Depends(_get_service),
):
    items = service.list_retrieval_profiles(state)
    return RetrievalProfileListResponse(items=items, total=len(items))


@router.post("/admin/retrieval-profiles", response_model=RetrievalProfileAdmin)
def create_retrieval_profile(
    req: RetrievalProfileCreateRequest,
    service: ProfileRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    return service.create_retrieval_profile(req)


@router.get("/admin/retrieval-profiles/{retrieval_profile_id}")
def get_retrieval_profile(
    retrieval_profile_id: str,
    service: ProfileRegistryService = Depends(_get_service),
):
    result = service.get_retrieval_profile(retrieval_profile_id)
    if result is None:
        raise not_found(f"Retrieval profile {retrieval_profile_id} not found")
    return result


@router.patch("/admin/retrieval-profiles/{retrieval_profile_id}")
def update_retrieval_profile(
    retrieval_profile_id: str,
    req: RetrievalProfileUpdateRequest,
    service: ProfileRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    try:
        result = service.update_retrieval_profile(retrieval_profile_id, req)
    except ValueError as e:
        raise conflict(str(e))
    if result is None:
        raise not_found(f"Retrieval profile {retrieval_profile_id} not found")
    return result


@router.post("/admin/retrieval-profiles/{retrieval_profile_id}/publish")
async def publish_retrieval_profile(
    retrieval_profile_id: str,
    service: ProfileRegistryService = Depends(_get_service),
    audit_service: OpsAuditService = Depends(_get_audit_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    profile = service.get_retrieval_profile(retrieval_profile_id)
    if profile is None:
        raise not_found(f"Retrieval profile {retrieval_profile_id} not found")

    # Call downstream validate
    retrieval_client = RetrievalClient()
    try:
        validate_payload = {
            "retrieval_profile_id": retrieval_profile_id,
            "profile_config": profile.profile_config,
            "tenant_id": user.tenant_id or "default",
        }
        validate_result = await retrieval_client.validate_retrieval_profile(validate_payload)
    except DownstreamError as e:
        audit_service.log_action(
            action="publish",
            target_type="retrieval_profile",
            target_id=retrieval_profile_id,
            before_state=profile.state.value if profile.state else "draft",
            after_state="rejected",
            reason=f"{e.code}: {e.message}",
            tenant_id=user.tenant_id or "default",
        )
        raise conflict(f"Profile validation failed: {e.code}: {e.message}")

    # Check validation result
    if not validate_result.get("valid", False):
        errors = validate_result.get("errors", [])
        error_msg = "; ".join(f"{e.get('code')}: {e.get('message')}" for e in errors)
        audit_service.log_action(
            action="publish",
            target_type="retrieval_profile",
            target_id=retrieval_profile_id,
            before_state=profile.state.value if profile.state else "draft",
            after_state="rejected",
            reason=f"VALIDATION_FAILED: {error_msg}",
            tenant_id=user.tenant_id or "default",
        )
        raise conflict(f"Profile validation failed: {error_msg}")

    # Publish with validation result
    result = service.publish_retrieval_profile(retrieval_profile_id, validate_result=validate_result)
    if result is None:
        raise not_found(f"Retrieval profile {retrieval_profile_id} not found")

    # Sync projection to retrieval runtime
    canonical_config = validate_result.get("canonical_config", {}) or {}
    try:
        sync_payload = {
            "command_id": f"sync_ret_{retrieval_profile_id}",
            "trace_id": f"trc_sync_ret_{retrieval_profile_id}",
            "idempotency_key": f"idem_sync_ret_{retrieval_profile_id}",
            "actor": user.user_id,
            "tenant_id": user.tenant_id or "default",
            "target_type": "retrieval_profile_projection",
            "target_id": retrieval_profile_id,
            "payload": {
                "profile_id": retrieval_profile_id,
                "collection_id": getattr(result, "collection_id", None) or canonical_config.get("collection_id", "") or "",
                "profile_version": result.version or canonical_config.get("profile_version", 1),
                "profile_hash": result.profile_hash or canonical_config.get("profile_hash", ""),
                "bm25_weight": canonical_config.get("bm25_weight", 0.5),
                "vector_weight": canonical_config.get("vector_weight", 0.5),
                "candidate_top_k": canonical_config.get("candidate_top_k", 20),
                "similarity_threshold": canonical_config.get("similarity_threshold", 0.0),
                "rerank_enabled": canonical_config.get("rerank_enabled", True),
                "rerank_model": canonical_config.get("rerank_model", ""),
                "fail_policy": canonical_config.get("fail_policy", "fail_closed"),
                "expansion_policy": canonical_config.get("expansion_policy", {}),
                "pack_budget": canonical_config.get("pack_budget", 1200),
                "enabled": True,
                "updated_by": user.user_id,
            },
        }
        await retrieval_client.sync_retrieval_profile_projection(sync_payload)
    except DownstreamError as e:
        # Log but do not fail publish; retrieval query will fail fast if profile is missing
        audit_service.log_action(
            action="sync_projection",
            target_type="retrieval_profile",
            target_id=retrieval_profile_id,
            before_state="published",
            after_state="sync_failed",
            reason=f"{e.code}: {e.message}",
            tenant_id=user.tenant_id or "default",
        )

    audit_service.log_action(
        action="publish",
        target_type="retrieval_profile",
        target_id=retrieval_profile_id,
        before_state=profile.state.value if profile.state else "draft",
        after_state="published",
        reason=f"Validated by {validate_result.get('validator_version', 'unknown')}",
        tenant_id=user.tenant_id or "default",
    )
    return result


@router.post("/admin/retrieval-profiles/{retrieval_profile_id}/transition")
def transition_retrieval_state(
    retrieval_profile_id: str,
    req: ProfileStateTransitionRequest,
    service: ProfileRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    try:
        target = ProfileState(req.target_state)
    except ValueError:
        raise conflict(f"Invalid target state: {req.target_state}")
    result = service.transition_retrieval_state(retrieval_profile_id, target)
    if result is None:
        raise not_found(f"Retrieval profile {retrieval_profile_id} not found")
    return result
