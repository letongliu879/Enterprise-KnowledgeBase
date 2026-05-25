"""Shared runtime helpers for event-driven stage execution."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from reality_rag_contracts import (
    AgentReview,
    ConversionResult,
    ConversionStatus,
    IntakeJobState,
    PublishStatus,
    QualityReport,
    ReviewDecision,
    StageName,
    StageTaskState,
)
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.document_policies import DocumentPolicyRepository
from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from reality_rag_persistence.repositories.stage_tasks import StageTaskRepository
from reality_rag_persistence.repositories.tenants import TenantRepository

from .domains.lease_service import StageTaskLeaseService
from .orchestrator import OrchestratorService
from .stages import StageContext
from .stages.adapters import (
    conversion_output_to_ctx,
    ctx_to_conversion_input,
    ctx_to_conversion_output,
    ctx_to_publishing_input,
    ctx_to_publishing_output,
    ctx_to_review_input,
    ctx_to_review_output,
    publishing_output_to_ctx,
    review_output_to_ctx,
)
from .stages.pure_stages import _logical_document_id, run_conversion_stage, run_publishing_stage, run_review_stage


def json_summary(payload: Any) -> dict[str, Any]:
    safe = _json_safe(payload)
    if isinstance(safe, dict):
        return safe
    return json.loads(json.dumps(safe, default=str))


def build_stage_context(session, intake_job_id: str) -> tuple[Any, Any, Any, Any, Any, StageContext]:
    job = IntakeJobRepository(session).get(intake_job_id)
    if job is None:
        raise ValueError(f"Intake job not found: {intake_job_id}")

    source_file = SourceFileRepository(session).get(job.source_file_id)
    if source_file is None:
        raise ValueError(f"Source file not found: {job.source_file_id}")

    obj = ObjectBlobRepository(session).get(job.object_id)
    if obj is None:
        raise ValueError(f"Object blob not found: {job.object_id}")

    collection = CollectionRepository(session).get(job.collection_id)
    tenant = TenantRepository(session).get("default")
    document_repo = DocumentRepository(session)
    policy_repo = DocumentPolicyRepository(session)

    ctx = StageContext(
        collection_id=job.collection_id,
        source_file_path=obj.storage_key,
        collection=collection,
        tenant=tenant,
        job_id=job.trace_id or intake_job_id,
        intake_job_id=intake_job_id,
        source_file_id=job.source_file_id,
        object_id=job.object_id,
        content_hash=source_file.content_hash,
        source_hash=source_file.content_hash,
        session=session,
        document_repo=document_repo,
        policy_repo=policy_repo,
        index_version="v1",
    )
    if job.preliminary_doc_id:
        ctx.doc_id = job.preliminary_doc_id
    return job, source_file, obj, document_repo, policy_repo, ctx


def start_stage(session, intake_job_id: str, stage_name: StageName, input_hash: str) -> tuple[Any, Any] | tuple[None, None]:
    if not intake_job_id or session is None:
        return None, None
    try:
        orch = OrchestratorService(session)
        idempotency_key = f"{intake_job_id}:{stage_name.value}:v1:{input_hash}"
        existing = orch.check_existing_result(idempotency_key)
        if existing is not None:
            return None, None
        task, _ = orch.find_or_create_stage_task(
            intake_job_id,
            stage_name,
            idempotency_key,
            "v1",
            input_hash,
        )
        worker_id = "worker-ingestion-stage-runtime"
        leased = orch.acquire_lease(task.stage_task_id, worker_id, lease_seconds=300)
        if not leased:
            return None, None
        attempt = orch.start_stage_attempt(task.stage_task_id, intake_job_id, stage_name)
        orch.advance_state(intake_job_id, _running_state(stage_name), stage_name.value)
        return task, attempt
    except Exception:
        return None, None


def _start_existing_stage(
    session,
    stage_task_id: str,
    intake_job_id: str,
    stage_name: StageName,
    worker_id: str,
) -> tuple[Any, Any, bool]:
    task = StageTaskRepository(session).get(stage_task_id)
    if task is None:
        raise ValueError(f"Stage task not found: {stage_task_id}")
    if task.intake_job_id != intake_job_id:
        raise ValueError(f"Stage task {stage_task_id} does not belong to intake job {intake_job_id}")
    if task.stage_name != stage_name.value:
        raise ValueError(f"Stage task {stage_task_id} is not {stage_name.value}")

    lease_service = StageTaskLeaseService(session)
    if not lease_service.acquire_lease(stage_task_id, worker_id, ttl_seconds=300):
        refreshed = StageTaskRepository(session).get(stage_task_id)
        if refreshed is not None and refreshed.state == StageTaskState.SUCCEEDED.value:
            return refreshed, None, True
        return None, None, True

    orch = OrchestratorService(session)
    attempt = orch.start_stage_attempt(
        stage_task_id,
        intake_job_id,
        stage_name,
        worker_id=worker_id,
    )
    orch.advance_state(intake_job_id, _running_state(stage_name), stage_name.value)
    refreshed = StageTaskRepository(session).get(stage_task_id) or task
    return refreshed, attempt, True


def finish_stage(
    session,
    intake_job_id: str,
    task,
    attempt,
    *,
    success: bool,
    stage_name: StageName,
    result_hash: str | None = None,
    summary_json: dict[str, Any] | None = None,
    error_code: str | None = None,
    fail_reason: str = "",
) -> None:
    if not intake_job_id or session is None or task is None or attempt is None:
        return
    try:
        orch = OrchestratorService(session)
        orch.complete_stage_attempt(attempt.stage_attempt_id, success, error_code)
        if success:
            orch.update_task_state(task.stage_task_id, StageTaskState.SUCCEEDED)
            if result_hash is not None:
                orch.record_stage_result(
                    task.stage_task_id,
                    attempt.stage_attempt_id,
                    intake_job_id,
                    stage_name,
                    task.idempotency_key,
                    result_hash,
                    summary_json=summary_json,
                )
        else:
            orch.update_task_state(task.stage_task_id, StageTaskState.FAILED)
            orch.fail_intake_job(intake_job_id, fail_reason or error_code or "Stage failed")
    finally:
        try:
            OrchestratorService(session).release_lease(task.stage_task_id)
        except Exception:
            pass


def run_conversion(session, intake_job_id: str, pipeline) -> None:
    job, source_file, _, document_repo, _, ctx = build_stage_context(session, intake_job_id)
    task, attempt = start_stage(session, intake_job_id, StageName.CONVERSION, source_file.content_hash)
    if task is None or attempt is None:
        return
    _run_conversion_core(session, job, source_file, document_repo, ctx, task, attempt, pipeline)


def execute_conversion_task(
    session,
    stage_task_id: str,
    intake_job_id: str,
    pipeline,
    worker_id: str,
) -> bool:
    job, source_file, _, document_repo, _, ctx = build_stage_context(session, intake_job_id)
    task, attempt, should_ack = _start_existing_stage(
        session,
        stage_task_id,
        intake_job_id,
        StageName.CONVERSION,
        worker_id,
    )
    if attempt is None:
        return should_ack
    _run_conversion_core(session, job, source_file, document_repo, ctx, task, attempt, pipeline)
    return True


def _run_conversion_core(session, job, source_file, document_repo, ctx, task, attempt, pipeline) -> None:

    conv_inp = ctx_to_conversion_input(ctx)
    latest_version = None
    logical_doc_id = _logical_document_id(ctx.source_file_path)
    latest = document_repo.get_latest_by_logical_id(logical_doc_id, ctx.collection_id)
    if latest is not None:
        latest_version = latest.version
    conv_out = run_conversion_stage(
        conv_inp,
        pipeline._converters,
        existing_published_doc_id=None,
        latest_version=latest_version,
    )
    ctx = conversion_output_to_ctx(conv_out, ctx)
    summary = json_summary(asdict(ctx_to_conversion_output(ctx)))
    success = (
        conv_out.conversion_result is not None
        and conv_out.conversion_result.conversion_status == ConversionStatus.SUCCESS
    )
    finish_stage(
        session,
        job.intake_job_id,
        task,
        attempt,
        success=success,
        stage_name=StageName.CONVERSION,
        result_hash=(conv_out.result_hash if success else None),
        summary_json=summary,
        error_code=(None if success else "conversion_failed"),
        fail_reason=(
            conv_out.conversion_result.error_message
            if conv_out.conversion_result is not None
            else "Conversion failed"
        ),
    )
    OrchestratorService(session).publish_stage_completed(
        intake_job_id=job.intake_job_id,
        stage_task_id=task.stage_task_id,
        stage_attempt_id=attempt.stage_attempt_id,
        stage_name=StageName.CONVERSION,
        success=success,
        trace_id=job.trace_id,
        error_code=(None if success else "conversion_failed"),
        error_message=(
            conv_out.conversion_result.error_message
            if conv_out.conversion_result is not None
            else "Conversion failed"
        ),
    )


def run_review(session, intake_job_id: str, pipeline) -> None:
    from reality_rag_persistence.models import StageResultModel

    job, source_file, _, _, _, ctx = build_stage_context(session, intake_job_id)
    conv_row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == job.intake_job_id)
        .filter(StageResultModel.stage_name == StageName.CONVERSION.value)
        .first()
    )
    if conv_row is None:
        raise ValueError(f"Missing conversion result for intake job {job.intake_job_id}")

    task, attempt = start_stage(session, intake_job_id, StageName.AGENT_REVIEW, source_file.content_hash)
    if task is None or attempt is None:
        return
    _run_review_core(session, job, source_file, ctx, task, attempt, pipeline, conv_row)


def execute_review_task(
    session,
    stage_task_id: str,
    intake_job_id: str,
    pipeline,
    worker_id: str,
) -> bool:
    from reality_rag_persistence.models import StageResultModel

    job, source_file, _, _, _, ctx = build_stage_context(session, intake_job_id)
    conv_row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == job.intake_job_id)
        .filter(StageResultModel.stage_name == StageName.CONVERSION.value)
        .first()
    )
    if conv_row is None:
        raise ValueError(f"Missing conversion result for intake job {job.intake_job_id}")

    task, attempt, should_ack = _start_existing_stage(
        session,
        stage_task_id,
        intake_job_id,
        StageName.AGENT_REVIEW,
        worker_id,
    )
    if attempt is None:
        return should_ack
    _run_review_core(session, job, source_file, ctx, task, attempt, pipeline, conv_row)
    return True


def _run_review_core(session, job, source_file, ctx, task, attempt, pipeline, conv_row) -> None:

    conversion_summary = conv_row.summary_json or {}
    ctx.doc_id = conversion_summary.get("preliminary_doc_id", job.preliminary_doc_id or "")
    ctx.logical_document_id = conversion_summary.get("logical_document_id", "")
    ctx.version = conversion_summary.get("version", 1)
    if conversion_summary.get("conversion_result") is not None:
        ctx.result = ConversionResult.model_validate(conversion_summary["conversion_result"])
    if conversion_summary.get("quality_report") is not None:
        ctx.quality_report = QualityReport.model_validate(conversion_summary["quality_report"])

    review_inp = ctx_to_review_input(ctx)
    review_out = run_review_stage(
        review_inp,
        pipeline._agent_reviewer,
        pipeline._agent_review_cache,
    )
    ctx = review_output_to_ctx(review_out, ctx)
    ctx.agent_review = normalize_agent_review(ctx.agent_review, ctx.doc_id)
    summary = json_summary(asdict(ctx_to_review_output(ctx)))
    finish_stage(
        session,
        job.intake_job_id,
        task,
        attempt,
        success=True,
        stage_name=StageName.AGENT_REVIEW,
        result_hash=review_out.result_hash,
        summary_json=summary,
    )
    OrchestratorService(session).publish_stage_completed(
        intake_job_id=job.intake_job_id,
        stage_task_id=task.stage_task_id,
        stage_attempt_id=attempt.stage_attempt_id,
        stage_name=StageName.AGENT_REVIEW,
        success=True,
        trace_id=job.trace_id,
    )


def run_publishing(session, intake_job_id: str) -> None:
    from reality_rag_persistence.models import StageResultModel

    job, source_file, _, document_repo, policy_repo, ctx = build_stage_context(session, intake_job_id)
    conv_row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == intake_job_id)
        .filter(StageResultModel.stage_name == StageName.CONVERSION.value)
        .first()
    )
    review_row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == intake_job_id)
        .filter(StageResultModel.stage_name == StageName.AGENT_REVIEW.value)
        .first()
    )
    if conv_row is None or review_row is None:
        raise ValueError(f"Missing stage result(s) for intake job {intake_job_id}")

    conv_summary = conv_row.summary_json or {}
    review_summary = review_row.summary_json or {}
    ctx.doc_id = conv_summary.get("preliminary_doc_id", job.preliminary_doc_id or "")
    ctx.logical_document_id = conv_summary.get("logical_document_id", "")
    ctx.version = conv_summary.get("version", 1)
    if conv_summary.get("conversion_result") is not None:
        ctx.result = ConversionResult.model_validate(conv_summary["conversion_result"])
    if conv_summary.get("quality_report") is not None:
        ctx.quality_report = QualityReport.model_validate(conv_summary["quality_report"])
    if review_summary.get("agent_review") is not None:
        ctx.agent_review = normalize_agent_review(review_summary["agent_review"], ctx.doc_id)
    ctx.review_context = review_summary.get("review_context", {})
    ctx.final_doc_id = job.final_doc_id or ""
    if not ctx.final_doc_id:
        raise ValueError(f"Missing final_doc_id for publishing intake job {intake_job_id}")
    ctx.publish_status = PublishStatus.PUBLISHED

    task, attempt = start_stage(session, intake_job_id, StageName.PUBLISHING, ctx.final_doc_id)
    if task is None or attempt is None:
        return
    _run_publishing_core(session, job, document_repo, policy_repo, ctx, task, attempt)


def execute_publishing_task(
    session,
    stage_task_id: str,
    intake_job_id: str,
    worker_id: str,
) -> bool:
    from reality_rag_persistence.models import StageResultModel

    job, _, _, document_repo, policy_repo, ctx = build_stage_context(session, intake_job_id)
    conv_row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == intake_job_id)
        .filter(StageResultModel.stage_name == StageName.CONVERSION.value)
        .first()
    )
    review_row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == intake_job_id)
        .filter(StageResultModel.stage_name == StageName.AGENT_REVIEW.value)
        .first()
    )
    if conv_row is None or review_row is None:
        raise ValueError(f"Missing stage result(s) for intake job {intake_job_id}")

    conv_summary = conv_row.summary_json or {}
    review_summary = review_row.summary_json or {}
    ctx.doc_id = conv_summary.get("preliminary_doc_id", job.preliminary_doc_id or "")
    ctx.logical_document_id = conv_summary.get("logical_document_id", "")
    ctx.version = conv_summary.get("version", 1)
    if conv_summary.get("conversion_result") is not None:
        ctx.result = ConversionResult.model_validate(conv_summary["conversion_result"])
    if conv_summary.get("quality_report") is not None:
        ctx.quality_report = QualityReport.model_validate(conv_summary["quality_report"])
    if review_summary.get("agent_review") is not None:
        ctx.agent_review = normalize_agent_review(review_summary["agent_review"], ctx.doc_id)
    ctx.review_context = review_summary.get("review_context", {})
    ctx.final_doc_id = job.final_doc_id or ""
    if not ctx.final_doc_id:
        raise ValueError(f"Missing final_doc_id for publishing intake job {intake_job_id}")
    ctx.publish_status = PublishStatus.PUBLISHED

    task, attempt, should_ack = _start_existing_stage(
        session,
        stage_task_id,
        intake_job_id,
        StageName.PUBLISHING,
        worker_id,
    )
    if attempt is None:
        return should_ack
    _run_publishing_core(session, job, document_repo, policy_repo, ctx, task, attempt)
    return True


def _run_publishing_core(session, job, document_repo, policy_repo, ctx, task, attempt) -> None:

    pub_inp = ctx_to_publishing_input(ctx)
    pub_out = run_publishing_stage(
        pub_inp,
        document_repo=document_repo,
        policy_repo=policy_repo,
    )
    ctx = publishing_output_to_ctx(pub_out, ctx)
    finish_stage(
        session,
        job.intake_job_id,
        task,
        attempt,
        success=True,
        stage_name=StageName.PUBLISHING,
        result_hash=pub_out.result_hash,
        summary_json=json_summary(asdict(ctx_to_publishing_output(ctx))),
    )
    OrchestratorService(session).publish_stage_completed(
        intake_job_id=job.intake_job_id,
        stage_task_id=task.stage_task_id,
        stage_attempt_id=attempt.stage_attempt_id,
        stage_name=StageName.PUBLISHING,
        success=True,
        trace_id=job.trace_id,
    )


def normalize_agent_review(value: Any, doc_id: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return AgentReview.model_validate({"doc_id": doc_id, **value})
    if isinstance(value, AgentReview):
        return value

    def _scalar_str(attr: str, default: str = "") -> str:
        candidate = getattr(value, attr, default)
        return candidate if isinstance(candidate, str) else default

    def _scalar_float(attr: str, default: float = 0.0) -> float:
        candidate = getattr(value, attr, default)
        return float(candidate) if isinstance(candidate, (int, float)) else default

    def _scalar_int(attr: str, default: int = 0) -> int:
        candidate = getattr(value, attr, default)
        return int(candidate) if isinstance(candidate, int) else default

    def _list_attr(attr: str) -> list[Any]:
        candidate = getattr(value, attr, [])
        return list(candidate) if isinstance(candidate, list) else []

    decision = getattr(value, "decision", None)
    if not isinstance(decision, (str, ReviewDecision)) and decision is not None:
        decision = None

    publish_recommendation = getattr(value, "publish_recommendation", None)
    if not isinstance(publish_recommendation, (str, PublishStatus)) and publish_recommendation is not None:
        publish_recommendation = None

    return AgentReview(
        doc_id=_scalar_str("doc_id", doc_id) or doc_id,
        decision=decision,
        confidence=_scalar_float("confidence", 0.0),
        reasons=_list_attr("reasons"),
        risk_tags=_list_attr("risk_tags"),
        suggested_actions=_list_attr("suggested_actions"),
        publish_recommendation=publish_recommendation,
        sections_requiring_review=_list_attr("sections_requiring_review"),
        document_type=_scalar_str("document_type", ""),
        suggested_authority_level=_scalar_int("suggested_authority_level", 0),
        detected_pii=_list_attr("detected_pii"),
        diff_summary=_scalar_str("diff_summary", ""),
    )


def _running_state(stage_name: StageName) -> IntakeJobState:
    if stage_name == StageName.CONVERSION:
        return IntakeJobState.CONVERSION_RUNNING
    if stage_name == StageName.AGENT_REVIEW:
        return IntakeJobState.REVIEW_RUNNING
    if stage_name == StageName.PUBLISHING:
        return IntakeJobState.PUBLISH_RUNNING
    raise ValueError(f"Unsupported stage: {stage_name.value}")


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if hasattr(value, "value"):
        return value.value
    return value
