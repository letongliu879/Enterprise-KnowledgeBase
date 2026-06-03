"""Pure stage executors — operate on schema inputs, no StageContext, no mandatory DB.

Each logical stage has a pure executor that:
  1. Accepts a schema input + injectable dependencies
  2. Returns a schema output with input_hash / result_hash
  3. Does NOT depend on StageContext or mutable global state

DB-dependent lookups (dedup, version, persist) are injected as parameters
so tests can run with mocks or stub data.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reality_rag_contracts import (
    AgentReview,
    AnchoredFinding,
    ConversionRequest,
    ConversionResult,
    ConversionStatus,
    DocumentSupportTier,
    IndexStatus,
    PublishStatus,
    QualityReport,
)

from intake_runtime.converters.base import BaseConverter
from intake_runtime.pipeline_utils import build_canonical_metadata, build_document_asset_paths
from .hash_utils import compute_input_hash, compute_result_hash
from .schemas import (
    ConversionStageInput,
    ConversionStageOutput,
    PublishingStageInput,
    PublishingStageOutput,
    ReviewStageInput,
    ReviewStageOutput,
    VersionConflictInfo,
)

if TYPE_CHECKING:
    from intake_runtime.agent_review_cache import AgentReviewCache


# ──────────────────────────────────────────────────────────────────────────────
#  Pure conversion executor
# ──────────────────────────────────────────────────────────────────────────────


def run_conversion_stage(
    inp: ConversionStageInput,
    converters: list[BaseConverter],
    *,
    existing_published_doc_id: str | None = None,
    latest_version: int | None = None,
) -> ConversionStageOutput:
    """Pure executor for the conversion logical stage.

    Parameters
    ----------
    inp:
        Stage input schema.
    converters:
        List of converter instances (injected, testable with fakes).
    existing_published_doc_id:
        Result of dedup lookup.  If set, the stage skips.
    latest_version:
        Result of version lookup.  If set, version = latest_version + 1.
    """
    # -- 1. Convert file -------------------------------------------------
    conv = _select_converter(converters, inp.source_file_path)
    if conv is not None:
        result = conv.convert(
            ConversionRequest(
                source_file_path=inp.source_file_path,
                collection_id=inp.collection_id,
                options={
                    "source_file_id": inp.source_file_id,
                    "tenant_id": inp.tenant_id,
                    "trace_id": inp.trace_id,
                    "metadata": dict(inp.source_metadata),
                },
            )
        )
    else:
        result = ConversionResult(
            source_file_path=inp.source_file_path,
            conversion_status=ConversionStatus.UNSUPPORTED,
            error_message=f"No converter found for: {inp.source_file_path}",
        )

    # -- 2. Dedup --------------------------------------------------------
    source_hash = inp.source_hash or _compute_source_hash(inp.source_file_path)
    dedup_skipped = False
    skip_reason: str | None = None
    preliminary_doc_id = ""
    logical_document_id = ""
    version = 1
    version_conflict: VersionConflictInfo | None = None

    if result.conversion_status == ConversionStatus.SUCCESS:
        if existing_published_doc_id is not None:
            dedup_skipped = True
            skip_reason = "duplicate"
            preliminary_doc_id = existing_published_doc_id
        else:
            # -- 3. Version ------------------------------------------------
            logical_document_id = _logical_document_id(inp.source_file_path)
            version = (latest_version or 0) + 1
            preliminary_doc_id = _doc_id(
                inp.source_file_path, version, inp.collection_id
            )
            if latest_version is not None and latest_version > 0:
                version_conflict = VersionConflictInfo(
                    logical_document_id=logical_document_id,
                    existing_version=latest_version,
                    proposed_version=version,
                    conflict_type="new_version",
                )

    # -- 4. Quality ------------------------------------------------------
    quality_report: QualityReport | None = None
    if result.conversion_status == ConversionStatus.SUCCESS and not dedup_skipped:
        quality_report = _build_quality_report(preliminary_doc_id or inp.source_file_path, result)

    # -- Build output ----------------------------------------------------
    input_hash = compute_input_hash(inp)
    output = ConversionStageOutput(
        schema_version=inp.schema_version,
        input_hash=input_hash,
        result_hash="",
        conversion_result=result,
        quality_report=quality_report,
        preliminary_doc_id=preliminary_doc_id,
        logical_document_id=logical_document_id,
        version=version,
        source_hash=source_hash,
        version_conflict=version_conflict,
        dedup_skipped=dedup_skipped,
        skip_reason=skip_reason,
        parse_snapshot_id=str((result.metadata or {}).get("parse_snapshot_id") or "").strip(),
    )
    output.result_hash = compute_result_hash(output)
    return output


# -- Helpers copied / adapted from existing stages -------------------------

def _select_converter(converters: list[BaseConverter], file_path: str) -> BaseConverter | None:
    ext_map: dict[str, BaseConverter] = {}
    for c in converters:
        for ext in c.supported_extensions():
            ext_map[ext] = c
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext)


def _compute_source_hash(source_file_path: str) -> str:
    path = Path(source_file_path)
    if not path.exists():
        return ""
    import hashlib

    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _logical_document_id(source_file_path: str) -> str:
    import hashlib

    normalized_path = source_file_path.lower().encode("utf-8")
    digest = hashlib.sha1(normalized_path).hexdigest()[:8]
    stem = Path(source_file_path).stem.lower()
    slug = "".join(ch if ch.isalnum() else "-" for ch in stem).strip("-")
    slug = "-".join(part for part in slug.split("-") if part) or "document"
    return f"{slug}-{digest}"


def _doc_id(source_file_path: str, version: int, collection_id: str) -> str:
    import hashlib

    normalized_path = source_file_path.lower().encode("utf-8")
    collection_suffix = collection_id.lower().encode("utf-8") if collection_id else b""
    digest = hashlib.sha1(normalized_path + collection_suffix).hexdigest()[:8]
    stem = Path(source_file_path).stem.lower()
    slug = "".join(ch if ch.isalnum() else "-" for ch in stem).strip("-")
    slug = "-".join(part for part in slug.split("-") if part) or "document"
    return f"doc-{slug}-{digest}-v{version}"


def _build_quality_report(doc_id: str, result: ConversionResult) -> QualityReport:
    import re

    from intake_runtime.quality_utils import assess_table_quality, detect_garbled_text, detect_truncation

    canonical_md = result.canonical_md or ""
    length = len(canonical_md)

    score = 1.0 if length > 0 else 0.0
    has_headings = bool(re.search(r"^#{1,6}\s+", canonical_md, re.MULTILINE))
    paragraph_count = len([p for p in canonical_md.split("\n\n") if p.strip()])

    if length >= 500 and has_headings and paragraph_count >= 3:
        support_tier = DocumentSupportTier.A
    elif length >= 200:
        support_tier = DocumentSupportTier.B
    elif length > 0:
        support_tier = DocumentSupportTier.C
    else:
        support_tier = DocumentSupportTier.D

    table_extraction_quality = assess_table_quality(canonical_md)
    garbled_text_rate = detect_garbled_text(canonical_md)
    blank_ratio = canonical_md.count("\n\n\n") / max(length, 1)
    truncation_suspicion = detect_truncation(
        canonical_md, result.metadata.get("file_size", 0)
    )
    image_density = result.metadata.get("image_count", 0) / max(paragraph_count, 1)
    ocr_used = "ocr" in result.metadata.get("tool_chain", [])

    blocking_reasons: list[str] = []
    if length == 0:
        blocking_reasons.append("Empty canonical markdown")
    if garbled_text_rate > 0.1:
        blocking_reasons.append(f"High garbled text rate: {garbled_text_rate:.1%}")
    if table_extraction_quality < 0.5:
        blocking_reasons.append("Table extraction quality below threshold")
    if truncation_suspicion:
        blocking_reasons.append("Document may be truncated")
    if blank_ratio > 0.05:
        blocking_reasons.append("Excessive blank regions")

    if support_tier in (DocumentSupportTier.A, DocumentSupportTier.B) and not blocking_reasons:
        recommended = PublishStatus.PUBLISHED
    elif support_tier == DocumentSupportTier.D or len(blocking_reasons) >= 2:
        recommended = PublishStatus.QUARANTINED
    else:
        recommended = PublishStatus.PENDING_REVIEW

    return QualityReport(
        doc_id=doc_id,
        support_tier=support_tier,
        conversion_score=score,
        ocr_used=ocr_used,
        garbled_text_rate=round(garbled_text_rate, 4),
        blank_ratio=round(min(blank_ratio, 1.0), 4),
        table_extraction_quality=table_extraction_quality,
        image_density=round(image_density, 4),
        source_canonical_length_mismatch=0.0,
        truncation_suspicion=truncation_suspicion,
        recommended_review_status=recommended,
        blocking_reasons=blocking_reasons,
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Pure review executor
# ──────────────────────────────────────────────────────────────────────────────


def run_review_stage(
    inp: ReviewStageInput,
    agent_reviewer,
    agent_review_cache=None,
) -> ReviewStageOutput:
    """Pure executor for the agent_review logical stage.

    No DB required.  Cache is optional (may be None).
    """
    from intake_runtime.agent_review_cache import build_cache_key, _ttl_for_review

    if inp.quality_report is None:
        output = ReviewStageOutput(
            schema_version=inp.schema_version,
            input_hash="",
            result_hash="",
            agent_review=None,
        )
        output.input_hash = compute_input_hash(inp)
        output.result_hash = compute_result_hash(output)
        return output

    reviewer_model = getattr(getattr(agent_reviewer, "_config", None), "model", "")
    cache_key = build_cache_key(
        canonical_content=inp.canonical_content,
        quality_report=inp.quality_report,
        collection_id=inp.collection_id,
        authority_level=inp.collection_authority_level,
        model=reviewer_model,
    )

    cached_review = (
        agent_review_cache.get(cache_key)
        if agent_review_cache is not None
        else None
    )

    review_context: dict[str, Any] = {}
    generated_at = datetime.now(timezone.utc).isoformat()
    reviewer_config = getattr(agent_reviewer, "_config", None)

    def event_hook(**event: Any) -> None:
        if event.get("event_type") == "review.started":
            review_context["request"] = {
                "model": event.get("payload", {}).get("model"),
                "prompt_excerpt": event.get("payload", {}).get("prompt_excerpt"),
                "canonical_excerpt": event.get("payload", {}).get("canonical_excerpt"),
            }
        elif event.get("event_type") == "review.completed":
            review_context["response"] = event.get("payload", {})

    if cached_review is not None:
        agent_review = cached_review.model_copy(update={"doc_id": inp.preliminary_doc_id})
        cache_hit = True
    else:
        agent_review = agent_reviewer.review(
            doc_id=inp.preliminary_doc_id,
            canonical_content=inp.canonical_content,
            quality_report=inp.quality_report,
            event_hook=event_hook,
        )
        if agent_review_cache is not None:
            ttl = _ttl_for_review(agent_review)
            cache_value = agent_review.model_copy(update={"doc_id": ""})
            agent_review_cache.set(cache_key, cache_value, ttl_seconds=ttl)
        cache_hit = False

    agent_review = _normalize_review_findings(
        agent_review=agent_review,
        source_file_id=inp.source_file_id,
        parse_snapshot_id=inp.parse_snapshot_id,
    )

    # Extract LLM call records if available (attached by DeepSeekAgentReviewer)
    llm_records: list[Any] = getattr(agent_review, "_llm_call_records", [])
    if llm_records:
        review_context["llm_call_records"] = [
            {
                "subtask_name": r.subtask_name,
                "provider": r.provider,
                "model_name": r.model_name,
                "model_version": r.model_version,
                "prompt_version": r.prompt_version,
                "request_hash": r.request_hash,
                "response_hash": r.response_hash,
                "input_token_count": r.input_token_count,
                "output_token_count": r.output_token_count,
                "total_token_count": r.total_token_count,
                "latency_ms": r.latency_ms,
                "status": r.status,
                "error_code": r.error_code,
                "retry_count": r.retry_count,
                "json_parse_success": r.json_parse_success,
                "schema_validation_success": r.schema_validation_success,
            }
            for r in llm_records
        ]

    review_context["artifact_metadata"] = {
        "review_model": getattr(reviewer_config, "model", ""),
        "prompt_version": getattr(reviewer_config, "prompt_version", ""),
        "artifact_schema_version": getattr(reviewer_config, "artifact_schema_version", "v2"),
        "generated_at": generated_at,
        "source_file_id": inp.source_file_id,
        "parse_snapshot_id": inp.parse_snapshot_id,
    }

    output = ReviewStageOutput(
        schema_version=inp.schema_version,
        input_hash="",
        result_hash="",
        agent_review=agent_review,
        cache_hit=cache_hit,
        review_context=review_context,
    )
    output.input_hash = compute_input_hash(inp)
    output.result_hash = compute_result_hash(output)
    return output


def _normalize_review_findings(
    *,
    agent_review: AgentReview,
    source_file_id: str,
    parse_snapshot_id: str,
) -> AgentReview:
    normalized: list[AnchoredFinding] = []
    for finding in agent_review.anchored_findings:
        source_quote = (finding.source_quote or "").strip()
        problem_summary = (finding.problem_summary or "").strip()
        if not source_quote or not problem_summary:
            continue
        normalized_problem = _normalize_finding_text(problem_summary)
        normalized_quote = _normalize_finding_text(source_quote)
        finding_id = hashlib.sha256(
            f"{source_file_id}|{parse_snapshot_id}|{normalized_problem}|{normalized_quote}".encode("utf-8")
        ).hexdigest()
        normalized.append(
            AnchoredFinding(
                finding_id=finding_id,
                source_quote=source_quote,
                problem_summary=problem_summary,
                severity=(finding.severity or "medium"),
                confidence=max(0.0, min(1.0, float(finding.confidence))),
            )
        )
    return agent_review.model_copy(update={"anchored_findings": normalized})


def _normalize_finding_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


# ──────────────────────────────────────────────────────────────────────────────
#  Pure publishing executor
# ──────────────────────────────────────────────────────────────────────────────


def run_publishing_stage(
    inp: PublishingStageInput,
    *,
    document_repo=None,
    policy_repo=None,
    persist_fn=None,
) -> PublishingStageOutput:
    """Pure executor for the publishing logical stage.

    Side effects: writes sidecar files to REALITY_RAG_SIDECAR_DIR.
    DB: optional (if repos are None, persist is skipped).
    """
    from datetime import datetime, timezone

    from intake_runtime.index_assets import build_index_asset_bundle
    from intake_runtime.pipeline_utils import build_document_asset_paths

    result = inp.conversion_result
    if result is None or result.conversion_status != ConversionStatus.SUCCESS:
        output = PublishingStageOutput(
            schema_version=inp.schema_version,
            input_hash="",
            result_hash="",
        )
        output.input_hash = compute_input_hash(inp)
        output.result_hash = compute_result_hash(output)
        return output

    target_doc_id = inp.final_doc_id or inp.preliminary_doc_id

    # Build asset paths
    asset_paths = build_document_asset_paths(
        inp.collection_id, target_doc_id
    )

    # Build canonical metadata (using legacy doc_id for compat)
    canonical_metadata = _build_canonical_metadata_from_input(inp, asset_paths)

    # Write assets
    _write_text_asset(asset_paths["canonical_md"], result.canonical_md or "")
    _write_json_asset(
        asset_paths["canonical_meta"], canonical_metadata.model_dump(mode="json")
    )

    if inp.quality_report is not None:
        _write_json_asset(
            asset_paths["quality_report"], inp.quality_report.model_dump(mode="json")
        )
    if inp.agent_review is not None:
        _write_json_asset(
            asset_paths["agent_review"], inp.agent_review.model_dump(mode="json")
        )

    human_review = {
        "doc_id": target_doc_id,
        "status": (
            "not_required" if inp.publish_status == PublishStatus.PUBLISHED else "pending"
        ),
        "note": "",
        "history": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_asset(asset_paths["human_review"], human_review)

    # review_context (from ReviewStageOutput if available)
    if inp.review_context:
        _write_json_asset(asset_paths["review_context"], inp.review_context)

    # processing_record
    processing_record = _build_processing_record(
        doc_id=target_doc_id,
        job_id=inp.intake_job_id,
        collection_id=inp.collection_id,
        result=result,
        source_hash=inp.source_hash,
        asset_paths=asset_paths,
    )
    _write_json_asset(asset_paths["processing_record"], processing_record.model_dump(mode="json"))

    # Build index asset bundle
    bundle = build_index_asset_bundle(
        canonical_metadata=canonical_metadata,
        canonical_content=result.canonical_md or "",
        index_version=inp.index_version,
    )
    _write_json_asset(asset_paths["chunk_manifest"], bundle.model_dump(mode="json"))
    _write_json_asset(
        asset_paths["opensearch_records"],
        [record.model_dump(mode="json") for record in bundle.opensearch_records],
    )
    _write_json_asset(
        asset_paths["qdrant_points"],
        [point.model_dump(mode="json") for point in bundle.qdrant_points],
    )

    # Persist to DB (optional) — delegated to publishing_domain
    document_persisted = False
    policy_persisted = False
    if document_repo is not None:
        if persist_fn is None:
            raise RuntimeError("persist_fn is required when document_repo is provided")
        document_persisted, policy_persisted = persist_fn(
            canonical_metadata,
            document_repo=document_repo,
            policy_repo=policy_repo,
            collection_authority_level=inp.collection_authority_level,
        )

    output = PublishingStageOutput(
        schema_version=inp.schema_version,
        input_hash="",
        result_hash="",
        asset_paths=asset_paths,
        asset_bundle=bundle,
        canonical_metadata=canonical_metadata,
        document_persisted=document_persisted,
        policy_persisted=policy_persisted,
    )
    output.input_hash = compute_input_hash(inp)
    output.result_hash = compute_result_hash(output)
    return output


def _build_canonical_metadata_from_input(
    inp: PublishingStageInput, asset_paths: dict[str, str]
) -> Any:
    from reality_rag_contracts import CanonicalMetadata

    result = inp.conversion_result
    quality_summary = "No quality report"
    if inp.quality_report is not None:
        quality_summary = (
            f"Tier {inp.quality_report.support_tier.value}: score {inp.quality_report.conversion_score:.2f}; "
            f"recommended {inp.quality_report.recommended_review_status.value}"
        )

    processing_summary = "No conversion result"
    if result is not None:
        extension = result.metadata.get("extension", "")
        processing_summary = (
            f"{result.conversion_status.value} via {result.metadata.get('converter', 'unknown')} {extension}"
        ).strip()

    target_doc_id = inp.final_doc_id or inp.preliminary_doc_id

    return CanonicalMetadata(
        tenant_id=inp.tenant_id,
        collection_id=inp.collection_id,
        doc_id=target_doc_id,
        logical_document_id=inp.logical_document_id,
        source_hash=inp.source_hash,
        version=inp.version,
        publish_status=inp.publish_status,
        index_status=(
            IndexStatus.NOT_INDEXED
            if inp.publish_status != PublishStatus.PUBLISHED
            else IndexStatus.INDEXING
        ),
        authority_level=inp.collection_authority_level,
        quality_summary=quality_summary[:2048],
        processing_summary=processing_summary[:2048],
        asset_paths=asset_paths,
    )


def _write_text_asset(asset_path: str, content: str) -> None:
    path = Path(asset_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json_asset(asset_path: str, payload: dict[str, Any]) -> None:
    import json

    path = Path(asset_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_processing_record(*, doc_id, job_id, collection_id, result, source_hash, asset_paths):
    from datetime import datetime, timezone
    from reality_rag_contracts import ProcessingRecord

    return ProcessingRecord(
        doc_id=doc_id,
        job_id=job_id,
        collection_id=collection_id,
        source_file_path=result.source_file_path,
        source_hash=source_hash,
        conversion_status=result.conversion_status,
        tool_chain=[result.metadata.get("converter", "unknown")],
        tool_versions={},
        parameters={},
        warnings=result.warnings,
        error_message=result.error_message,
        published_asset_paths=asset_paths,
        created_at=datetime.now(timezone.utc),
    )
