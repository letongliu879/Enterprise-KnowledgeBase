"""Adapters between StageContext and stage schemas."""

from __future__ import annotations

from reality_rag_contracts import PublishStatus

from .hash_utils import compute_input_hash, compute_result_hash
from .protocol import StageContext
from .schemas import (
    ConversionStageInput,
    ConversionStageOutput,
    PublishingStageInput,
    PublishingStageOutput,
    ReviewStageInput,
    ReviewStageOutput,
    VersionConflictInfo,
)


def ctx_to_conversion_input(ctx: StageContext) -> ConversionStageInput:
    return ConversionStageInput(
        schema_version="v1",
        intake_job_id=ctx.job_id,
        collection_id=ctx.collection_id,
        source_file_path=ctx.source_file_path,
        tenant_id=(ctx.tenant.tenant_id if ctx.tenant is not None else "default"),
        collection_authority_level=(
            ctx.collection.authority_level if ctx.collection is not None else 0
        ),
        index_version=ctx.index_version,
        source_hash=ctx.source_hash,
        source_file_id=ctx.source_file_id,
        trace_id=ctx.job_id,
        source_metadata={
            "source_file_id": ctx.source_file_id,
            "object_id": ctx.object_id,
            "content_hash": ctx.content_hash,
            "filename": ctx.source_file_path,
        },
    )


def conversion_output_to_ctx(output: ConversionStageOutput, ctx: StageContext) -> StageContext:
    ctx.result = output.conversion_result
    ctx.quality_report = output.quality_report
    ctx.logical_document_id = output.logical_document_id
    ctx.source_hash = output.source_hash
    ctx.version = output.version
    ctx.skipped = output.dedup_skipped
    ctx.skip_reason = output.skip_reason or ""
    ctx.doc_id = output.preliminary_doc_id
    ctx.parse_snapshot_id = output.parse_snapshot_id
    return ctx


def ctx_to_conversion_output(ctx: StageContext) -> ConversionStageOutput:
    inp = ctx_to_conversion_input(ctx)
    input_hash = compute_input_hash(inp)
    version_conflict = None
    if ctx.version > 1 and ctx.document_repo is not None:
        latest = ctx.document_repo.get_latest_by_logical_id(
            ctx.logical_document_id, ctx.collection_id
        )
        if latest is not None:
            version_conflict = VersionConflictInfo(
                logical_document_id=ctx.logical_document_id,
                existing_version=latest.version,
                proposed_version=ctx.version,
                existing_doc_id=latest.doc_id,
                conflict_type="new_version",
            )

    output = ConversionStageOutput(
        schema_version="v1",
        input_hash=input_hash,
        result_hash="",
        conversion_result=ctx.result,
        quality_report=ctx.quality_report,
        preliminary_doc_id=ctx.doc_id,
        logical_document_id=ctx.logical_document_id,
        version=ctx.version,
        source_hash=ctx.source_hash,
        version_conflict=version_conflict,
        dedup_skipped=ctx.skipped,
        skip_reason=ctx.skip_reason or None,
        parse_snapshot_id=(
            str((ctx.result.metadata or {}).get("parse_snapshot_id") or getattr(ctx, "parse_snapshot_id", "")).strip()
            if ctx.result is not None
            else getattr(ctx, "parse_snapshot_id", "")
        ),
    )
    output.result_hash = compute_result_hash(output)
    return output


def ctx_to_review_input(ctx: StageContext) -> ReviewStageInput:
    result = ctx.result
    quality = ctx.quality_report
    return ReviewStageInput(
        schema_version="v1",
        intake_job_id=ctx.job_id,
        collection_id=ctx.collection_id,
        source_file_id=ctx.source_file_id,
        preliminary_doc_id=ctx.doc_id,
        logical_document_id=ctx.logical_document_id,
        parse_snapshot_id=str(getattr(ctx, "parse_snapshot_id", "") or ""),
        canonical_content=(result.canonical_md if result is not None else ""),
        quality_report=quality,
        collection_authority_level=(
            ctx.collection.authority_level if ctx.collection is not None else 0
        ),
        review_model="",
    )


def review_output_to_ctx(output: ReviewStageOutput, ctx: StageContext) -> StageContext:
    ctx.agent_review = output.agent_review
    ctx.review_context = output.review_context
    return ctx


def ctx_to_review_output(ctx: StageContext) -> ReviewStageOutput:
    inp = ctx_to_review_input(ctx)
    input_hash = compute_input_hash(inp)

    output = ReviewStageOutput(
        schema_version="v1",
        input_hash=input_hash,
        result_hash="",
        agent_review=ctx.agent_review,
        cache_hit=False,
        review_context=getattr(ctx, "review_context", {}),
    )
    output.result_hash = compute_result_hash(output)
    return output


def ctx_to_publishing_input(ctx: StageContext) -> PublishingStageInput:
    return PublishingStageInput(
        schema_version="v1",
        intake_job_id=ctx.job_id,
        collection_id=ctx.collection_id,
        preliminary_doc_id=ctx.doc_id,
        final_doc_id=ctx.final_doc_id,
        logical_document_id=ctx.logical_document_id,
        version=ctx.version,
        source_hash=ctx.source_hash,
        tenant_id=(ctx.tenant.tenant_id if ctx.tenant is not None else "default"),
        collection_authority_level=(
            ctx.collection.authority_level if ctx.collection is not None else 0
        ),
        index_version=ctx.index_version,
        conversion_result=ctx.result,
        quality_report=ctx.quality_report,
        agent_review=ctx.agent_review,
        review_context=getattr(ctx, "review_context", {}),
        publish_status=(ctx.publish_status or PublishStatus.DRAFT),
    )


def publishing_output_to_ctx(output: PublishingStageOutput, ctx: StageContext) -> StageContext:
    ctx.asset_paths = output.asset_paths
    ctx.asset_bundle = output.asset_bundle
    ctx.canonical_metadata = output.canonical_metadata
    return ctx


def ctx_to_publishing_output(ctx: StageContext) -> PublishingStageOutput:
    inp = ctx_to_publishing_input(ctx)
    input_hash = compute_input_hash(inp)

    output = PublishingStageOutput(
        schema_version="v1",
        input_hash=input_hash,
        result_hash="",
        asset_paths=ctx.asset_paths,
        asset_bundle=ctx.asset_bundle,
        canonical_metadata=ctx.canonical_metadata,
        document_persisted=(ctx.document_repo is not None and ctx.canonical_metadata is not None),
        policy_persisted=(ctx.policy_repo is not None and ctx.canonical_metadata is not None),
    )
    output.result_hash = compute_result_hash(output)
    return output
