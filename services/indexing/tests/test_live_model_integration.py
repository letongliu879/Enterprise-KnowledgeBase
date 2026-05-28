from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from indexing_service.backends import embed_texts
from indexing_service.config import load_indexing_config
from indexing_service.jobs.parse_preview_runner import ParsePreviewRunner
from indexing_service.preview_contracts import ParsePreviewRequestedCommand
from indexing_service.persistent_repository import PersistentIndexingRepository


pytestmark = pytest.mark.live_model


def test_live_embedding_returns_real_vector() -> None:
    cfg = load_indexing_config()
    assert cfg.models.embedding_api_key
    assert cfg.models.embedding_base_url
    assert cfg.models.embedding_model

    vectors = asyncio.run(embed_texts(["Finance reimbursement policy."]))
    assert len(vectors) == 1
    assert isinstance(vectors[0], list)
    assert len(vectors[0]) > 0
    assert any(float(value) != 0.0 for value in vectors[0])


def test_live_preview_produces_metadata_tags_and_toc() -> None:
    cfg = load_indexing_config()
    assert cfg.models.chat_api_key
    assert cfg.models.chat_base_url
    assert cfg.models.chat_model

    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    runner = ParsePreviewRunner(repository=repo)
    accepted = runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_live_model_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_live_model_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            collection_parser_config={
                "enable_metadata": True,
                "metadata": ["department", "doc_type", "summary"],
                "built_in_metadata": ["title"],
                "toc_extraction": True,
                "tag_kb_ids": ["kb_policy"],
                "available_tags": ["reimbursement", "deadline", "finance"],
                "auto_keywords": 2,
                "auto_questions": 2,
            },
            trace_id="trc_live_model_01",
        )
    )

    assert accepted.warnings == ["text:qa_pattern"] or "text:qa_pattern" in accepted.warnings
    snapshot = repo.get_parse_snapshot(accepted.parse_snapshot_id)
    assert snapshot.document_metadata.get("title")
    assert snapshot.document_metadata.get("doc_type")
    assert snapshot.document_metadata.get("summary")
    assert snapshot.document_metadata.get("outline")
    assert snapshot.outline
    assert snapshot.upstream_chunks
    first = snapshot.upstream_chunks[0]
    assert first.get("important_kwd")
    assert first.get("question_kwd")
    assert first.get("tag_feas")
