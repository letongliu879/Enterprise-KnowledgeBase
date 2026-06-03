"""Compatibility wrappers for shared intake runtime stage execution."""

from __future__ import annotations

from intake_runtime import stage_runtime as _shared
from ingestion_worker.domains.publishing_domain import persist_document_and_policy

json_summary = _shared.json_summary
build_stage_context = _shared.build_stage_context
start_stage = _shared.start_stage
finish_stage = _shared.finish_stage
run_conversion = _shared.run_conversion
execute_conversion_task = _shared.execute_conversion_task
run_review = _shared.run_review
execute_review_task = _shared.execute_review_task
normalize_agent_review = _shared.normalize_agent_review


def run_publishing(session, intake_job_id: str) -> None:
    return _shared.run_publishing(
        session,
        intake_job_id,
        persist_fn=persist_document_and_policy,
    )


def execute_publishing_task(
    session,
    stage_task_id: str,
    intake_job_id: str,
    worker_id: str,
) -> bool:
    return _shared.execute_publishing_task(
        session,
        stage_task_id,
        intake_job_id,
        worker_id,
        persist_fn=persist_document_and_policy,
    )


_running_state = _shared._running_state
_json_safe = _shared._json_safe
