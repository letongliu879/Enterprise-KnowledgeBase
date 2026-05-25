from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from reality_rag_persistence.run_audit_store import PersistentRunAuditStore


def _append_projection(env_name: str, payload: dict[str, Any]) -> None:
    raw = os.getenv(env_name)
    if not raw:
        return
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


class IndexingTraceRecorder:
    def __init__(self) -> None:
        self._store = PersistentRunAuditStore()

    def write_run_trace(
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
        extra: dict[str, object] | None = None,
    ) -> None:
        payload = {
            "trace_id": trace_id,
            "run_kind": run_kind,
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "principal_id": principal_id,
            "query_id": query_id,
            "index_version_id": index_version_id,
            "profile_id": profile_id,
            "root_status": root_status,
            "debug_ref": debug_ref,
            "result_count": result_count,
        }
        if extra:
            payload.update(extra)
        _append_projection("REALITY_RAG_RUN_TRACES_FILE", payload)
        self._store.upsert_trace(
            trace_id=trace_id,
            run_kind=run_kind,
            tenant_id=tenant_id,
            collection_id=collection_id,
            principal_id=principal_id,
            query_id=query_id,
            index_version_id=index_version_id,
            profile_id=profile_id,
            root_status=root_status,
            debug_ref=debug_ref,
            result_count=result_count,
            source_file_id=str(payload.get("source_file_id") or "") or None,
            intake_job_id=str(payload.get("intake_job_id") or "") or None,
            final_doc_id=str(payload.get("final_doc_id") or "") or None,
            approval_ticket_id=str(payload.get("approval_ticket_id") or "") or None,
            extra_json=extra or {},
        )

    def write_run_step(self, *, trace_id: str, step_name: str, status: str, summary: str) -> None:
        payload = {
            "trace_id": trace_id,
            "step_name": step_name,
            "status": status,
            "summary": summary,
        }
        _append_projection("REALITY_RAG_RUN_STEPS_FILE", payload)
        self._store.append_step(**payload)

    def write_trace_artifact(
        self,
        *,
        trace_id: str,
        artifact_ref: str,
        artifact_kind: str,
        summary: str,
    ) -> None:
        payload = {
            "trace_id": trace_id,
            "artifact_ref": artifact_ref,
            "artifact_kind": artifact_kind,
            "summary": summary,
        }
        _append_projection("REALITY_RAG_TRACE_ARTIFACTS_FILE", payload)
        self._store.append_artifact(**payload)
