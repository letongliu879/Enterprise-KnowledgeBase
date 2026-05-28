from __future__ import annotations

from typing import Any

from reality_rag_contracts import ChunkAsset, IndexAssetBundle, OpenSearchIndexRecord, QdrantPointRecord

from indexing_service.domain import ChunkRecord, IndexVersionRecord


def build_index_asset_bundle(
    *,
    indexed_document_id: str,
    index_version: IndexVersionRecord,
    final_doc_id: str,
    canonical_source: str,
    chunks: list[ChunkRecord],
) -> IndexAssetBundle:
    chunk_assets: list[ChunkAsset] = []
    opensearch_records: list[OpenSearchIndexRecord] = []
    qdrant_points: list[QdrantPointRecord] = []
    document_metadata = _document_metadata(chunks)

    for ordinal, chunk in enumerate(chunks):
        metadata = _bundle_metadata(chunk)
        chunk_assets.append(
            ChunkAsset(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.final_doc_id,
                collection_id=chunk.collection_id,
                chunk_index=ordinal,
                canonical_source=canonical_source,
                heading=" / ".join(chunk.section_path),
                content=chunk.display_text,
                token_estimate=_token_estimate(chunk.vector_text),
                metadata=metadata,
            )
        )
        opensearch_records.append(
            OpenSearchIndexRecord(
                index_name=index_version.opensearch_index,
                document_id=chunk.chunk_id,
                body={
                    "indexed_document_id": indexed_document_id,
                    "id": chunk.record_id or chunk.chunk_id,
                    "chunk_id": chunk.chunk_id,
                    "kb_id": chunk.kb_id,
                    "doc_id": chunk.final_doc_id,
                    "tenant_id": chunk.tenant_id,
                    "collection_id": chunk.collection_id,
                    "final_doc_id": chunk.final_doc_id,
                    "index_version_id": chunk.index_version_id,
                    "document_index_revision_id": chunk.document_index_revision_id,
                    "chunk_type": chunk.chunk_type,
                    "doc_type_kwd": chunk.doc_type_kwd,
                    "available_int": chunk.available_int,
                    "display_text": chunk.display_text,
                    "content_with_weight": chunk.content_with_weight,
                    "content_ltks": chunk.content_ltks,
                    "content_sm_ltks": chunk.content_sm_ltks,
                    "vector_text": chunk.vector_text,
                    "title_text": chunk.title_text,
                    "embedding_text": chunk.embedding_text,
                    "embedding_title_weight": chunk.embedding_title_weight,
                    "docnm_kwd": chunk.docnm_kwd,
                    "title_tks": chunk.title_tks,
                    "title_sm_tks": chunk.title_sm_tks,
                    "authors_tks": chunk.authors_tks,
                    "authors_sm_tks": chunk.authors_sm_tks,
                    "important_kwd": chunk.important_kwd,
                    "important_tks": chunk.important_tks,
                    "question_kwd": chunk.question_kwd,
                    "question_tks": chunk.question_tks,
                    "tag_kwd": chunk.tag_kwd,
                    "tag_feas": chunk.tag_feas,
                    "pagerank_fea": chunk.pagerank_fea,
                    "removed_kwd": chunk.removed_kwd,
                    "source_id": chunk.source_id,
                    "chunk_data": chunk.chunk_data,
                    "img_id": chunk.img_id,
                    "mom_id": chunk.mom_id,
                    "create_time": chunk.create_time,
                    "create_timestamp_flt": chunk.create_timestamp_flt,
                    "position_int": chunk.position_int,
                    "page_num_int": chunk.page_num_int,
                    "top_int": chunk.top_int,
                    "section_path": chunk.section_path,
                    "page_spans": chunk.page_spans,
                    "source_block_ids": chunk.source_block_ids,
                    "keyword_terms": chunk.keyword_terms,
                    "confirmed_tags": chunk.confirmed_tags,
                    "visibility": chunk.visibility,
                    "published_document_state": chunk.published_document_state,
                    "allowed_principal_ids": chunk.access_control.get("allowed_principal_ids", []),
                    "allowed_groups": chunk.access_control.get("allowed_groups", []),
                    "citation_payload": chunk.citation_payload,
                    "governance": metadata.get("governance", {}),
                    "metadata": metadata,
                    "chunk_hash": chunk.chunk_hash,
                },
            )
        )
        qdrant_points.append(
            QdrantPointRecord(
                collection_name=index_version.qdrant_collection,
                point_id=chunk.chunk_id,
                payload={
                    "indexed_document_id": indexed_document_id,
                    "id": chunk.record_id or chunk.chunk_id,
                    "chunk_id": chunk.chunk_id,
                    "kb_id": chunk.kb_id,
                    "doc_id": chunk.final_doc_id,
                    "tenant_id": chunk.tenant_id,
                    "collection_id": chunk.collection_id,
                    "final_doc_id": chunk.final_doc_id,
                    "index_version_id": chunk.index_version_id,
                    "chunk_type": chunk.chunk_type,
                    "doc_type_kwd": chunk.doc_type_kwd,
                    "available_int": chunk.available_int,
                    "display_text": chunk.display_text,
                    "content_with_weight": chunk.content_with_weight,
                    "content_ltks": chunk.content_ltks,
                    "content_sm_ltks": chunk.content_sm_ltks,
                    "vector_text": chunk.vector_text,
                    "title_text": chunk.title_text,
                    "embedding_text": chunk.embedding_text,
                    "embedding_title_weight": chunk.embedding_title_weight,
                    "docnm_kwd": chunk.docnm_kwd,
                    "title_tks": chunk.title_tks,
                    "title_sm_tks": chunk.title_sm_tks,
                    "authors_tks": chunk.authors_tks,
                    "authors_sm_tks": chunk.authors_sm_tks,
                    "important_kwd": chunk.important_kwd,
                    "important_tks": chunk.important_tks,
                    "question_kwd": chunk.question_kwd,
                    "question_tks": chunk.question_tks,
                    "tag_kwd": chunk.tag_kwd,
                    "tag_feas": chunk.tag_feas,
                    "pagerank_fea": chunk.pagerank_fea,
                    "removed_kwd": chunk.removed_kwd,
                    "source_id": chunk.source_id,
                    "chunk_data": chunk.chunk_data,
                    "img_id": chunk.img_id,
                    "mom_id": chunk.mom_id,
                    "create_time": chunk.create_time,
                    "create_timestamp_flt": chunk.create_timestamp_flt,
                    "position_int": chunk.position_int,
                    "page_num_int": chunk.page_num_int,
                    "top_int": chunk.top_int,
                    "section_path": chunk.section_path,
                    "page_spans": chunk.page_spans,
                    "source_block_ids": chunk.source_block_ids,
                    "keyword_terms": chunk.keyword_terms,
                    "confirmed_tags": chunk.confirmed_tags,
                    "visibility": chunk.visibility,
                    "published_document_state": chunk.published_document_state,
                    "allowed_principal_ids": chunk.access_control.get("allowed_principal_ids", []),
                    "allowed_groups": chunk.access_control.get("allowed_groups", []),
                    "citation_payload": chunk.citation_payload,
                    "governance": metadata.get("governance", {}),
                    "metadata": metadata,
                    "chunk_hash": chunk.chunk_hash,
                },
            )
        )

    return IndexAssetBundle(
        indexed_document_id=indexed_document_id,
        doc_id=final_doc_id,
        collection_id=index_version.collection_id,
        index_version=index_version.index_version_id,
        canonical_source=canonical_source,
        document_metadata=document_metadata,
        chunks=chunk_assets,
        opensearch_records=opensearch_records,
        qdrant_points=qdrant_points,
    )


def _bundle_metadata(chunk: ChunkRecord) -> dict[str, Any]:
    return {
        **chunk.metadata,
        "access_control": chunk.access_control,
        "citation_payload": chunk.citation_payload,
        "keyword_terms": chunk.keyword_terms,
        "confirmed_tags": chunk.confirmed_tags,
    }


def _token_estimate(text: str) -> int:
    normalized = text.strip()
    if not normalized:
        return 0
    return max(1, len(normalized.split()))


def _document_metadata(chunks: list[ChunkRecord]) -> dict[str, Any]:
    for chunk in chunks:
        metadata = chunk.metadata.get("doc_metadata")
        if isinstance(metadata, dict) and metadata:
            return dict(metadata)
    return {}
