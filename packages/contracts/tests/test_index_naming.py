from reality_rag_contracts import (
    build_opensearch_index_name,
    build_qdrant_collection_name,
    build_versioned_backend_name,
)


def test_backend_name_reuses_collection_prefixed_index_version():
    name = build_versioned_backend_name(
        prefix="reality-rag",
        collection_id="col-1",
        index_version="col-1-v-final",
    )
    assert name == "reality-rag-col-1-v-final"


def test_backend_name_adds_collection_when_missing_from_version():
    name = build_versioned_backend_name(
        prefix="reality-rag",
        collection_id="col-1",
        index_version="v-final",
    )
    assert name == "reality-rag-col-1-v-final"


def test_backend_names_are_sanitized():
    opensearch_name = build_opensearch_index_name(
        index_prefix="Reality RAG",
        collection_id="COL 1",
        index_version="Release/2026-05-17",
    )
    qdrant_name = build_qdrant_collection_name(
        collection_prefix="Reality RAG",
        collection_id="COL 1",
        index_version="Release/2026-05-17",
    )

    assert opensearch_name == "reality-rag-col-1-release-2026-05-17"
    assert qdrant_name == "reality-rag-col-1-release-2026-05-17"
