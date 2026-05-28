"""Build index-ready sidecar assets from canonical markdown."""

from __future__ import annotations

from hashlib import sha256

from reality_rag_contracts import (
    CanonicalMetadata,
    ChunkAsset,
    IndexAssetBundle,
    OpenSearchIndexRecord,
    QdrantPointRecord,
)


def build_index_asset_bundle(
    *,
    canonical_metadata: CanonicalMetadata,
    canonical_content: str,
    index_version: str = "v1",
) -> IndexAssetBundle:
    chunks = _chunk_markdown(canonical_content)
    chunk_assets: list[ChunkAsset] = []
    opensearch_records: list[OpenSearchIndexRecord] = []
    qdrant_points: list[QdrantPointRecord] = []
    index_name = f"reality-rag-{canonical_metadata.collection_id}-{index_version}"

    for idx, content in enumerate(chunks):
        chunk_id = _chunk_id(canonical_metadata.doc_id, idx, content)
        metadata = {
            "tenant_id": canonical_metadata.tenant_id,
            "collection_id": canonical_metadata.collection_id,
            "doc_id": canonical_metadata.doc_id,
            "logical_document_id": canonical_metadata.logical_document_id,
            "source_hash": canonical_metadata.source_hash,
            "publish_status": canonical_metadata.publish_status.value,
            "index_status": canonical_metadata.index_status.value,
            "authority_level": canonical_metadata.authority_level,
            "governance_level": canonical_metadata.governance_level,
            "access_policy": canonical_metadata.access_policy,
            "domain_tags": canonical_metadata.domain_tags,
            "risk_tags": canonical_metadata.risk_tags,
        }
        chunk_assets.append(
            ChunkAsset(
                chunk_id=chunk_id,
                doc_id=canonical_metadata.doc_id,
                collection_id=canonical_metadata.collection_id,
                chunk_index=idx,
                canonical_source=canonical_metadata.asset_paths.get("canonical_md", ""),
                heading=_heading_for(content),
                content=content,
                token_estimate=max(1, len(content.split())),
                metadata=metadata,
            )
        )
        body = {
            **metadata,
            "chunk_id": chunk_id,
            "chunk_index": idx,
            "content": content,
            "index_version": index_version,
        }
        opensearch_records.append(
            OpenSearchIndexRecord(
                index_name=index_name,
                document_id=chunk_id,
                body=body,
            )
        )
        qdrant_points.append(
            QdrantPointRecord(
                collection_name=index_name,
                point_id=chunk_id,
                payload=body,
            )
        )

    return IndexAssetBundle(
        indexed_document_id=f"{canonical_metadata.doc_id}:{index_version}",
        doc_id=canonical_metadata.doc_id,
        collection_id=canonical_metadata.collection_id,
        index_version=index_version,
        canonical_source=canonical_metadata.asset_paths.get("canonical_md", ""),
        document_metadata={
            "tenant_id": canonical_metadata.tenant_id,
            "logical_document_id": canonical_metadata.logical_document_id,
            "source_hash": canonical_metadata.source_hash,
            "quality_summary": canonical_metadata.quality_summary,
            "processing_summary": canonical_metadata.processing_summary,
        },
        chunks=chunk_assets,
        opensearch_records=opensearch_records,
        qdrant_points=qdrant_points,
    )


def retarget_index_asset_bundle(bundle: IndexAssetBundle, index_version: str) -> IndexAssetBundle:
    return bundle.model_copy(update={"index_version": index_version})


def _chunk_markdown(content: str) -> list[str]:
    paragraphs = [part.strip() for part in content.split("\n\n") if part.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        if current and current_len + paragraph_len > 1800:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += paragraph_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _chunk_id(doc_id: str, idx: int, content: str) -> str:
    digest = sha256(f"{doc_id}:{idx}:{content}".encode("utf-8")).hexdigest()[:16]
    return f"chk_{digest}"


def _heading_for(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""

__all__ = [
    "build_index_asset_bundle",
    "retarget_index_asset_bundle",
]
