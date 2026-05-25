"""Telemetry storage for production observability.

Provides TelemetryStore for writing telemetry_events, llm_call_log,
review_quality_feedback, and llm_cost_daily.

All write operations are best-effort: failures are logged but do not
block the main ingestion pipeline.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from reality_rag_contracts import (
    LLMCallLog,
    LLMCostDaily,
    ReviewQualityFeedback,
    TelemetryEvent,
)

from .models import (
    LLMCallLogModel,
    LLMCostDailyModel,
    ReviewQualityFeedbackModel,
    TelemetryEventModel,
)

logger = logging.getLogger(__name__)

# Fields that must never enter telemetry attributes
_SENSITIVE_KEYS = {
    "canonical_md",
    "canonical_content",
    "sanitized_md",
    "sanitized_content",
    "prompt",
    "prompt_text",
    "response",
    "response_text",
    "content",
    "body",
    "source_bytes",
    "password",
    "api_key",
    "token",
    "secret",
    "authorization",
    "cookie",
    "session_id",
    "presigned_url",
    "original_pii",
    "pii_value",
}


def _sanitize_attributes(attrs: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive keys from telemetry attributes.

    Also truncates string values > 1KB to prevent accidental leakage.
    """
    sanitized: dict[str, Any] = {}
    for key, value in attrs.items():
        if key.lower() in _SENSITIVE_KEYS:
            continue
        if isinstance(value, str):
            if len(value) > 1024:
                sanitized[key] = value[:1024]
            else:
                sanitized[key] = value
        elif isinstance(value, (int, float, bool, type(None))):
            sanitized[key] = value
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_attributes(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize_attributes(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = str(value)
    return sanitized


def _json_hash(value: dict[str, Any]) -> str:
    """Deterministic SHA-256 hash of a JSON-serializable dict."""
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TelemetryStore:
    """Best-effort telemetry persistence.

    All methods accept an optional ``session``.  When ``session`` is None,
    the store creates a short-lived session from ``session_factory``.
    Write failures are logged but never raised.
    """

    def __init__(self, session_factory: Any | None = None) -> None:
        self._session_factory = session_factory

    def _get_session(self, session: Session | None) -> Session | None:
        if session is not None:
            return session
        if self._session_factory is not None:
            try:
                return self._session_factory()
            except Exception:
                logger.exception("telemetry: failed to create session")
        return None

    def emit_event(
        self,
        event: TelemetryEvent,
        *,
        session: Session | None = None,
    ) -> None:
        """Persist a telemetry event."""
        db_session = self._get_session(session)
        if db_session is None:
            return
        try:
            sanitized_attrs = _sanitize_attributes(event.attributes_json)
            row = TelemetryEventModel(
                event_id=event.event_id,
                event_name=event.event_name,
                event_time=event.event_time,
                schema_version=event.schema_version,
                trace_id=event.trace_id,
                intake_job_id=event.intake_job_id,
                source_file_id=event.source_file_id,
                collection_id=event.collection_id,
                visibility=event.visibility,
                stage_name=event.stage_name,
                stage_task_id=event.stage_task_id,
                ticket_id=event.ticket_id,
                final_doc_id=event.final_doc_id,
                component=event.component,
                component_version=event.component_version,
                status=event.status,
                duration_ms=event.duration_ms,
                error_code=event.error_code,
                retry_count=event.retry_count,
                attributes_json=sanitized_attrs,
            )
            db_session.add(row)
            if session is None:
                db_session.commit()
        except Exception:
            logger.exception("telemetry: failed to emit event %s", event.event_id)
            if session is None and db_session is not None:
                db_session.rollback()

    def log_llm_call(
        self,
        log: LLMCallLog,
        *,
        session: Session | None = None,
    ) -> None:
        """Persist an LLM call log entry."""
        db_session = self._get_session(session)
        if db_session is None:
            return
        try:
            row = LLMCallLogModel(
                llm_call_id=log.llm_call_id,
                trace_id=log.trace_id,
                intake_job_id=log.intake_job_id,
                stage_task_id=log.stage_task_id,
                review_id=log.review_id,
                provider=log.provider,
                model_name=log.model_name,
                model_version=log.model_version,
                prompt_version=log.prompt_version,
                policy_version=log.policy_version,
                request_hash=log.request_hash,
                response_hash=log.response_hash,
                input_token_count=log.input_token_count,
                output_token_count=log.output_token_count,
                total_token_count=log.total_token_count,
                latency_ms=log.latency_ms,
                timeout_ms=log.timeout_ms,
                status=log.status,
                error_code=log.error_code,
                retry_count=log.retry_count,
                json_parse_success=log.json_parse_success,
                schema_validation_success=log.schema_validation_success,
                redaction_before_send=log.redaction_before_send,
                external_model_used=log.external_model_used,
                created_at=log.created_at,
            )
            db_session.add(row)
            if session is None:
                db_session.commit()
        except Exception:
            logger.exception("telemetry: failed to log LLM call %s", log.llm_call_id)
            if session is None and db_session is not None:
                db_session.rollback()

    def record_review_feedback(
        self,
        feedback: ReviewQualityFeedback,
        *,
        session: Session | None = None,
    ) -> None:
        """Persist review quality feedback."""
        db_session = self._get_session(session)
        if db_session is None:
            return
        try:
            row = ReviewQualityFeedbackModel(
                feedback_id=feedback.feedback_id,
                review_id=feedback.review_id,
                intake_job_id=feedback.intake_job_id,
                ticket_id=feedback.ticket_id,
                collection_id=feedback.collection_id,
                visibility=feedback.visibility,
                model_name=feedback.model_name,
                model_version=feedback.model_version,
                prompt_version=feedback.prompt_version,
                routing_recommendation=feedback.routing_recommendation,
                review_status=feedback.review_status,
                pii_count_by_type=feedback.pii_count_by_type,
                pii_count_by_severity=feedback.pii_count_by_severity,
                visibility_conflict=feedback.visibility_conflict,
                visibility_conflict_type=feedback.visibility_conflict_type,
                approval_decision=feedback.approval_decision,
                auto_approved=feedback.auto_approved,
                manual_override=feedback.manual_override,
                return_target_stage=feedback.return_target_stage,
                return_reason_code=feedback.return_reason_code,
                approver_changed_tags=feedback.approver_changed_tags,
                approved_after_review_failure=feedback.approved_after_review_failure,
                created_at=feedback.created_at,
            )
            db_session.add(row)
            if session is None:
                db_session.commit()
        except Exception:
            logger.exception(
                "telemetry: failed to record review feedback %s", feedback.feedback_id
            )
            if session is None and db_session is not None:
                db_session.rollback()

    def upsert_cost_daily(
        self,
        cost: LLMCostDaily,
        *,
        session: Session | None = None,
    ) -> None:
        """Upsert a daily LLM cost aggregate.

        If a row already exists for the (date, provider, model_name, ...)
        composite key, the values are accumulated.
        """
        db_session = self._get_session(session)
        if db_session is None:
            return
        try:
            existing = (
                db_session.query(LLMCostDailyModel)
                .filter_by(
                    date=cost.date,
                    provider=cost.provider,
                    model_name=cost.model_name,
                    model_version=cost.model_version,
                    prompt_version=cost.prompt_version,
                    collection_id=cost.collection_id,
                    visibility=cost.visibility,
                )
                .first()
            )
            if existing is not None:
                existing.call_count += cost.call_count
                existing.success_count += cost.success_count
                existing.failure_count += cost.failure_count
                existing.input_tokens += cost.input_tokens
                existing.output_tokens += cost.output_tokens
                if cost.estimated_cost is not None:
                    existing.estimated_cost = (existing.estimated_cost or 0.0) + cost.estimated_cost
                if cost.avg_latency_ms is not None:
                    existing.avg_latency_ms = cost.avg_latency_ms
                if cost.p95_latency_ms is not None:
                    existing.p95_latency_ms = cost.p95_latency_ms
            else:
                row = LLMCostDailyModel(
                    date=cost.date,
                    provider=cost.provider,
                    model_name=cost.model_name,
                    model_version=cost.model_version,
                    prompt_version=cost.prompt_version,
                    collection_id=cost.collection_id,
                    visibility=cost.visibility,
                    call_count=cost.call_count,
                    success_count=cost.success_count,
                    failure_count=cost.failure_count,
                    input_tokens=cost.input_tokens,
                    output_tokens=cost.output_tokens,
                    estimated_cost=cost.estimated_cost,
                    avg_latency_ms=cost.avg_latency_ms,
                    p95_latency_ms=cost.p95_latency_ms,
                )
                db_session.add(row)
            if session is None:
                db_session.commit()
        except Exception:
            logger.exception("telemetry: failed to upsert cost daily %s", cost.date)
            if session is None and db_session is not None:
                db_session.rollback()

    def aggregate_llm_cost_daily(
        self,
        date: str,
        *,
        session: Session | None = None,
    ) -> list[LLMCostDaily]:
        """Aggregate llm_call_log entries for a specific date into llm_cost_daily rows.

        Returns the upserted rows so callers can inspect the result.
        """
        from sqlalchemy import func

        db_session = self._get_session(session)
        if db_session is None:
            return []

        try:
            results = (
                db_session.query(
                    LLMCallLogModel.provider,
                    LLMCallLogModel.model_name,
                    LLMCallLogModel.model_version,
                    LLMCallLogModel.prompt_version,
                    LLMCallLogModel.collection_id,
                    LLMCallLogModel.visibility,
                    func.count().label("call_count"),
                    func.sum(func.case((LLMCallLogModel.status == "succeeded", 1), else_=0)).label("success_count"),
                    func.sum(func.case((LLMCallLogModel.status != "succeeded", 1), else_=0)).label("failure_count"),
                    func.sum(LLMCallLogModel.input_token_count).label("input_tokens"),
                    func.sum(LLMCallLogModel.output_token_count).label("output_tokens"),
                    func.avg(LLMCallLogModel.latency_ms).label("avg_latency"),
                )
                .filter(func.date(LLMCallLogModel.created_at) == date)
                .group_by(
                    LLMCallLogModel.provider,
                    LLMCallLogModel.model_name,
                    LLMCallLogModel.model_version,
                    LLMCallLogModel.prompt_version,
                    LLMCallLogModel.collection_id,
                    LLMCallLogModel.visibility,
                )
                .all()
            )

            upserted: list[LLMCostDaily] = []
            for row in results:
                cost = LLMCostDaily(
                    date=date,
                    provider=row.provider or "unknown",
                    model_name=row.model_name or "unknown",
                    model_version=row.model_version or "unknown",
                    prompt_version=row.prompt_version or "unknown",
                    collection_id=row.collection_id or "unknown",
                    visibility=row.visibility or "INTERNAL",
                    call_count=row.call_count or 0,
                    success_count=row.success_count or 0,
                    failure_count=row.failure_count or 0,
                    input_tokens=int(row.input_tokens or 0),
                    output_tokens=int(row.output_tokens or 0),
                    avg_latency_ms=int(row.avg_latency or 0) if row.avg_latency else None,
                )
                self.upsert_cost_daily(cost, session=db_session)
                upserted.append(cost)

            if session is None:
                db_session.commit()
            return upserted
        except Exception:
            logger.exception("telemetry: failed to aggregate cost daily for %s", date)
            if session is None and db_session is not None:
                db_session.rollback()
            return []

    def get_llm_cost_daily(
        self,
        date: str | None = None,
        *,
        session: Session | None = None,
    ) -> list[LLMCostDaily]:
        """Query llm_cost_daily rows. If date is None, returns all rows."""
        db_session = self._get_session(session)
        if db_session is None:
            return []

        try:
            query = db_session.query(LLMCostDailyModel)
            if date:
                query = query.filter_by(date=date)
            rows = query.all()
            return [
                LLMCostDaily(
                    date=r.date,
                    provider=r.provider,
                    model_name=r.model_name,
                    model_version=r.model_version,
                    prompt_version=r.prompt_version,
                    collection_id=r.collection_id,
                    visibility=r.visibility,
                    call_count=r.call_count,
                    success_count=r.success_count,
                    failure_count=r.failure_count,
                    input_tokens=r.input_tokens,
                    output_tokens=r.output_tokens,
                    estimated_cost=r.estimated_cost,
                    avg_latency_ms=r.avg_latency_ms,
                    p95_latency_ms=r.p95_latency_ms,
                )
                for r in rows
            ]
        except Exception:
            logger.exception("telemetry: failed to query cost daily")
            return []
