"""State-transition helpers for event-driven intake job orchestration."""

from __future__ import annotations

from typing import Any

from reality_rag_contracts import (
    AgentReview,
    ConversionStatus,
    IntakeJobState,
    PublishStatus,
    QualityReport,
    StageName,
)
from reality_rag_persistence.models import StageResultModel
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from intake_runtime.orchestrator import OrchestratorService
from intake_runtime.stages.schemas import PublishingStageOutput

from .document_service_client import DocumentServiceClient


def schedule_stage(
    orch: OrchestratorService,
    intake_job_id: str,
    stage_name: StageName,
    idempotency_key: str,
    input_hash: str,
    queued_state: IntakeJobState,
) -> None:
    orch.advance_state(intake_job_id, queued_state)
    orch.find_or_create_stage_task(
        intake_job_id,
        stage_name,
        idempotency_key,
        "v1",
        input_hash,
    )


def apply_approval_decision(
    orch: OrchestratorService,
    intake_job_id: str,
    payload: dict[str, Any],
) -> None:
    decision = payload.get("decision")
    if decision == "approve":
        orch.advance_state(intake_job_id, IntakeJobState.APPROVAL_DECIDED)
        final_doc_id = payload.get("final_doc_id", "") or intake_job_id
        schedule_stage(
            orch,
            intake_job_id,
            StageName.PUBLISHING,
            f"{intake_job_id}:publishing:v1:{final_doc_id}",
            final_doc_id,
            IntakeJobState.PUBLISH_QUEUED,
        )
        return
    if decision == "reject":
        orch.advance_state(intake_job_id, IntakeJobState.REJECTED)
        return
    if decision == "expire":
        orch.advance_state(intake_job_id, IntakeJobState.EXPIRED)
        return
    if decision != "return":
        return

    target_stage = (payload.get("return_target_stage") or "").strip()
    rerun_key = payload.get("ticket_id", intake_job_id)
    if target_stage == StageName.CONVERSION.value:
        schedule_stage(
            orch,
            intake_job_id,
            StageName.CONVERSION,
            f"{intake_job_id}:conversion:return:{rerun_key}",
            f"return:{rerun_key}",
            IntakeJobState.CONVERSION_QUEUED,
        )
    elif target_stage == StageName.AGENT_REVIEW.value:
        schedule_stage(
            orch,
            intake_job_id,
            StageName.AGENT_REVIEW,
            f"{intake_job_id}:agent_review:return:{rerun_key}",
            f"return:{rerun_key}",
            IntakeJobState.REVIEW_QUEUED,
        )


def apply_stage_completed(session, orch: OrchestratorService, job, stage_name: StageName) -> None:
    if stage_name == StageName.CONVERSION:
        _after_conversion(session, orch, job)
        return
    if stage_name == StageName.AGENT_REVIEW:
        _after_review(session, orch, job)
        return
    if stage_name == StageName.PUBLISHING:
        _after_publishing(session, orch, job)
        return


def _after_conversion(session, orch: OrchestratorService, job) -> None:
    row = _stage_result(session, job.intake_job_id, StageName.CONVERSION)
    summary = row.summary_json or {}
    preliminary_doc_id = summary.get("preliminary_doc_id", "")
    if preliminary_doc_id:
        orch.set_preliminary_doc_id(job.intake_job_id, preliminary_doc_id)
    DocumentServiceClient(session).mark_consumed(job.source_file_id, job.intake_job_id)
    input_hash = _source_file_input_hash(session, job.source_file_id, job.object_id)
    schedule_stage(
        orch,
        job.intake_job_id,
        StageName.AGENT_REVIEW,
        f"{job.intake_job_id}:agent_review:v1:{input_hash}",
        input_hash,
        IntakeJobState.REVIEW_QUEUED,
    )


def _after_review(session, orch: OrchestratorService, job) -> None:
    conversion_summary = _stage_result(session, job.intake_job_id, StageName.CONVERSION).summary_json or {}
    review_summary = _stage_result(session, job.intake_job_id, StageName.AGENT_REVIEW).summary_json or {}
    quality_report = (
        QualityReport.model_validate(conversion_summary["quality_report"])
        if conversion_summary.get("quality_report") is not None
        else None
    )
    agent_review = _normalize_agent_review(
        review_summary.get("agent_review"),
        conversion_summary.get("preliminary_doc_id", job.preliminary_doc_id or ""),
    )
    publish_status = _resolve_publish_status(quality_report, agent_review)
    orch.advance_state(job.intake_job_id, IntakeJobState.APPROVAL_REQUESTED)
    orch.request_approval(
        intake_job_id=job.intake_job_id,
        preliminary_doc_id=conversion_summary.get("preliminary_doc_id", job.preliminary_doc_id or ""),
        collection_id=job.collection_id,
        publish_status=(publish_status.value if publish_status is not None else None),
        logical_document_id=conversion_summary.get("logical_document_id", ""),
        version=conversion_summary.get("version", 1),
        confirmed_tags=(agent_review.risk_tags if agent_review is not None else []),
        rejection_reason=(
            agent_review.reasons[0]
            if agent_review is not None and agent_review.reasons
            else "System decision"
        ),
        routing_recommendation=(
            "auto_approve" if publish_status == PublishStatus.PUBLISHED else "require_approval"
        ),
    )


def _after_publishing(session, orch: OrchestratorService, job) -> None:
    from reality_rag_contracts import CanonicalMetadata, IndexAssetBundle

    row = _stage_result(session, job.intake_job_id, StageName.PUBLISHING)
    summary = row.summary_json or {}
    output = PublishingStageOutput(
        schema_version=summary.get("schema_version", "v1"),
        input_hash=summary.get("input_hash", ""),
        result_hash=summary.get("result_hash", ""),
        asset_paths=summary.get("asset_paths", {}) or {},
        asset_bundle=(
            IndexAssetBundle.model_validate(summary.get("asset_bundle"))
            if isinstance(summary.get("asset_bundle"), dict)
            else summary.get("asset_bundle")
        ),
        canonical_metadata=(
            CanonicalMetadata.model_validate(summary.get("canonical_metadata"))
            if isinstance(summary.get("canonical_metadata"), dict)
            else summary.get("canonical_metadata")
        ),
        document_persisted=bool(summary.get("document_persisted")),
        policy_persisted=bool(summary.get("policy_persisted")),
    )
    final_doc_id = job.final_doc_id or (
        output.canonical_metadata.doc_id if output.canonical_metadata is not None else ""
    )
    if final_doc_id:
        orch.publish_completed(
            intake_job_id=job.intake_job_id,
            final_doc_id=final_doc_id,
            collection_id=job.collection_id,
            chunk_count=(len(output.asset_bundle.chunks) if output.asset_bundle is not None else 0),
            index_version=(
                output.canonical_metadata.asset_paths.get("index_version", "v1")
                if output.canonical_metadata is not None
                else "v1"
            ),
        )
    DocumentServiceClient(session).mark_cleanable(job.source_file_id, job.intake_job_id)


def _stage_result(session, intake_job_id: str, stage_name: StageName) -> StageResultModel:
    row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == intake_job_id)
        .filter(StageResultModel.stage_name == stage_name.value)
        .first()
    )
    if row is None or not row.summary_json:
        raise ValueError(f"Missing {stage_name.value} summary for intake job {intake_job_id}")
    return row


def _source_file_input_hash(session, source_file_id: str, fallback: str) -> str:
    source_file = SourceFileRepository(session).get(source_file_id)
    if source_file is None:
        return fallback
    return source_file.content_hash or fallback


def _resolve_publish_status(
    quality_report: QualityReport | None,
    agent_review: AgentReview | None,
) -> PublishStatus | None:
    from .domains.approval_domain import system_decide

    if quality_report is None and agent_review is None:
        return None
    return system_decide(quality_report, agent_review)


def _normalize_agent_review(value: Any, doc_id: str) -> AgentReview | None:
    if value is None:
        return None
    if isinstance(value, AgentReview):
        return value
    if isinstance(value, dict):
        try:
            return AgentReview.model_validate({"doc_id": doc_id, **value})
        except Exception:
            return AgentReview(
                doc_id=doc_id,
                reasons=value.get("reasons", []),
                risk_tags=value.get("risk_tags", []),
                publish_recommendation=value.get("publish_recommendation"),
                decision=value.get("decision"),
            )
    return AgentReview(
        doc_id=doc_id,
        reasons=getattr(value, "reasons", []) or [],
        risk_tags=getattr(value, "risk_tags", []) or [],
        publish_recommendation=getattr(value, "publish_recommendation", None),
        decision=getattr(value, "decision", None),
    )
