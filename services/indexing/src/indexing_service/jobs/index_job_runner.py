from __future__ import annotations

from pathlib import Path
import json
import re
from time import perf_counter
from hashlib import sha256

import ragflow_runtime
from indexing_service._compat import utc_now
from indexing_service.contracts import IndexBuildRequestedCommand
from reality_rag_contracts.indexing_models import ChunkRecord
from indexing_service.embedding.vector_text_builder import VectorTextBuilder
from indexing_service.parser_profiles import get_parser_profile
from indexing_service.governance_assets import (
    governance_confirmed_tags,
    governance_final_doc_id,
    governance_metadata,
    governance_publish_version,
    governance_published_document_state,
    governance_visibility,
    load_governance_assets,
)
from indexing_service.metrics import InMemoryIndexingMetrics
from indexing_service.repository import IndexingRepository
from indexing_service.security import IndexingSecurity
from indexing_service.trace_recorder import IndexingTraceRecorder
from indexing_service.vendor.ragflow_pdf_chunk_metadata import finalize_pdf_chunk
from indexing_service.writers.chunk_registry_writer import ChunkRegistryWriter
from rag.nlp import rag_tokenizer
from reality_rag_contracts import IndexedDocumentState


class IndexJobRunner:
    def __init__(
        self,
        repository: IndexingRepository,
        metrics: InMemoryIndexingMetrics | None = None,
        security: IndexingSecurity | None = None,
    ) -> None:
        self.repository = repository
        self.vector_text_builder = VectorTextBuilder()
        self.chunk_registry_writer = ChunkRegistryWriter()
        self.trace = IndexingTraceRecorder()
        self.metrics = metrics or InMemoryIndexingMetrics()
        self.security = security or IndexingSecurity()

    def accept(self, command: IndexBuildRequestedCommand) -> dict[str, str]:
        started_at = perf_counter()
        self.metrics.incr("indexing.materialization.requests_total")
        self.trace.write_run_trace(
            trace_id=command.trace_id,
            run_kind="indexing_materialization",
            tenant_id=command.tenant_id,
            collection_id=command.collection_id,
            principal_id="publishing-worker",
            query_id=command.build_request_id,
            index_version_id=command.target_index_version_id or "pending",
            profile_id=command.index_profile_id,
            root_status="RUNNING",
            debug_ref=f"dbg://indexing/materialization/{command.build_request_id}",
            result_count=0,
            extra={
                "final_doc_id": command.final_doc_id,
                "parse_snapshot_id": command.parse_snapshot_id,
            },
        )
        self.trace.write_run_step(
            trace_id=command.trace_id,
            step_name="index_build_requested",
            status="STARTED",
            summary=(
                f"build_request_id={command.build_request_id};"
                f"final_doc_id={command.final_doc_id};"
                f"parse_snapshot_id={command.parse_snapshot_id}"
            ),
        )
        index_version_id = command.target_index_version_id or f"idxv_{command.collection_id}_active"
        snapshot = self.repository.get_parse_snapshot(command.parse_snapshot_id)
        chunk_profile_id = snapshot.chunk_profile_id or snapshot.parser_id or command.index_profile_id
        record = self.repository.create_job(
            build_job_id=f"ibj_{command.build_request_id}",
            build_request_id=command.build_request_id,
            tenant_id=command.tenant_id,
            collection_id=command.collection_id,
            final_doc_id=command.final_doc_id,
            index_version_id=index_version_id,
            idempotency_key=command.idempotency_key,
            index_profile_id=command.index_profile_id,
            chunk_profile_id=chunk_profile_id,
        )
        self.trace.write_run_step(
            trace_id=command.trace_id,
            step_name="index_build_job_created",
            status="SUCCEEDED",
            summary=f"build_job_id={record.build_job_id};index_version_id={index_version_id};chunk_profile_id={chunk_profile_id}",
        )
        try:
            governance_assets = load_governance_assets(
                governance_overlay_ref=command.governance_overlay_ref,
                approval_decision_ref=command.approval_decision_ref,
                metadata_ref=command.metadata_ref,
            )
            resolved_final_doc_id = governance_final_doc_id(
                command_final_doc_id=command.final_doc_id,
                overlay=governance_assets.overlay,
            )
            resolved_publish_version = governance_publish_version(
                command_publish_version=command.publish_version,
                overlay=governance_assets.overlay,
            )
            resolved_visibility = governance_visibility(
                command_visibility=command.visibility,
                source_metadata=command.source_metadata,
                overlay=governance_assets.overlay,
            )
            resolved_confirmed_tags = governance_confirmed_tags(
                command_tags=command.confirmed_tags,
                overlay=governance_assets.overlay,
                approval=governance_assets.approval,
            )
            resolved_document_metadata = governance_metadata(
                snapshot_document_metadata=snapshot.document_metadata,
                external_document_metadata=governance_assets.document_metadata,
                overlay=governance_assets.overlay,
                approval=governance_assets.approval,
            )
            chunk_records = self._build_chunks(
                command=command,
                index_version_id=index_version_id,
                resolved_final_doc_id=resolved_final_doc_id,
                resolved_publish_version=resolved_publish_version,
                resolved_visibility=resolved_visibility,
                resolved_confirmed_tags=resolved_confirmed_tags,
                resolved_document_metadata=resolved_document_metadata,
                published_document_state=governance_published_document_state(governance_assets.approval),
            )
            self.repository.replace_chunks(
                index_version_id,
                chunk_records,
            )
            visible_chunk_count = len([chunk for chunk in chunk_records if chunk.available_int >= 1])
            hidden_chunk_count = len(chunk_records) - visible_chunk_count
            has_toc_chunk = any(chunk.metadata.get("is_toc_chunk") for chunk in chunk_records)
            has_parent_chunk = any(chunk.metadata.get("is_parent_chunk") for chunk in chunk_records)
            indexed_document = self.repository.upsert_indexed_document(
                indexed_document_id=f"idxdoc_{resolved_final_doc_id}_{index_version_id}",
                final_doc_id=resolved_final_doc_id,
                collection_id=command.collection_id,
                index_version=index_version_id,
                parser_id=snapshot.parser_id,
                source_suffix=snapshot.source_suffix,
                chunk_count=len(chunk_records),
                embedding_count=len(chunk_records),
                visible_chunk_count=visible_chunk_count,
                hidden_chunk_count=hidden_chunk_count,
                has_toc_chunk=has_toc_chunk,
                has_parent_chunk=has_parent_chunk,
                document_metadata=dict(resolved_document_metadata),
                outline=_indexed_document_outline(snapshot, chunk_records),
                state=IndexedDocumentState.CANDIDATE,
            )
            self.trace.write_trace_artifact(
                trace_id=command.trace_id,
                artifact_ref=f"indexed_document:{indexed_document.indexed_document_id}",
                artifact_kind="indexed_document",
                summary=(
                    f"indexed_document_id={indexed_document.indexed_document_id};"
                    f"parser_id={indexed_document.parser_id};"
                    f"source_suffix={indexed_document.source_suffix};"
                    f"visible_chunk_count={indexed_document.visible_chunk_count};"
                    f"hidden_chunk_count={indexed_document.hidden_chunk_count};"
                    f"has_toc_chunk={str(indexed_document.has_toc_chunk).lower()};"
                    f"has_parent_chunk={str(indexed_document.has_parent_chunk).lower()}"
                ),
            )
            backend_counts = self.repository.write_index_assets(
                indexed_document_id=indexed_document.indexed_document_id,
                index_version_id=index_version_id,
                final_doc_id=resolved_final_doc_id,
                canonical_source=command.canonical_asset_ref,
                chunks=chunk_records,
            )
            # Contract: request_type="publish" or "reindex" means build + activate atomically.
            # If caller wants build-only (e.g., staging), use request_type="build".
            request_type_value = str(command.request_type).lower()
            if request_type_value in ("publish", "reindex"):
                activated = self.repository.activate(index_version_id)
                self.repository.upsert_indexed_document(
                    indexed_document_id=indexed_document.indexed_document_id,
                    final_doc_id=resolved_final_doc_id,
                    collection_id=command.collection_id,
                    index_version=index_version_id,
                    parser_id=indexed_document.parser_id,
                    source_suffix=indexed_document.source_suffix,
                    chunk_count=indexed_document.chunk_count,
                    embedding_count=indexed_document.embedding_count,
                    visible_chunk_count=indexed_document.visible_chunk_count,
                    hidden_chunk_count=indexed_document.hidden_chunk_count,
                    has_toc_chunk=indexed_document.has_toc_chunk,
                    has_parent_chunk=indexed_document.has_parent_chunk,
                    document_metadata=dict(indexed_document.document_metadata),
                    outline=list(indexed_document.outline),
                    state=IndexedDocumentState.ACTIVE,
                )
                self.trace.write_run_step(
                    trace_id=command.trace_id,
                    step_name="index_version_activated",
                    status="SUCCEEDED",
                    summary=(
                        f"index_version_id={activated.index_version_id};"
                        f"previous_active_index_version_id={activated.previous_active_index_version_id or ''}"
                    ),
                )
                self._purge_retrieval_cache(
                    tenant_id=command.tenant_id,
                    collection_id=command.collection_id,
                    doc_id=resolved_final_doc_id,
                    trace_id=command.trace_id,
                )
                self._sync_index_projection_to_retrieval(
                    tenant_id=command.tenant_id,
                    collection_id=command.collection_id,
                    index_version_id=index_version_id,
                    final_doc_id=resolved_final_doc_id,
                    chunk_records=chunk_records,
                    trace_id=command.trace_id,
                )
            chunk_count = len(self.repository.list_active_chunks())
            duration_ms = int((perf_counter() - started_at) * 1000)
            self.metrics.incr("indexing.materialization.succeeded_total")
            self.metrics.incr(f"indexing.materialization.profile.{command.index_profile_id}.total")
            self.metrics.observe_ms("indexing.materialization.duration_ms", duration_ms)
            self.metrics.observe_ms(
                f"indexing.materialization.profile.{command.index_profile_id}.duration_ms",
                duration_ms,
            )
            self.trace.write_run_step(
                trace_id=command.trace_id,
                step_name="index_chunks_materialized",
                status="SUCCEEDED",
                summary=(
                    f"index_version_id={index_version_id};"
                    f"chunk_count={chunk_count};"
                    f"opensearch_record_count={backend_counts['opensearch_record_count']};"
                    f"qdrant_point_count={backend_counts['qdrant_point_count']}"
                ),
            )
            self.trace.write_trace_artifact(
                trace_id=command.trace_id,
                artifact_ref=f"art://indexing/{record.build_job_id}/index-assets",
                artifact_kind="index_asset_bundle",
                summary=(
                    f"indexed_document_id={indexed_document.indexed_document_id};"
                    f"index_version_id={index_version_id};"
                    f"chunk_count={chunk_count};"
                    f"opensearch_record_count={backend_counts['opensearch_record_count']};"
                    f"qdrant_point_count={backend_counts['qdrant_point_count']}"
                ),
            )
            self.trace.write_run_trace(
                trace_id=command.trace_id,
                run_kind="indexing_materialization",
                tenant_id=command.tenant_id,
                collection_id=command.collection_id,
                principal_id="publishing-worker",
                query_id=command.build_request_id,
                index_version_id=index_version_id,
                profile_id=command.index_profile_id,
                root_status="SUCCEEDED",
                debug_ref=f"dbg://indexing/materialization/{command.build_request_id}",
                result_count=chunk_count,
                extra={
                    "final_doc_id": command.final_doc_id,
                    "parse_snapshot_id": command.parse_snapshot_id,
                    "build_job_id": record.build_job_id,
                },
            )
            completed_record = self.repository.mark_job_completed(record.build_job_id)
            return {
                "build_job_id": completed_record.build_job_id,
                "status": completed_record.status,
                "accepted_command": completed_record.accepted_command,
            }
        except Exception as exc:
            self.repository.mark_job_completed(record.build_job_id, error_message=type(exc).__name__)
            raise

    def _build_chunks(
        self,
        *,
        command: IndexBuildRequestedCommand,
        index_version_id: str,
        resolved_final_doc_id: str,
        resolved_publish_version: str,
        resolved_visibility: str,
        resolved_confirmed_tags: list[str],
        resolved_document_metadata: dict[str, object],
        published_document_state: str,
    ):
        snapshot = self.repository.get_parse_snapshot(command.parse_snapshot_id)
        self.trace.write_run_step(
            trace_id=command.trace_id,
            step_name="parse_snapshot_loaded",
            status="SUCCEEDED",
            summary=(
                f"parse_snapshot_id={snapshot.parse_snapshot_id};"
                f"parser_id={snapshot.parser_id};"
                f"upstream_chunk_count={len(snapshot.upstream_chunks)}"
            ),
        )
        if not snapshot.upstream_chunks:
            raise ValueError(
                f"ParseSnapshot '{command.parse_snapshot_id}' does not contain usable upstream chunks; "
                "formal indexing must reuse a successful parse preview result."
            )
        title = self._title(snapshot, command.final_doc_id)
        self.trace.write_trace_artifact(
            trace_id=command.trace_id,
            artifact_ref=f"parse_snapshot:{snapshot.parse_snapshot_id}:upstream_chunks",
            artifact_kind="upstream_chunks",
            summary=f"chunk_count={len(snapshot.upstream_chunks)};title={title}",
        )
        self.trace.write_run_step(
            trace_id=command.trace_id,
            step_name="token_chunks_assembled",
            status="SUCCEEDED",
            summary=f"assembled_chunk_count={len(snapshot.upstream_chunks)};section_count={len(snapshot.upstream_chunks)}",
        )
        upstream_chunks = self._apply_pre_publish_edits(
            snapshot.upstream_chunks,
            command=command,
            trace_id=command.trace_id,
        )
        self.metrics.observe_ms(
            "indexing.materialization.chunk_count",
            len(upstream_chunks),
        )
        governance = self.security.authorize_index_build(
            tenant_id=command.tenant_id,
            collection_id=command.collection_id,
            source_metadata={
                **command.source_metadata,
                "visibility": resolved_visibility,
            },
        )
        document_index_revision_id = f"dir_{resolved_final_doc_id}_{resolved_publish_version}"
        allowed_principal_ids = _csv_values(command.source_metadata.get("allowed_principal_ids"))
        allowed_groups = _csv_values(command.source_metadata.get("allowed_groups"))
        filename = command.source_metadata.get("filename") or snapshot.source_filename or Path(command.source_binary_ref).name
        kb_id = command.collection_id
        source_ids = [command.source_file_id]
        pagerank_fea = _optional_int(command.source_metadata.get("pagerank_fea"))
        if pagerank_fea is None:
            pagerank_fea = _optional_int(command.source_metadata.get("pagerank"))

        profile = get_parser_profile(snapshot.parser_profile_id) or get_parser_profile(snapshot.parser_id)
        embedding_text_policy = profile.embedding_text_policy if profile else "display_text"
        chunk_records: list[ChunkRecord] = []
        mother_chunk_ids: set[str] = set()
        for ordinal, chunk in enumerate(upstream_chunks, start=1):
            chunk_id = f"chk_{resolved_final_doc_id}_{index_version_id}_{ordinal:04d}"
            normalized_chunk_metadata = finalize_pdf_chunk(dict(chunk))
            created_at = utc_now()
            create_time = created_at.strftime("%Y-%m-%d %H:%M:%S")
            create_timestamp_flt = created_at.timestamp()
            display_text = str(chunk.get("content_with_weight", "")).strip()
            section_path = _section_path_from_chunk(
                normalized_chunk_metadata,
                title,
                parser_id=snapshot.parser_id,
            )
            source_block_ids = _source_block_ids_from_chunk(normalized_chunk_metadata, ordinal)
            vector_text = self.vector_text_builder.build(
                title=title,
                display_text=display_text,
                upstream_chunk=normalized_chunk_metadata,
                embedding_text_policy=embedding_text_policy,
                section_path=section_path,
            )
            title_text = self.vector_text_builder.build_title_text(
                title=title,
                filename=filename,
                upstream_chunk=normalized_chunk_metadata,
            )
            embedding_title_weight = self.vector_text_builder.title_weight(
                parser_config=snapshot.parser_config,
            )
            doc_name = str(normalized_chunk_metadata.get("docnm_kwd") or title_text).strip() or "Title"
            title_tokens = _normalized_token_string(
                normalized_chunk_metadata.get("title_tks"),
                fallback=rag_tokenizer.tokenize(doc_name),
            )
            title_small_tokens = _normalized_token_string(
                normalized_chunk_metadata.get("title_sm_tks"),
                fallback=rag_tokenizer.fine_grained_tokenize(title_tokens),
            )
            content_tokens = _normalized_token_string(
                normalized_chunk_metadata.get("content_ltks"),
                fallback=rag_tokenizer.tokenize(display_text),
            )
            content_small_tokens = _normalized_token_string(
                normalized_chunk_metadata.get("content_sm_ltks"),
                fallback=rag_tokenizer.fine_grained_tokenize(content_tokens),
            )
            authors_tokens = _normalized_token_string(normalized_chunk_metadata.get("authors_tks"))
            authors_small_tokens = _normalized_token_string(normalized_chunk_metadata.get("authors_sm_tks"))
            important_keywords = _normalized_string_list(normalized_chunk_metadata.get("important_kwd"))
            important_tokens = _normalized_token_string(
                normalized_chunk_metadata.get("important_tks"),
                fallback=_tokens_from_keyword_list(normalized_chunk_metadata.get("important_kwd")),
            )
            question_keywords = _normalized_string_list(normalized_chunk_metadata.get("question_kwd"))
            question_tokens = _normalized_token_string(
                normalized_chunk_metadata.get("question_tks"),
                fallback=_tokens_from_question_list(normalized_chunk_metadata.get("question_kwd")),
            )
            tag_features = _normalized_tag_features(normalized_chunk_metadata.get("tag_feas"))
            tag_keywords = _normalized_string_list(normalized_chunk_metadata.get("tag_kwd")) or list(tag_features.keys())
            image_id = str(normalized_chunk_metadata.get("img_id") or "").strip()
            mom_id = _mom_id_from_chunk(normalized_chunk_metadata)
            position_int = _normalized_position_int(normalized_chunk_metadata.get("position_int"))
            page_num_int = _normalized_int_list(normalized_chunk_metadata.get("page_num_int"))
            top_int = _normalized_int_list(normalized_chunk_metadata.get("top_int"))
            keyword_terms = _keyword_terms(
                title=title,
                filename=filename,
                section_path=section_path,
                confirmed_tags=resolved_confirmed_tags,
                display_text=display_text,
                upstream_chunk=normalized_chunk_metadata,
            )
            citation_payload = {
                "collection_id": command.collection_id,
                "final_doc_id": resolved_final_doc_id,
                "section_path": section_path,
                "anchor": _anchor_from_chunk(
                    normalized_chunk_metadata,
                    ordinal,
                    parser_id=snapshot.parser_id,
                ),
            }
            citation_payload.update(
                {
                    key: normalized_chunk_metadata[key]
                    for key in ["position_int", "page_num_int", "top_int", "img_id", "row_id"]
                    if key in normalized_chunk_metadata
                }
            )
            if snapshot.parser_id == "presentation":
                slide_number = _first_page_number(normalized_chunk_metadata)
                if slide_number is not None:
                    citation_payload["slide_number"] = slide_number
                citation_payload["page_kind"] = "slide"
            page_spans = _page_spans_from_citation(citation_payload)
            chunk_metadata = _chunk_metadata(
                normalized_chunk_metadata,
                resolved_document_metadata,
                parser_id=snapshot.parser_id,
            )
            chunk_metadata["governance"] = {
                "final_doc_id": resolved_final_doc_id,
                "visibility": resolved_visibility,
                "confirmed_tags": list(resolved_confirmed_tags),
                "publish_version": resolved_publish_version,
            }
            approval_metadata = resolved_document_metadata.get("approval")
            if isinstance(approval_metadata, dict) and approval_metadata:
                chunk_metadata["approval"] = dict(approval_metadata)
            chunk_payload = ChunkRecord(
                chunk_id=chunk_id,
                record_id=chunk_id,
                kb_id=kb_id,
                tenant_id=command.tenant_id,
                collection_id=command.collection_id,
                final_doc_id=resolved_final_doc_id,
                index_version_id=index_version_id,
                document_index_revision_id=document_index_revision_id,
                chunk_type=_chunk_type_from_upstream(
                    normalized_chunk_metadata,
                    parser_id=snapshot.parser_id,
                    display_text=display_text,
                ),
                doc_type_kwd=str(normalized_chunk_metadata.get("doc_type_kwd") or ""),
                available_int=0 if chunk.get("__hidden__") else 1,
                display_text=display_text,
                content_with_weight=display_text,
                content_ltks=content_tokens,
                content_sm_ltks=content_small_tokens,
                vector_text=vector_text,
                title_text=title_text,
                embedding_text=vector_text,
                embedding_title_weight=embedding_title_weight,
                docnm_kwd=doc_name,
                title_tks=title_tokens,
                title_sm_tks=title_small_tokens,
                authors_tks=authors_tokens,
                authors_sm_tks=authors_small_tokens,
                important_kwd=important_keywords,
                important_tks=important_tokens,
                question_kwd=question_keywords,
                question_tks=question_tokens,
                tag_kwd=tag_keywords,
                tag_feas=tag_features,
                pagerank_fea=pagerank_fea,
                removed_kwd="N",
                source_id=list(source_ids),
                chunk_data=_chunk_data(normalized_chunk_metadata),
                img_id=image_id,
                mom_id=mom_id,
                create_time=create_time,
                create_timestamp_flt=create_timestamp_flt,
                position_int=position_int,
                page_num_int=page_num_int,
                top_int=top_int,
                section_path=section_path,
                page_spans=page_spans,
                source_block_ids=source_block_ids,
                keyword_terms=keyword_terms,
                confirmed_tags=resolved_confirmed_tags,
                visibility=resolved_visibility,
                published_document_state=published_document_state,
                access_control={
                    "allowed_principal_ids": list(governance.allowed_principal_ids or allowed_principal_ids),
                    "allowed_groups": list(governance.allowed_groups or allowed_groups),
                },
                citation_payload=citation_payload,
                lexical_payload={
                    "lexical_text": display_text,
                    "title": title,
                    "section_path": section_path,
                    "keyword_terms": keyword_terms,
                    "governance": {
                        "final_doc_id": resolved_final_doc_id,
                        "visibility": resolved_visibility,
                        "confirmed_tags": list(resolved_confirmed_tags),
                        "publish_version": resolved_publish_version,
                    },
                },
                vector_payload={
                    "embedding_model": self.repository.DEFAULT_EMBEDDING_MODEL,
                    "parser_id": snapshot.parser_id,
                    "source_suffix": snapshot.source_suffix,
                    "title_text": title_text,
                    "embedding_text": vector_text,
                    "embedding_title_weight": embedding_title_weight,
                    "docnm_kwd": doc_name,
                    "governance": {
                        "final_doc_id": resolved_final_doc_id,
                        "visibility": resolved_visibility,
                        "confirmed_tags": list(resolved_confirmed_tags),
                        "publish_version": resolved_publish_version,
                    },
                },
                metadata=chunk_metadata,
                chunk_hash=self.repository.stable_chunk_hash(display_text),
            )
            chunk_records.append(chunk_payload)

            mother_chunk = _mother_chunk_record(
                source_chunk=chunk_payload,
                source_metadata=normalized_chunk_metadata,
            )
            if mother_chunk is not None and mother_chunk.chunk_id not in mother_chunk_ids:
                mother_chunk_ids.add(mother_chunk.chunk_id)
                chunk_records.append(mother_chunk)

        toc_chunk = _toc_chunk_record(
            snapshot=snapshot,
            source_chunk=next((chunk for chunk in reversed(chunk_records) if chunk.available_int >= 1), None),
            visible_chunks=[chunk for chunk in chunk_records if chunk.available_int >= 1],
        )
        if toc_chunk is not None:
            chunk_records.append(toc_chunk)

        return self.chunk_registry_writer.write(chunk_records)

    def _title(self, snapshot, final_doc_id: str) -> str:
        if snapshot.outline:
            root_title = str(snapshot.outline[0]).strip()
            if root_title:
                return root_title
        for line in snapshot.preview_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("# ").strip()
        if snapshot.source_filename:
            stem = Path(snapshot.source_filename).stem.strip()
            if stem:
                return stem
        return Path(final_doc_id).stem

    def _apply_pre_publish_edits(
        self,
        upstream_chunks: list[dict[str, object]],
        *,
        command: IndexBuildRequestedCommand,
        trace_id: str,
    ) -> list[dict[str, object]]:
        """Apply pre-publish chunk edit overlays from repository before materialization.

        Matches revisions to upstream chunks by the upstream chunk's ``id`` field
        against ``revision.base_evidence_id``.  Revisions with ``status != draft``
        are ignored.  This is fail-open: if the repository does not support listing
        revisions, the original upstream chunks are returned unchanged.
        """
        list_revisions = getattr(self.repository, "list_chunk_revisions_by_doc", None)
        if list_revisions is None:
            return list(upstream_chunks)

        revisions = list_revisions(
            doc_id=command.final_doc_id,
            collection_id=command.collection_id,
            status="draft",
        )
        if not revisions:
            return list(upstream_chunks)

        # Build lookup by base_evidence_id
        revision_by_chunk_id: dict[str, Any] = {}
        for revision in revisions:
            revision_by_chunk_id[revision.base_evidence_id] = revision

        modified: list[dict[str, object]] = []
        applied_count = 0
        skipped_count = 0

        for chunk in upstream_chunks:
            chunk_id = str(chunk.get("id") or "").strip()
            revision = revision_by_chunk_id.get(chunk_id) if chunk_id else None

            if revision is None:
                modified.append(dict(chunk))
                continue

            if revision.operation == "delete":
                skipped_count += 1
                continue

            if revision.operation == "hide":
                hidden_chunk = dict(chunk)
                hidden_chunk["__hidden__"] = True
                if revision.content is not None:
                    hidden_chunk["content_with_weight"] = revision.content
                modified.append(hidden_chunk)
                applied_count += 1
                continue

            if revision.operation == "update":
                updated_chunk = dict(chunk)
                if revision.content is not None:
                    updated_chunk["content_with_weight"] = revision.content
                if revision.vector_text is not None:
                    updated_chunk["__vector_text_override__"] = revision.vector_text
                if revision.section_path is not None:
                    updated_chunk["__section_path_override__"] = revision.section_path
                if revision.metadata_patch is not None:
                    metadata = dict(updated_chunk.get("metadata", {}))
                    metadata.update(revision.metadata_patch)
                    updated_chunk["metadata"] = metadata
                modified.append(updated_chunk)
                applied_count += 1
                continue

            # Unknown operation — pass through unchanged
            modified.append(dict(chunk))

        if applied_count or skipped_count:
            self.trace.write_run_step(
                trace_id=trace_id,
                step_name="pre_publish_edits_applied",
                status="SUCCEEDED",
                summary=(
                    f"applied_count={applied_count};"
                    f"skipped_count={skipped_count};"
                    f"original_count={len(upstream_chunks)};"
                    f"result_count={len(modified)}"
                ),
            )

        return modified

    def _purge_retrieval_cache(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        doc_id: str,
        trace_id: str,
    ) -> None:
        """Purge retrieval cache after index activation. Fail-open."""
        import logging
        import os

        retrieval_url = os.environ.get("RETRIEVAL_SERVICE_URL", "").rstrip("/")
        if not retrieval_url:
            return

        try:
            import httpx

            resp = httpx.post(
                f"{retrieval_url}/internal/cache/purge",
                json={
                    "tenant_id": tenant_id,
                    "collection_id": collection_id,
                    "doc_id": doc_id,
                },
                timeout=10.0,
            )
            if resp.status_code >= 400:
                logging.getLogger(__name__).warning(
                    "retrieval cache purge failed: %s %s",
                    resp.status_code,
                    resp.text,
                )
            else:
                result = resp.json()
                self.trace.write_run_step(
                    trace_id=trace_id,
                    step_name="retrieval_cache_purged",
                    status="SUCCEEDED",
                    summary=f"purged_count={result.get('purged_count', 0)}",
                )
        except Exception:
            logging.getLogger(__name__).warning(
                "retrieval cache purge failed with exception",
                exc_info=True,
            )

    def _sync_index_projection_to_retrieval(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        index_version_id: str,
        final_doc_id: str,
        chunk_records: list[ChunkRecord],
        trace_id: str,
    ) -> None:
        """Sync index projection (chunks + index registry + published doc) to retrieval runtime. Fail-open."""
        import logging
        import os
        import uuid

        retrieval_url = os.environ.get("RETRIEVAL_SERVICE_URL", "").rstrip("/")
        if not retrieval_url:
            return

        try:
            import httpx
            from reality_rag_contracts import IndexProjectionSync, IndexProjectionPayload

            chunks_json = [chunk.model_dump(mode="json", by_alias=True) for chunk in chunk_records]

            # Look up index version record to include registry metadata
            index_version_record = self.repository.get_index_version(index_version_id)

            sync_command = IndexProjectionSync(
                command_id=f"cmd_idxproj_{uuid.uuid4().hex[:12]}",
                trace_id=trace_id,
                idempotency_key=f"idemp_idxproj_{collection_id}_{index_version_id}_{final_doc_id}_{uuid.uuid4().hex[:8]}",
                actor="indexing-service",
                tenant_id=tenant_id,
                target_type="index_projection",
                target_id=f"{collection_id}:{index_version_id}",
                payload=IndexProjectionPayload(
                    collection_id=collection_id,
                    index_version_id=index_version_id,
                    sync_mode="full_replace",
                    doc_id=final_doc_id,
                    chunks=chunks_json,
                    tenant_id=tenant_id,
                    opensearch_index=index_version_record.opensearch_index if index_version_record else None,
                    qdrant_collection=index_version_record.qdrant_collection if index_version_record else None,
                    embedding_model=index_version_record.embedding_model if index_version_record else None,
                    chunk_profile_id=index_version_record.chunk_profile_id if index_version_record else None,
                    index_profile_id=index_version_record.index_profile_id if index_version_record else None,
                    schema_version=index_version_record.schema_version if index_version_record else "v1",
                    published_document_state="PUBLISHED",
                ),
            )

            resp = httpx.post(
                f"{retrieval_url}/internal/index-projections/sync",
                json=sync_command.model_dump(mode="json"),
                timeout=30.0,
            )
            if resp.status_code >= 400:
                logging.getLogger(__name__).warning(
                    "retrieval index projection sync failed: %s %s",
                    resp.status_code,
                    resp.text,
                )
            else:
                result = resp.json()
                self.trace.write_run_step(
                    trace_id=trace_id,
                    step_name="retrieval_index_projection_synced",
                    status="SUCCEEDED",
                    summary=(
                        f"chunks_synced={result.get('chunks_synced', 0)};"
                        f"chunks_removed={result.get('chunks_removed', 0)}"
                    ),
                )
        except Exception:
            logging.getLogger(__name__).warning(
                "retrieval index projection sync failed with exception",
                exc_info=True,
            )

def _csv_values(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return []
    return [value.strip() for value in raw.split(",") if value.strip()]


def _normalized_token_string(value: object, *, fallback: str = "") -> str:
    if isinstance(value, list):
        text = " ".join(str(item).strip() for item in value if str(item).strip()).strip()
    else:
        text = str(value or "").strip()
    return text or str(fallback or "").strip()


def _normalized_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalized_tag_features(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, score in value.items():
        key_text = str(key).strip()
        if not key_text:
            continue
        try:
            normalized[key_text] = float(score)
        except (TypeError, ValueError):
            continue
    return normalized


def _normalized_int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    normalized: list[int] = []
    for item in value:
        if isinstance(item, (int, float)):
            normalized.append(int(item))
    return normalized


def _normalized_position_int(value: object) -> list[tuple[int, int, int, int, int]]:
    if not isinstance(value, list):
        return []
    normalized: list[tuple[int, int, int, int, int]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) < 5:
            continue
        try:
            normalized.append((int(item[0]), int(item[1]), int(item[2]), int(item[3]), int(item[4])))
        except (TypeError, ValueError):
            continue
    return normalized


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _tokens_from_keyword_list(value: object) -> str:
    if isinstance(value, list):
        joined = " ".join(str(item).strip() for item in value if str(item).strip()).strip()
        if joined:
            return rag_tokenizer.tokenize(joined)
    return ""


def _tokens_from_question_list(value: object) -> str:
    if isinstance(value, list):
        joined = "\n".join(str(item).strip() for item in value if str(item).strip()).strip()
        if joined:
            return rag_tokenizer.tokenize(joined)
    return ""


def _mom_id_from_chunk(chunk: dict[str, object]) -> str:
    mom = str(chunk.get("mom_id") or "").strip()
    if mom:
        return mom
    parent_text = str(chunk.get("mom") or chunk.get("mom_with_weight") or "").strip()
    if not parent_text:
        return ""
    return _stable_parent_id(parent_text)


def _mother_chunk_record(
    *,
    source_chunk: ChunkRecord,
    source_metadata: dict[str, object],
) -> ChunkRecord | None:
    parent_text = str(source_metadata.get("mom") or source_metadata.get("mom_with_weight") or "").strip()
    if not parent_text:
        return None
    mom_id = source_chunk.mom_id or _stable_parent_id(parent_text)
    return ChunkRecord(
        chunk_id=mom_id,
        record_id=mom_id,
        kb_id=source_chunk.kb_id,
        tenant_id=source_chunk.tenant_id,
        collection_id=source_chunk.collection_id,
        final_doc_id=source_chunk.final_doc_id,
        index_version_id=source_chunk.index_version_id,
        document_index_revision_id=source_chunk.document_index_revision_id,
        chunk_type="parent",
        doc_type_kwd="text",
        available_int=0,
        display_text=parent_text,
        content_with_weight=parent_text,
        content_ltks=source_chunk.content_ltks,
        content_sm_ltks=source_chunk.content_sm_ltks,
        vector_text=parent_text,
        title_text=source_chunk.title_text,
        embedding_text=parent_text,
        embedding_title_weight=source_chunk.embedding_title_weight,
        docnm_kwd=source_chunk.docnm_kwd,
        title_tks=source_chunk.title_tks,
        title_sm_tks=source_chunk.title_sm_tks,
        authors_tks=source_chunk.authors_tks,
        authors_sm_tks=source_chunk.authors_sm_tks,
        important_kwd=[],
        important_tks="",
        question_kwd=[],
        question_tks="",
        tag_kwd=[],
        tag_feas={},
        pagerank_fea=source_chunk.pagerank_fea,
        removed_kwd="N",
        source_id=list(source_chunk.source_id),
        chunk_data=None,
        img_id="",
        mom_id="",
        create_time=source_chunk.create_time,
        create_timestamp_flt=source_chunk.create_timestamp_flt,
        position_int=list(source_chunk.position_int),
        page_num_int=list(source_chunk.page_num_int),
        top_int=list(source_chunk.top_int),
        section_path=list(source_chunk.section_path),
        page_spans=list(source_chunk.page_spans),
        source_block_ids=[source_chunk.chunk_id],
        keyword_terms=list(source_chunk.keyword_terms),
        confirmed_tags=list(source_chunk.confirmed_tags),
        visibility=source_chunk.visibility,
        published_document_state=source_chunk.published_document_state,
        access_control=dict(source_chunk.access_control),
        citation_payload=dict(source_chunk.citation_payload),
        lexical_payload={
            **source_chunk.lexical_payload,
            "lexical_text": parent_text,
        },
        vector_payload={
            **source_chunk.vector_payload,
            "embedding_text": parent_text,
        },
        metadata={
            **source_chunk.metadata,
            "is_parent_chunk": True,
        },
        chunk_hash="sha256:" + sha256(parent_text.encode("utf-8")).hexdigest(),
    )


def _stable_parent_id(parent_text: str) -> str:
    return sha256(parent_text.encode("utf-8")).hexdigest()[:16]


def _toc_chunk_record(
    *,
    snapshot,
    source_chunk: ChunkRecord | None,
    visible_chunks: list[ChunkRecord],
) -> ChunkRecord | None:
    outline_payload = snapshot.document_metadata.get("outline")
    if not outline_payload:
        return None
    if source_chunk is None:
        return None
    mapped_outline = _outline_with_chunk_ids(outline_payload, visible_chunks)
    toc_text = _toc_json_text(mapped_outline)
    if not toc_text:
        return None
    toc_chunk_id = sha256(f"{snapshot.parse_snapshot_id}:toc".encode("utf-8")).hexdigest()[:16]
    return ChunkRecord(
        chunk_id=toc_chunk_id,
        record_id=toc_chunk_id,
        kb_id=source_chunk.kb_id,
        tenant_id=source_chunk.tenant_id,
        collection_id=source_chunk.collection_id,
        final_doc_id=source_chunk.final_doc_id,
        index_version_id=source_chunk.index_version_id,
        document_index_revision_id=source_chunk.document_index_revision_id,
        chunk_type="toc",
        doc_type_kwd="text",
        available_int=0,
        display_text=toc_text,
        content_with_weight=toc_text,
        content_ltks=source_chunk.content_ltks,
        content_sm_ltks=source_chunk.content_sm_ltks,
        vector_text=toc_text,
        title_text=source_chunk.title_text,
        embedding_text=toc_text,
        embedding_title_weight=source_chunk.embedding_title_weight,
        docnm_kwd=source_chunk.docnm_kwd,
        title_tks=source_chunk.title_tks,
        title_sm_tks=source_chunk.title_sm_tks,
        authors_tks=source_chunk.authors_tks,
        authors_sm_tks=source_chunk.authors_sm_tks,
        important_kwd=[],
        important_tks="",
        question_kwd=[],
        question_tks="",
        tag_kwd=[],
        tag_feas={},
        pagerank_fea=source_chunk.pagerank_fea,
        removed_kwd="N",
        source_id=list(source_chunk.source_id),
        chunk_data=None,
        img_id="",
        mom_id="",
        create_time=source_chunk.create_time,
        create_timestamp_flt=source_chunk.create_timestamp_flt,
        position_int=[],
        page_num_int=[100000000],
        top_int=[],
        section_path=list(source_chunk.section_path[:1] or source_chunk.section_path),
        page_spans=[{"page_from": 100000000, "page_to": 100000000}],
        source_block_ids=[source_chunk.chunk_id],
        keyword_terms=["toc", *source_chunk.keyword_terms[:4]],
        confirmed_tags=list(source_chunk.confirmed_tags),
        visibility=source_chunk.visibility,
        published_document_state=source_chunk.published_document_state,
        access_control=dict(source_chunk.access_control),
        citation_payload={
            "collection_id": source_chunk.collection_id,
            "final_doc_id": source_chunk.final_doc_id,
            "section_path": list(source_chunk.section_path[:1] or source_chunk.section_path),
            "anchor": "toc",
            "toc_kwd": "toc",
        },
        lexical_payload={
            **source_chunk.lexical_payload,
            "lexical_text": toc_text,
        },
        vector_payload={
            **source_chunk.vector_payload,
            "embedding_text": toc_text,
        },
        metadata={
            **{
                key: value
                for key, value in source_chunk.metadata.items()
                if key not in {"is_parent_chunk", "is_toc_chunk", "toc_kwd"}
            },
            "toc_kwd": "toc",
            "is_toc_chunk": True,
        },
        chunk_hash="sha256:" + sha256(toc_text.encode("utf-8")).hexdigest(),
    )


def _toc_json_text(value: object) -> str:
    import json

    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return ""


def _indexed_document_outline(snapshot, chunk_records: list[ChunkRecord]) -> list[dict[str, object]]:
    outline_payload = snapshot.document_metadata.get("outline")
    visible_chunks = [chunk for chunk in chunk_records if chunk.available_int >= 1]
    if isinstance(outline_payload, list):
        normalized = _outline_with_chunk_ids(outline_payload, visible_chunks)
        if normalized:
            return normalized
    return [
        {"level": "0", "title": str(item).strip(), "ids": [visible_chunks[0].chunk_id] if visible_chunks else []}
        for item in snapshot.outline
        if str(item).strip()
    ]


def _outline_with_chunk_ids(
    outline_payload: object,
    visible_chunks: list[ChunkRecord],
) -> list[dict[str, object]]:
    if not isinstance(outline_payload, list):
        return []
    normalized: list[dict[str, object]] = []
    for index, item in enumerate(outline_payload):
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        raw_chunk_idx = copied.pop("chunk_id", None)
        ids: list[str] = []
        chunk_idx = _optional_int(raw_chunk_idx)
        if chunk_idx is not None and 0 <= chunk_idx < len(visible_chunks):
            ids.append(visible_chunks[chunk_idx].chunk_id)
            next_idx: int | None = None
            for future in outline_payload[index + 1 :]:
                if isinstance(future, dict):
                    next_idx = _optional_int(future.get("chunk_id"))
                    if next_idx is not None:
                        break
            if next_idx is not None:
                for join_idx in range(chunk_idx + 1, min(next_idx + 1, len(visible_chunks))):
                    ids.append(visible_chunks[join_idx].chunk_id)
        copied["ids"] = ids
        normalized.append(copied)
    return normalized


def _keyword_terms(
    *,
    title: str,
    filename: str,
    section_path: list[str],
    confirmed_tags: list[str],
    display_text: str,
    upstream_chunk: dict[str, object],
) -> list[str]:
    seen: list[str] = []
    important_kwd = upstream_chunk.get("important_kwd")
    if isinstance(important_kwd, list):
        important_blob = " ".join(str(item).strip() for item in important_kwd if str(item).strip())
    else:
        important_blob = str(important_kwd or "").strip()
    authors_blob = _authors_text(upstream_chunk)
    candidates = [
        title,
        filename,
        " ".join(section_path),
        " ".join(confirmed_tags),
        display_text,
        important_blob,
        authors_blob,
        " ".join(str(value) for value in upstream_chunk.values() if isinstance(value, str)),
    ]
    for blob in candidates:
        for term in re.split(r"[^a-z0-9_]+", blob.lower()):
            if len(term) < 2:
                continue
            if term not in seen:
                seen.append(term)
    return seen[:16]


def _page_spans_from_citation(citation_payload: dict[str, object]) -> list[dict[str, int]]:
    page_numbers = citation_payload.get("page_num_int")
    if isinstance(page_numbers, list) and page_numbers:
        normalized = [int(page_no) for page_no in page_numbers if isinstance(page_no, (int, float))]
        if normalized:
            return [{"page_from": min(normalized), "page_to": max(normalized)}]
    return [{"page_from": 1, "page_to": 1}]


def _section_path_from_chunk(chunk: dict[str, object], title: str, *, parser_id: str) -> list[str]:
    raw = chunk.get("section_path")
    if isinstance(raw, list):
        normalized = [str(item).strip() for item in raw if str(item).strip()]
        if normalized:
            return normalized
    raw_paths = chunk.get("section_paths")
    if isinstance(raw_paths, list):
        normalized_paths = [str(item).strip() for item in raw_paths if str(item).strip()]
        if normalized_paths:
            if title and normalized_paths[0].lower() != title.lower():
                return [title, *normalized_paths]
            return normalized_paths
    if parser_id == "presentation":
        slide_number = _first_page_number(chunk)
        if slide_number is not None:
            return [title, f"Slide {slide_number}"]
    if parser_id == "paper":
        important_kwd = chunk.get("important_kwd")
        if isinstance(important_kwd, list):
            normalized_keywords = [str(item).strip() for item in important_kwd if str(item).strip()]
            if normalized_keywords:
                return [title, normalized_keywords[0]]
    if parser_id == "qa":
        qa_title = _qa_section_title(chunk)
        if qa_title:
            return [title, qa_title]
    derived: list[str] = [title]
    for key in ("docnm_kwd", "title_tks", "title_sm_tks"):
        value = chunk.get(key)
        if not value:
            continue
        if isinstance(value, list):
            text = " ".join(str(item).strip() for item in value if str(item).strip())
        else:
            text = str(value).strip()
        if text and text.lower() != title.lower():
            derived.append(text)
            break
    return derived


def _source_block_ids_from_chunk(chunk: dict[str, object], ordinal: int) -> list[str]:
    values: list[str] = []
    for key in ("id", "img_id", "row_id", "mom_id"):
        value = chunk.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            values.append(text)
    if values:
        return values
    return [f"upstream_chunk_{ordinal:04d}"]


def _anchor_from_chunk(chunk: dict[str, object], ordinal: int, *, parser_id: str) -> str:
    page_numbers = _page_numbers(chunk)
    if page_numbers:
        if parser_id == "presentation":
            return f"slide:{min(page_numbers)}-{max(page_numbers)}:chunk:{ordinal}"
        return f"page:{min(page_numbers)}-{max(page_numbers)}:chunk:{ordinal}"
    return f"chunk:{ordinal}"


def _chunk_metadata(
    chunk: dict[str, object],
    document_metadata: dict[str, object],
    *,
    parser_id: str,
) -> dict[str, object]:
    excluded = {
        "content_with_weight",
        "content_ltks",
        "content_sm_ltks",
        "position_int",
        "page_num_int",
        "top_int",
        "__outline__",
    }
    metadata = {
        key: value
        for key, value in chunk.items()
        if key not in excluded
    }
    metadata["parser_id"] = parser_id
    if parser_id == "presentation":
        slide_number = _first_page_number(chunk)
        if slide_number is not None:
            metadata["slide_number"] = slide_number
    if parser_id == "paper":
        authors_text = _authors_text(chunk)
        if authors_text:
            metadata["authors"] = authors_text
    if parser_id == "qa":
        qa_title = _qa_section_title(chunk)
        if qa_title:
            metadata["qa_question"] = qa_title
    important_kwd = chunk.get("important_kwd")
    if isinstance(important_kwd, list):
        normalized_keywords = [str(item).strip() for item in important_kwd if str(item).strip()]
        if normalized_keywords:
            metadata["important_kwd"] = normalized_keywords
    if document_metadata:
        metadata["doc_metadata"] = dict(document_metadata)
    return metadata


def _chunk_type_from_upstream(
    chunk: dict[str, object],
    *,
    parser_id: str,
    display_text: str,
) -> str:
    doc_type = str(chunk.get("doc_type_kwd", "")).strip().lower()
    if doc_type == "table":
        return "table"
    if doc_type == "image":
        if parser_id == "presentation" and display_text:
            return "mixed"
        if parser_id == "qa" and display_text:
            return "mixed"
        return "figure" if not display_text else "mixed"
    return "text"


def _chunk_data(chunk: dict[str, object]) -> dict[str, object] | None:
    value = chunk.get("chunk_data")
    if isinstance(value, dict):
        return dict(value)
    return None


def _page_numbers(chunk: dict[str, object]) -> list[int]:
    page_numbers = chunk.get("page_num_int")
    if isinstance(page_numbers, list) and page_numbers:
        return [int(page_no) for page_no in page_numbers if isinstance(page_no, (int, float))]
    return []


def _first_page_number(chunk: dict[str, object]) -> int | None:
    page_numbers = _page_numbers(chunk)
    if page_numbers:
        return page_numbers[0]
    return None


def _authors_text(chunk: dict[str, object]) -> str:
    for key in ("authors", "authors_tks", "authors_sm_tks"):
        value = chunk.get(key)
        if isinstance(value, list):
            text = " ".join(str(item).strip() for item in value if str(item).strip()).strip()
        else:
            text = str(value or "").strip()
        if text:
            return text
    return ""


def _qa_section_title(chunk: dict[str, object]) -> str:
    question_lines = chunk.get("question_kwd")
    if isinstance(question_lines, list):
        for item in question_lines:
            text = str(item).strip()
            if text:
                return text
    content = str(chunk.get("content_with_weight") or "").strip()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(?:Question|Q|问题)[:：\s]+(.+)$", stripped, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""
