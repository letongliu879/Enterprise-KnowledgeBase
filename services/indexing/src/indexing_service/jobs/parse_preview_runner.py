from __future__ import annotations

import json
import os
import urllib.request
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from reality_rag_contracts.indexing_models import ParseSnapshotRecord
from indexing_service.metrics import InMemoryIndexingMetrics
from indexing_service.parse_detection import ParseHintDetector


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    try:
        import json as _json
        _json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def _read_bytes(source_binary_ref: str) -> bytes:
    if source_binary_ref.startswith("s3://"):
        import urllib.parse as _up
        s3_endpoint = os.environ.get("S3_ENDPOINT", "http://127.0.0.1:9000").rstrip("/")
        rest = source_binary_ref[5:]  # strip "s3://"
        bucket, key = rest.split("/", 1)
        quoted_key = _up.quote(key, safe="")
        url = f"{s3_endpoint}/{bucket}/{quoted_key}"
        with urllib.request.urlopen(url) as resp:
            return resp.read()
    return Path(source_binary_ref).read_bytes()
from indexing_service.parse_policy import ParsePolicyResolver
from indexing_service.preview_contracts import ParsePreviewAccepted, ParsePreviewRequestedCommand
from indexing_service.repository import IndexingRepository, create_indexing_repository
from indexing_service.runtime_bridge.ragflow_app_runtime import RAGFlowAppRuntime
from indexing_service.security import IndexingSecurity
from indexing_service.trace_recorder import IndexingTraceRecorder


class ParsePreviewRunner:
    def __init__(
        self,
        repository: IndexingRepository | None = None,
        runtime: RAGFlowAppRuntime | None = None,
        policy_resolver: ParsePolicyResolver | None = None,
        trace_recorder: IndexingTraceRecorder | None = None,
        metrics: InMemoryIndexingMetrics | None = None,
        security: IndexingSecurity | None = None,
    ) -> None:
        self._repository = repository or create_indexing_repository()
        self._runtime = runtime or RAGFlowAppRuntime()
        self._policy_resolver = policy_resolver or ParsePolicyResolver()
        self._trace = trace_recorder or IndexingTraceRecorder()
        self._metrics = metrics or InMemoryIndexingMetrics()
        self._security = security or IndexingSecurity()

    def accept(self, command: ParsePreviewRequestedCommand) -> ParsePreviewAccepted:
        started_at = perf_counter()
        self._metrics.incr("indexing.parse_preview.requests_total")
        requested_parser_id = (command.parser_id or "").strip().lower()
        collection_default_parser_id = (command.collection_parser_id or "").strip().lower()
        self._trace.write_run_trace(
            trace_id=command.trace_id,
            run_kind="indexing_parse_preview",
            tenant_id=command.tenant_id,
            collection_id=command.collection_id,
            principal_id=command.source_system or "system",
            query_id=command.request_id,
            index_version_id="pending",
            profile_id=collection_default_parser_id or "naive",
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
        binary = _read_bytes(command.source_binary_ref)
        policy = self._policy_resolver.resolve(
            filename=command.filename,
            mime_type=command.mime_type,
            binary=binary,
            collection_default_parser_id=collection_default_parser_id or "naive",
            collection_parser_config=dict(command.collection_parser_config),
            requested_parser_id=requested_parser_id or None,
            requested_parser_config=dict(command.parser_config) if command.parser_config else None,
        )
        self._trace.write_run_step(
            trace_id=command.trace_id,
            step_name="parse_hint_detected",
            status="SUCCEEDED",
            summary=(
                f"document_family={policy.document_family};"
                f"parser_id={policy.parser_id};"
                f"decision_reason={policy.decision_reason}"
            ),
        )
        self._trace.write_run_step(
            trace_id=command.trace_id,
            step_name="parse_policy_resolved",
            status="SUCCEEDED",
            summary=(
                f"parser_id={policy.parser_id};"
                f"document_family={policy.document_family};"
                f"effective_profile_id={policy.effective_profile_id};"
                f"chunk_profile_id={policy.chunk_profile_id}"
            ),
        )
        self._metrics.incr(f"indexing.parse_preview.profile.{policy.parser_id}.total")

        preview = self._runtime.build_preview(
            asset_ref=command.source_binary_ref,
            parser_id=policy.parser_id,
            parser_config=policy.parser_config,
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
        input_hash = "sha256:" + sha256(binary).hexdigest()
        policy_key = json.dumps({"parser_id": policy.parser_id, "parser_config": policy.parser_config}, sort_keys=True)
        policy_hash = sha256(policy_key.encode("utf-8")).hexdigest()[:16]
        parse_snapshot_id = f"pss_{input_hash[:16]}_{policy.parser_id}_{policy_hash}"
        upstream_chunks = _json_safe(list(preview.get("upstream_chunks", [])))
        warnings = list(policy.warnings)
        warnings.extend(str(item) for item in preview.get("warnings", []) if str(item))
        if not upstream_chunks:
            warnings.append(f"upstream:no_chunks:{policy.parser_id}")
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
            parser_id=policy.parser_id,
            parser_backend=policy.parser_backend,
            parser_profile_id=policy.effective_profile_id,
            chunk_profile_id=policy.chunk_profile_id,
            document_family=policy.document_family,
            effective_policy=policy.decision_reason,
            collection_parser_config=dict(command.collection_parser_config),
            parser_config=dict(preview.get("parser_config", policy.parser_config)),
            input_hash=input_hash,
            preview_text=str(preview["preview_text"]),
            upstream_chunks=upstream_chunks,
            outline=list(preview["outline"]),
            document_metadata=dict(preview.get("document_metadata", {})),
            chunk_preview=chunk_preview,
            warnings=warnings,
            decision_reason=policy.decision_reason,
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
            profile_id=policy.parser_id,
            root_status="SUCCEEDED",
            debug_ref=f"dbg://indexing/parse-preview/{command.request_id}",
            result_count=len(snapshot.chunk_preview),
            extra={
                "source_file_id": command.source_file_id,
                "parse_snapshot_id": parse_snapshot_id,
                "decision_reason": policy.decision_reason,
            },
        )
        duration_ms = int((perf_counter() - started_at) * 1000)
        self._metrics.incr("indexing.parse_preview.succeeded_total")
        self._metrics.observe_ms("indexing.parse_preview.duration_ms", duration_ms)
        self._metrics.observe_ms(
            f"indexing.parse_preview.profile.{policy.parser_id}.duration_ms",
            duration_ms,
        )
        return ParsePreviewAccepted(
            request_id=command.request_id,
            source_file_id=command.source_file_id,
            parse_snapshot_id=parse_snapshot_id,
            parser_id=policy.parser_id,
            decision_reason=policy.decision_reason,
            preview_text_ref=f"parse_snapshot:{parse_snapshot_id}:preview_text",
            chunk_preview_ref=f"parse_snapshot:{parse_snapshot_id}:chunk_preview",
            warnings=snapshot.warnings,
            trace_id=command.trace_id,
        )
