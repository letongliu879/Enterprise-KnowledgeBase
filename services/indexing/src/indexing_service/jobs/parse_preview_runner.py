from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import perf_counter

from indexing_service.domain import ParseSnapshotRecord
from indexing_service.metrics import InMemoryIndexingMetrics
from indexing_service.parse_detection import ParseHintDetector
from indexing_service.preview_contracts import ParsePreviewAccepted, ParsePreviewRequestedCommand
from indexing_service.ragflow_strategy import get_ragflow_parser
from indexing_service.repository import InMemoryIndexingRepository, create_indexing_repository
from indexing_service.runtime_bridge.ragflow_app_runtime import RAGFlowAppRuntime
from indexing_service.security import IndexingSecurity
from indexing_service.trace_recorder import IndexingTraceRecorder


class ParsePreviewRunner:
    def __init__(
        self,
        repository: InMemoryIndexingRepository | None = None,
        runtime: RAGFlowAppRuntime | None = None,
        detector: ParseHintDetector | None = None,
        trace_recorder: IndexingTraceRecorder | None = None,
        metrics: InMemoryIndexingMetrics | None = None,
        security: IndexingSecurity | None = None,
    ) -> None:
        self._repository = repository or create_indexing_repository()
        self._runtime = runtime or RAGFlowAppRuntime()
        self._detector = detector or ParseHintDetector()
        self._trace = trace_recorder or IndexingTraceRecorder()
        self._metrics = metrics or InMemoryIndexingMetrics()
        self._security = security or IndexingSecurity()

    def accept(self, command: ParsePreviewRequestedCommand) -> ParsePreviewAccepted:
        started_at = perf_counter()
        self._metrics.incr("indexing.parse_preview.requests_total")
        requested_parser_id = (command.parser_id or "").strip().lower()
        collection_default_parser_id = (command.collection_parser_id or "").strip().lower()
        profile_id = collection_default_parser_id or "naive"
        self._trace.write_run_trace(
            trace_id=command.trace_id,
            run_kind="indexing_parse_preview",
            tenant_id=command.tenant_id,
            collection_id=command.collection_id,
            principal_id=command.source_system or "system",
            query_id=command.request_id,
            index_version_id="pending",
            profile_id=profile_id,
            root_status="RUNNING",
            debug_ref=f"dbg://indexing/parse-preview/{command.request_id}",
            result_count=0,
            extra={
                "source_file_id": command.source_file_id,
                "source_binary_ref": command.source_binary_ref,
            },
        )
        self._trace.write_run_step(
            trace_id=command.trace_id,
            step_name="parse_preview_requested",
            status="STARTED",
            summary=f"source_file_id={command.source_file_id};filename={command.filename};mime_type={command.mime_type}",
        )
        self._security.authorize_parse_preview(
            tenant_id=command.tenant_id,
            collection_id=command.collection_id,
            principal_id=command.source_system or "system",
            source_metadata=command.metadata,
        )
        binary = Path(command.source_binary_ref).read_bytes()
        hints = self._detector.detect(
            filename=command.filename,
            mime_type=command.mime_type,
            binary=binary,
        )
        self._trace.write_run_step(
            trace_id=command.trace_id,
            step_name="parse_hint_detected",
            status="SUCCEEDED",
            summary=(
                f"content_class_hint={hints.content_class_hint or ''};"
                f"scanned_pdf={str(hints.scanned_pdf).lower()};"
                f"table_heavy={str(hints.table_heavy).lower()};"
                f"presentation_like={str(hints.presentation_like).lower()};"
                f"reason={hints.reason}"
            ),
        )

        parser_id = get_ragflow_parser(
            filename=command.filename,
            collection_default_parser_id=collection_default_parser_id or "naive",
        )
        collection_parser_config = dict(command.collection_parser_config)
        parser_config = dict(collection_parser_config)
        warnings: list[str] = [hints.reason] if hints.reason else []
        if requested_parser_id:
            warnings.append(f"manual_parser_override_ignored:{requested_parser_id}")
        if command.parser_config:
            warnings.append("manual_parser_config_override_ignored")
        decision_reason = f"upstream:file_service.get_parser:{parser_id}"
        self._trace.write_run_step(
            trace_id=command.trace_id,
            step_name="parse_policy_resolved",
            status="SUCCEEDED",
            summary=(
                f"parser_id={parser_id};"
                f"collection_parser_id={collection_default_parser_id or 'naive'};"
                f"decision_reason={decision_reason}"
            ),
        )
        self._metrics.incr(f"indexing.parse_preview.profile.{parser_id}.total")

        preview = self._runtime.build_preview(
            asset_ref=command.source_binary_ref,
            parser_id=parser_id,
            parser_config=parser_config,
            fallback_title=Path(command.filename).stem or command.source_file_id,
            tenant_id=command.tenant_id,
            source_file_id=command.source_file_id,
        )
        progress_events = list(preview.get("progress_events", []))
        self._trace.write_trace_artifact(
            trace_id=command.trace_id,
            artifact_ref=f"art://indexing/{command.request_id}/runtime-progress",
            artifact_kind="runtime_progress_events",
            summary=f"event_count={len(progress_events)}",
        )
        parse_snapshot_id = f"pss_{command.source_file_id}"
        input_hash = "sha256:" + sha256(binary).hexdigest()
        upstream_chunks = list(preview.get("upstream_chunks", []))
        warnings.extend(str(item) for item in preview.get("warnings", []) if str(item))
        if not upstream_chunks:
            warnings.append(f"upstream:no_chunks:{parser_id}")
        chunk_preview = [
            {
                "text": str(chunk.get("content_with_weight", "")).strip(),
                "doc_type_kwd": str(chunk.get("doc_type_kwd", "text")),
                "page_num_int": list(chunk.get("page_num_int", [])),
                "position_int": list(chunk.get("position_int", [])),
            }
            for chunk in upstream_chunks[:64]
            if str(chunk.get("content_with_weight", "")).strip()
        ]
        snapshot = ParseSnapshotRecord(
            parse_snapshot_id=parse_snapshot_id,
            request_id=command.request_id,
            tenant_id=command.tenant_id,
            collection_id=command.collection_id,
            source_file_id=command.source_file_id,
            source_binary_ref=command.source_binary_ref,
            source_filename=str(preview.get("source_filename") or command.filename),
            source_suffix=str(preview.get("source_suffix") or Path(command.filename).suffix.lower().lstrip(".")),
            parser_id=parser_id,
            parser_backend="ragflow_app",
            collection_parser_config=collection_parser_config,
            parser_config=dict(preview.get("parser_config", parser_config)),
            input_hash=input_hash,
            preview_text=str(preview["preview_text"]),
            upstream_chunks=upstream_chunks,
            outline=list(preview["outline"]),
            document_metadata=dict(preview.get("document_metadata", {})),
            chunk_preview=chunk_preview,
            warnings=warnings,
            decision_reason=decision_reason,
        )
        self._repository.save_parse_snapshot(snapshot)
        self._trace.write_run_step(
            trace_id=command.trace_id,
            step_name="parse_snapshot_persisted",
            status="SUCCEEDED",
            summary=(
                f"parse_snapshot_id={parse_snapshot_id};"
                f"upstream_chunk_count={len(snapshot.upstream_chunks)};"
                f"chunk_preview_count={len(snapshot.chunk_preview)}"
            ),
        )
        self._trace.write_trace_artifact(
            trace_id=command.trace_id,
            artifact_ref=f"parse_snapshot:{parse_snapshot_id}",
            artifact_kind="parse_snapshot",
            summary=(
                f"parser_id={snapshot.parser_id};"
                f"source_suffix={snapshot.source_suffix};"
                f"upstream_chunk_count={len(snapshot.upstream_chunks)}"
            ),
        )
        self._trace.write_run_trace(
            trace_id=command.trace_id,
            run_kind="indexing_parse_preview",
            tenant_id=command.tenant_id,
            collection_id=command.collection_id,
            principal_id=command.source_system or "system",
            query_id=command.request_id,
            index_version_id="pending",
            profile_id=parser_id,
            root_status="SUCCEEDED",
            debug_ref=f"dbg://indexing/parse-preview/{command.request_id}",
            result_count=len(snapshot.chunk_preview),
            extra={
                "source_file_id": command.source_file_id,
                "parse_snapshot_id": parse_snapshot_id,
                "decision_reason": decision_reason,
            },
        )
        duration_ms = int((perf_counter() - started_at) * 1000)
        self._metrics.incr("indexing.parse_preview.succeeded_total")
        self._metrics.observe_ms("indexing.parse_preview.duration_ms", duration_ms)
        self._metrics.observe_ms(
            f"indexing.parse_preview.profile.{parser_id}.duration_ms",
            duration_ms,
        )
        return ParsePreviewAccepted(
            request_id=command.request_id,
            source_file_id=command.source_file_id,
            parse_snapshot_id=parse_snapshot_id,
            parser_id=parser_id,
            decision_reason=decision_reason,
            preview_text_ref=f"parse_snapshot:{parse_snapshot_id}:preview_text",
            chunk_preview_ref=f"parse_snapshot:{parse_snapshot_id}:chunk_preview",
            warnings=snapshot.warnings,
            trace_id=command.trace_id,
        )
