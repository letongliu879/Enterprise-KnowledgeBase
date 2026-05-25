from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories import (
    ChunkRegistryRepository,
    IndexBuildJobRepository,
    IndexedDocumentRepository,
    IndexRegistryRepository,
    IndexVersionRepository,
    ParseSnapshotRepository,
    PublishedDocumentRepository,
    PublishJobRepository,
    RunStepRepository,
    RunTraceRepository,
    TraceArtifactRepository,
)


class MainChainLineageInspector:
    def __init__(self, runtime_dir: Path) -> None:
        self._runtime_dir = runtime_dir

    def get_by_source_file_id(self, source_file_id: str) -> dict[str, object]:
        session = get_session()
        try:
            run_traces = RunTraceRepository(session).list_by_source_file_id(source_file_id)
            if not run_traces:
                raise KeyError(source_file_id)
            return self._build_bundle(session=session, source_file_id=source_file_id, trace_id=run_traces[0].trace_id)
        finally:
            session.close()

    def get_by_trace_id(self, trace_id: str) -> dict[str, object]:
        session = get_session()
        try:
            run_traces = RunTraceRepository(session).list_by_trace_id(trace_id)
            if not run_traces:
                raise KeyError(trace_id)
            source_file_id = next((item.source_file_id for item in run_traces if item.source_file_id), None)
            return self._build_bundle(session=session, source_file_id=source_file_id, trace_id=trace_id)
        finally:
            session.close()

    def _build_bundle(
        self,
        *,
        session,
        source_file_id: str | None,
        trace_id: str,
    ) -> dict[str, object]:
        run_traces = RunTraceRepository(session).list_by_trace_id(trace_id)
        run_steps = RunStepRepository(session).list_by_trace_id(trace_id)
        trace_artifacts = TraceArtifactRepository(session).list_by_trace_id(trace_id)

        root = next((item for item in run_traces if item.run_kind == "intake"), run_traces[0] if run_traces else None)
        inferred_source_file_id = source_file_id or (root.source_file_id if root else None)
        doc_dir = self._runtime_dir / inferred_source_file_id if inferred_source_file_id else None
        sidecar = self._read_sidecar_bundle(doc_dir)

        final_doc_id = self._first_non_empty(
            sidecar.get("governance_overlay", {}).get("final_doc_id"),
            *(item.final_doc_id for item in run_traces if item.final_doc_id),
        )
        collection_id = self._first_non_empty(
            sidecar.get("metadata", {}).get("collection_id"),
            *(item.collection_id for item in run_traces if item.collection_id),
        )
        parse_snapshot_id = self._first_non_empty(
            *(
                str(item.extra_json.get("parse_snapshot_id") or "")
                for item in run_traces
                if isinstance(item.extra_json, dict)
            ),
        )

        parse_snapshot = None
        if parse_snapshot_id:
            parse_snapshot = ParseSnapshotRepository(session).get(parse_snapshot_id)

        published_document = (
            PublishedDocumentRepository(session).get_by_final_doc_id(final_doc_id)
            if final_doc_id
            else None
        )
        publish_jobs = []
        indexed_documents = []
        relevant_version_ids: set[str] = set()
        if collection_id:
            publish_jobs = [
                self._dump_model(job)
                for job in PublishJobRepository(session).list_by_collection(collection_id)
                if not final_doc_id or job.final_doc_id == final_doc_id
            ]
            indexed_documents = [
                self._dump_model(item)
                for item in IndexedDocumentRepository(session).list_by_collection(collection_id)
                if not final_doc_id or item.final_doc_id == final_doc_id
            ]
            relevant_version_ids.update(
                str(item["index_version"])
                for item in indexed_documents
                if str(item.get("index_version") or "").strip()
            )

        all_chunks = [
            self._dump_model(chunk)
            for chunk in ChunkRegistryRepository(session).list_all()
            if (not final_doc_id or chunk.final_doc_id == final_doc_id)
            and (not collection_id or chunk.collection_id == collection_id)
        ]
        relevant_version_ids.update(str(chunk["index_version_id"]) for chunk in all_chunks if chunk.get("index_version_id"))

        index_versions = []
        index_build_jobs = []
        index_registry = None
        if collection_id:
            index_versions = [
                self._dump_model(item)
                for item in IndexVersionRepository(session).list_by_collection(collection_id)
                if item.index_version_id in relevant_version_ids or not relevant_version_ids
            ]
            index_build_jobs = [
                self._dump_model(job)
                for job in IndexBuildJobRepository(session).list_by_collection(collection_id)
                if job.target_index_version in relevant_version_ids or not relevant_version_ids
            ]
            registry = IndexRegistryRepository(session).get(collection_id)
            index_registry = self._dump_model(registry) if registry is not None else None

        return {
            "lookup": {
                "trace_id": trace_id,
                "source_file_id": inferred_source_file_id,
                "collection_id": collection_id,
                "final_doc_id": final_doc_id,
            },
            "roots": [self._dump_model(item) for item in run_traces],
            "steps": [self._dump_model(item) for item in run_steps],
            "artifacts": [self._dump_model(item) for item in trace_artifacts],
            "sidecar": sidecar,
            "parse_snapshot": self._dump_model(parse_snapshot) if parse_snapshot is not None else None,
            "published_document": self._dump_model(published_document) if published_document is not None else None,
            "publish_jobs": publish_jobs,
            "index_build_jobs": index_build_jobs,
            "index_registry": index_registry,
            "index_versions": index_versions,
            "indexed_documents": indexed_documents,
            "chunks": all_chunks,
            "chunk_field_names": sorted(all_chunks[0].keys()) if all_chunks else [],
        }

    def _read_sidecar_bundle(self, doc_dir: Path | None) -> dict[str, object]:
        if doc_dir is None:
            return {}
        asset_paths: dict[str, str] = {}
        if doc_dir.exists():
            for item in sorted(doc_dir.iterdir()):
                asset_paths[item.name] = str(item)
        metadata = self._read_json(doc_dir / "metadata.json")
        approval = self._read_json(doc_dir / "approval.json")
        governance_overlay = self._read_json(doc_dir / "governance-overlay.json")
        approval_audit_log = self._read_jsonl(doc_dir / "approval_audit_log.jsonl")
        return {
            "doc_dir": str(doc_dir),
            "asset_paths": asset_paths,
            "metadata": metadata,
            "approval": approval,
            "governance_overlay": governance_overlay,
            "approval_audit_log": approval_audit_log,
        }

    @staticmethod
    def _read_json(path: Path) -> dict[str, object] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, object]]:
        if not path.exists():
            return []
        rows: list[dict[str, object]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    @staticmethod
    def _dump_model(value: object) -> dict[str, object] | None:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        return {"value": value}

    @staticmethod
    def _first_non_empty(*values: object) -> str | None:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None
