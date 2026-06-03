from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reality_rag_contracts import ApprovalTicket, StageName


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def load_review_artifact_payload(session, intake_job_id: str) -> dict[str, Any] | None:
    from reality_rag_persistence.models import StageResultModel

    row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == intake_job_id)
        .filter(StageResultModel.stage_name == StageName.AGENT_REVIEW.value)
        .order_by(StageResultModel.created_at.desc())
        .first()
    )
    if row is None:
        return None

    if row.result_ref:
        path = Path(row.result_ref)
        if path.exists() and path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))

    review_summary = row.summary_json or {}
    review_context = (
        review_summary.get("review_context", {})
        if isinstance(review_summary.get("review_context"), dict)
        else {}
    )
    artifact_metadata = (
        review_context.get("artifact_metadata", {})
        if isinstance(review_context.get("artifact_metadata"), dict)
        else {}
    )
    agent_review = (
        review_summary.get("agent_review", {})
        if isinstance(review_summary.get("agent_review"), dict)
        else {}
    )
    return {
        "review_run_id": row.stage_attempt_id,
        "intake_job_id": intake_job_id,
        "source_file_id": artifact_metadata.get("source_file_id"),
        "parse_snapshot_id": artifact_metadata.get("parse_snapshot_id"),
        "artifact_version": "v1",
        "result_hash": row.result_hash,
        "review_model": artifact_metadata.get("review_model", ""),
        "prompt_version": artifact_metadata.get("prompt_version", ""),
        "artifact_schema_version": artifact_metadata.get("artifact_schema_version", "v2"),
        "generated_at": artifact_metadata.get("generated_at", row.created_at.isoformat() if row.created_at else utc_now_iso()),
        "agent_review": agent_review,
        "review_context": review_context,
        "agent_review_ref": row.result_ref,
    }


def build_ticket_event_payload(session, ticket: ApprovalTicket) -> dict[str, Any]:
    from reality_rag_persistence.repositories.collections import CollectionRepository
    from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
    from reality_rag_persistence.repositories.source_files import SourceFileRepository

    intake_job = IntakeJobRepository(session).get(ticket.intake_job_id)
    source_file = (
        SourceFileRepository(session).get(intake_job.source_file_id)
        if intake_job is not None and intake_job.source_file_id
        else None
    )
    collection = CollectionRepository(session).get(ticket.collection_id)

    artifact_payload = load_review_artifact_payload(session, ticket.intake_job_id) or {}
    agent_review = (
        artifact_payload.get("agent_review", {})
        if isinstance(artifact_payload.get("agent_review"), dict)
        else {}
    )
    findings = agent_review.get("anchored_findings", []) if isinstance(agent_review.get("anchored_findings"), list) else []
    blocking_count = sum(
        1
        for finding in findings
        if isinstance(finding, dict) and str(finding.get("severity", "")).lower() in {"critical", "high"}
    )
    filename = None
    upload_id = None
    if source_file is not None:
        filename = source_file.sanitized_name or source_file.original_name or None
        upload_id = source_file.upload_id or None

    source_file_id = artifact_payload.get("source_file_id")
    if not source_file_id and intake_job is not None:
        source_file_id = intake_job.source_file_id

    parse_snapshot_id = artifact_payload.get("parse_snapshot_id")
    if not parse_snapshot_id and intake_job is not None:
        parse_snapshot_id = getattr(intake_job, "parse_snapshot_id", None)

    ticket_doc_id = ticket.final_doc_id or ticket.preliminary_doc_id
    enriched_findings: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        enriched_findings.append({
            "finding_id": str(finding.get("finding_id", "") or ""),
            "source_quote": str(finding.get("source_quote", "") or ""),
            "problem_summary": str(finding.get("problem_summary", "") or ""),
            "severity": str(finding.get("severity", "medium") or "medium"),
            "confidence": float(finding.get("confidence", 0.0) or 0.0),
            "ticket_id": ticket.ticket_id,
            "doc_id": ticket_doc_id,
            "source_file_id": source_file_id,
            "parse_snapshot_id": parse_snapshot_id,
            "evidence_id": None,
            "page_from": None,
            "page_to": None,
            "state": "open",
            "category": "",
            "problem_detail": None,
            "chunk_quote": None,
            "source_anchor_json": None,
            "why_wrong": None,
            "suggested_fix": None,
            "suggested_operation": None,
        })

    return {
        "ticket_id": ticket.ticket_id,
        "tenant_id": ticket.tenant_id or (collection.tenant_id if collection is not None else "tenant_acme"),
        "collection_id": ticket.collection_id,
        "upload_id": upload_id,
        "source_file_id": source_file_id,
        "parse_snapshot_id": parse_snapshot_id,
        "doc_id": ticket_doc_id,
        "title": filename or ticket_doc_id or ticket.ticket_id,
        "filename": filename,
        "state": ticket.state.value,
        "routing_recommendation": ticket.routing_recommendation,
        "decision": ticket.decision,
        "decision_actor": ticket.decision_actor,
        "decision_reason": ticket.decision_reason,
        "final_doc_id": ticket.final_doc_id,
        "confirmed_tags": ticket.confirmed_tags or [],
        "return_target_stage": ticket.return_target_stage,
        "return_reason": ticket.return_reason,
        "review_run_id": artifact_payload.get("review_run_id"),
        "agent_review_ref": artifact_payload.get("agent_review_ref"),
        "artifact_version": artifact_payload.get("artifact_version"),
        "prompt_version": artifact_payload.get("prompt_version"),
        "artifact_schema_version": artifact_payload.get("artifact_schema_version"),
        "generated_at": artifact_payload.get("generated_at"),
        "agent_decision": agent_review.get("decision"),
        "agent_risk_level": _derive_agent_risk_level(agent_review, findings),
        "agent_finding_count": len(enriched_findings),
        "agent_blocking_finding_count": blocking_count,
        "findings": enriched_findings,
    }


def _derive_agent_risk_level(agent_review: dict[str, Any], findings: list[dict[str, Any]]) -> str | None:
    severities = {
        str(finding.get("severity", "")).lower()
        for finding in findings
        if isinstance(finding, dict)
    }
    if "critical" in severities or "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"

    decision = str(agent_review.get("decision", "") or "").lower()
    if decision in {"reject", "quarantine"}:
        return "high"
    if decision in {"request_changes", "review"}:
        return "medium"

    risk_tags = agent_review.get("risk_tags", [])
    if isinstance(risk_tags, list) and risk_tags:
        return "medium"
    return "low" if decision == "approve" else None
