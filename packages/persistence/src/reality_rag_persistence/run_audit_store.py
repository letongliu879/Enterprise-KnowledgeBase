from __future__ import annotations

import logging
from typing import Any

from .database import create_all, get_session
from .repositories import RunStepRepository, RunTraceRepository, TraceArtifactRepository

logger = logging.getLogger(__name__)


class PersistentRunAuditStore:
    def __init__(self) -> None:
        self._ready = False

    def _ensure_ready(self) -> bool:
        if self._ready:
            return True
        try:
            create_all()
        except Exception:
            logger.exception("run audit store init failed")
            return False
        self._ready = True
        return True

    def upsert_trace(
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
    ) -> None:
        if not self._ensure_ready():
            return
        session = get_session()
        try:
            RunTraceRepository(session).upsert(
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
                source_file_id=source_file_id,
                intake_job_id=intake_job_id,
                final_doc_id=final_doc_id,
                approval_ticket_id=approval_ticket_id,
                extra_json=extra_json,
            )
            session.commit()
        except Exception:
            logger.exception("run audit trace write failed: trace_id=%s run_kind=%s", trace_id, run_kind)
            session.rollback()
        finally:
            session.close()

    def append_step(
        self,
        *,
        trace_id: str,
        step_name: str,
        status: str,
        summary: str,
        details_json: dict[str, Any] | None = None,
    ) -> None:
        if not self._ensure_ready():
            return
        session = get_session()
        try:
            RunStepRepository(session).append(
                trace_id=trace_id,
                step_name=step_name,
                status=status,
                summary=summary,
                details_json=details_json,
            )
            session.commit()
        except Exception:
            logger.exception("run audit step write failed: trace_id=%s step_name=%s", trace_id, step_name)
            session.rollback()
        finally:
            session.close()

    def append_artifact(
        self,
        *,
        trace_id: str,
        artifact_ref: str,
        artifact_kind: str,
        summary: str,
        details_json: dict[str, Any] | None = None,
    ) -> None:
        if not self._ensure_ready():
            return
        session = get_session()
        try:
            TraceArtifactRepository(session).append(
                trace_id=trace_id,
                artifact_ref=artifact_ref,
                artifact_kind=artifact_kind,
                summary=summary,
                details_json=details_json,
            )
            session.commit()
        except Exception:
            logger.exception(
                "run audit artifact write failed: trace_id=%s artifact_kind=%s",
                trace_id,
                artifact_kind,
            )
            session.rollback()
        finally:
            session.close()
