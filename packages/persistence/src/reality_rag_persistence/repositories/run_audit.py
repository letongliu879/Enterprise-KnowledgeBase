from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy.orm import Session

from ..models import RunStepModel, RunTraceModel, TraceArtifactModel


@dataclass
class RunTraceEntry:
    run_trace_id: str
    trace_id: str
    run_kind: str
    tenant_id: str
    collection_id: str
    principal_id: str
    query_id: str
    index_version_id: str
    profile_id: str
    root_status: str
    debug_ref: str
    result_count: int
    source_file_id: str | None = None
    intake_job_id: str | None = None
    final_doc_id: str | None = None
    approval_ticket_id: str | None = None
    extra_json: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class RunStepEntry:
    run_step_id: int
    trace_id: str
    step_name: str
    status: str
    summary: str
    details_json: dict[str, Any] | None = None
    created_at: datetime | None = None


@dataclass
class TraceArtifactEntry:
    trace_artifact_id: int
    trace_id: str
    artifact_ref: str
    artifact_kind: str
    summary: str
    details_json: dict[str, Any] | None = None
    created_at: datetime | None = None


class RunTraceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        *,
        trace_id: str,
        run_kind: str,
        tenant_id: str,
        collection_id: str,
        principal_id: str,
        query_id: str,
        index_version_id: str,
        profile_id: str,
        root_status: str,
        debug_ref: str,
        result_count: int,
        source_file_id: str | None = None,
        intake_job_id: str | None = None,
        final_doc_id: str | None = None,
        approval_ticket_id: str | None = None,
        extra_json: dict[str, Any] | None = None,
    ) -> RunTraceEntry:
        now = datetime.now(timezone.utc)
        run_trace_id = self._build_id(trace_id=trace_id, run_kind=run_kind, query_id=query_id)
        row = self._session.get(RunTraceModel, run_trace_id)
        if row is None:
            row = RunTraceModel(
                run_trace_id=run_trace_id,
                trace_id=trace_id,
                run_kind=run_kind,
                created_at=now,
            )
            self._session.add(row)
        row.tenant_id = tenant_id
        row.collection_id = collection_id
        row.principal_id = principal_id
        row.query_id = query_id
        row.index_version_id = index_version_id
        row.profile_id = profile_id
        row.root_status = root_status
        row.debug_ref = debug_ref
        row.result_count = int(result_count)
        row.source_file_id = source_file_id
        row.intake_job_id = intake_job_id
        row.final_doc_id = final_doc_id
        row.approval_ticket_id = approval_ticket_id
        row.extra_json = dict(extra_json or {})
        row.updated_at = now
        self._session.flush()
        return self._to_entry(row)

    def get(self, run_trace_id: str) -> RunTraceEntry | None:
        row = self._session.get(RunTraceModel, run_trace_id)
        if row is None:
            return None
        return self._to_entry(row)

    def list_by_trace_id(self, trace_id: str) -> list[RunTraceEntry]:
        rows = (
            self._session.query(RunTraceModel)
            .filter(RunTraceModel.trace_id == trace_id)
            .order_by(RunTraceModel.created_at.asc())
            .all()
        )
        return [self._to_entry(row) for row in rows]

    def list_by_source_file_id(self, source_file_id: str) -> list[RunTraceEntry]:
        rows = (
            self._session.query(RunTraceModel)
            .filter(RunTraceModel.source_file_id == source_file_id)
            .order_by(RunTraceModel.created_at.asc())
            .all()
        )
        return [self._to_entry(row) for row in rows]

    def list_by_final_doc_id(self, final_doc_id: str) -> list[RunTraceEntry]:
        rows = (
            self._session.query(RunTraceModel)
            .filter(RunTraceModel.final_doc_id == final_doc_id)
            .order_by(RunTraceModel.created_at.asc())
            .all()
        )
        return [self._to_entry(row) for row in rows]

    @staticmethod
    def _build_id(*, trace_id: str, run_kind: str, query_id: str) -> str:
        return "rtr_" + sha256(f"{trace_id}:{run_kind}:{query_id}".encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _to_entry(row: RunTraceModel) -> RunTraceEntry:
        return RunTraceEntry(
            run_trace_id=row.run_trace_id,
            trace_id=row.trace_id,
            run_kind=row.run_kind,
            tenant_id=row.tenant_id,
            collection_id=row.collection_id,
            principal_id=row.principal_id,
            query_id=row.query_id,
            index_version_id=row.index_version_id,
            profile_id=row.profile_id,
            root_status=row.root_status,
            debug_ref=row.debug_ref,
            result_count=row.result_count,
            source_file_id=row.source_file_id,
            intake_job_id=row.intake_job_id,
            final_doc_id=row.final_doc_id,
            approval_ticket_id=row.approval_ticket_id,
            extra_json=row.extra_json or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class RunStepRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self,
        *,
        trace_id: str,
        step_name: str,
        status: str,
        summary: str,
        details_json: dict[str, Any] | None = None,
    ) -> RunStepEntry:
        row = RunStepModel(
            trace_id=trace_id,
            step_name=step_name,
            status=status,
            summary=summary,
            details_json=dict(details_json or {}),
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(row)
        self._session.flush()
        return self._to_entry(row)

    def list_by_trace_id(self, trace_id: str) -> list[RunStepEntry]:
        rows = (
            self._session.query(RunStepModel)
            .filter(RunStepModel.trace_id == trace_id)
            .order_by(RunStepModel.run_step_id.asc())
            .all()
        )
        return [self._to_entry(row) for row in rows]

    @staticmethod
    def _to_entry(row: RunStepModel) -> RunStepEntry:
        return RunStepEntry(
            run_step_id=row.run_step_id,
            trace_id=row.trace_id,
            step_name=row.step_name,
            status=row.status,
            summary=row.summary,
            details_json=row.details_json or {},
            created_at=row.created_at,
        )


class TraceArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self,
        *,
        trace_id: str,
        artifact_ref: str,
        artifact_kind: str,
        summary: str,
        details_json: dict[str, Any] | None = None,
    ) -> TraceArtifactEntry:
        row = TraceArtifactModel(
            trace_id=trace_id,
            artifact_ref=artifact_ref,
            artifact_kind=artifact_kind,
            summary=summary,
            details_json=dict(details_json or {}),
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(row)
        self._session.flush()
        return self._to_entry(row)

    def list_by_trace_id(self, trace_id: str) -> list[TraceArtifactEntry]:
        rows = (
            self._session.query(TraceArtifactModel)
            .filter(TraceArtifactModel.trace_id == trace_id)
            .order_by(TraceArtifactModel.trace_artifact_id.asc())
            .all()
        )
        return [self._to_entry(row) for row in rows]

    @staticmethod
    def _to_entry(row: TraceArtifactModel) -> TraceArtifactEntry:
        return TraceArtifactEntry(
            trace_artifact_id=row.trace_artifact_id,
            trace_id=row.trace_id,
            artifact_ref=row.artifact_ref,
            artifact_kind=row.artifact_kind,
            summary=row.summary,
            details_json=row.details_json or {},
            created_at=row.created_at,
        )
