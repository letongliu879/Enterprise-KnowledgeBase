from __future__ import annotations

import json
import os
from pathlib import Path

from reality_rag_contracts import CanonicalMetadata, IndexStatus, PublishStatus

from .stages.protocol import StageContext


def build_canonical_metadata(ctx: StageContext) -> CanonicalMetadata:
    """Build CanonicalMetadata from StageContext."""
    doc_id = ctx.final_doc_id or ctx.doc_id
    return CanonicalMetadata(
        tenant_id=(ctx.tenant.tenant_id if ctx.tenant is not None else "default"),
        collection_id=ctx.collection_id,
        doc_id=doc_id,
        logical_document_id=ctx.logical_document_id,
        source_hash=ctx.source_hash,
        source_content_hash=ctx.content_hash or ctx.source_hash,
        version=ctx.version,
        publish_status=ctx.publish_status,
        index_status=(
            IndexStatus.NOT_INDEXED
            if ctx.publish_status != PublishStatus.PUBLISHED
            else IndexStatus.INDEXING
        ),
        authority_level=(ctx.collection.authority_level if ctx.collection is not None else 0),
        quality_summary=_truncate_summary(_quality_summary(ctx.quality_report)),
        processing_summary=_truncate_summary(_processing_summary(ctx.result)),
        asset_paths=ctx.asset_paths,
    )


def _base_sidecar_dir() -> Path:
    raw = os.getenv("REALITY_RAG_SIDECAR_DIR")
    if not raw:
        raise RuntimeError("REALITY_RAG_SIDECAR_DIR not set")
    return Path(raw)


def build_document_asset_paths(collection_id: str, doc_id: str) -> dict[str, str]:
    base = _base_sidecar_dir() / collection_id / doc_id
    return {
        "canonical_md": str(base / "canonical.md"),
        "canonical_meta": str(base / "canonical.meta.json"),
        "quality_report": str(base / "quality_report.json"),
        "agent_review": str(base / "agent_review.json"),
        "review_context": str(base / "review_context.json"),
        "human_review": str(base / "human_review.json"),
        "processing_record": str(base / "processing_record.json"),
        "chunk_manifest": str(base / "chunk_manifest.json"),
        "opensearch_records": str(base / "opensearch_records.json"),
        "qdrant_points": str(base / "qdrant_points.json"),
    }


def build_review_artifact_path(collection_id: str, intake_job_id: str) -> str:
    base = _base_sidecar_dir() / collection_id / "_review_runs" / intake_job_id
    return str(base / "agent_review_artifact.json")


def report_asset_path(collection_id: str, job_id: str) -> str:
    return str(_base_sidecar_dir() / collection_id / job_id / "conversion_report.json")


def write_json_asset(asset_path: str, payload: dict) -> None:
    path = Path(asset_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _truncate_summary(text: str) -> str:
    return text[:2048]


def _quality_summary(report) -> str:
    if report is None:
        return "No quality report"
    return (
        f"Tier {report.support_tier.value}: score {report.conversion_score:.2f}; "
        f"recommended {report.recommended_review_status.value}"
    )


def _processing_summary(result) -> str:
    if result is None:
        return "No conversion result"
    extension = result.metadata.get("extension", "")
    return f"{result.conversion_status.value} via {result.metadata.get('converter', 'unknown')} {extension}".strip()

