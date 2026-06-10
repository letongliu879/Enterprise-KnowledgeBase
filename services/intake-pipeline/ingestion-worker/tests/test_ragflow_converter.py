from __future__ import annotations

from pathlib import Path

from reality_rag_contracts import ConversionRequest, ConversionStatus

from intake_runtime.converters.ragflow_converter import RAGFlowConverter


def test_ragflow_converter_preserves_success_when_preview_text_missing(tmp_path, monkeypatch):
    source = tmp_path / "policy.docx"
    source.write_bytes(b"not-empty-docx-placeholder")

    def _fake_parse(_self, command):
        return (
            {"parse_snapshot_id": "ps_001", "parser_id": "naive", "decision_reason": "ok"},
            {
                "preview_text": "",
                "warnings": [],
                "upstream_chunks": [],
                "outline": [],
                "document_metadata": {},
                "parser_config": {},
                "parser_backend": "ragflow",
                "source_suffix": "docx",
            },
        )

    monkeypatch.setattr(RAGFlowConverter, "_parse_via_indexing", _fake_parse)

    result = RAGFlowConverter().convert(
        ConversionRequest(
            source_file_path=str(source),
            collection_id="col_default",
            options={"source_file_id": "src_001", "tenant_id": "tenant_acme", "trace_id": "trace_001"},
        )
    )

    assert result.conversion_status == ConversionStatus.SUCCESS
    assert result.canonical_md == ""
    assert "indexing parse returned no canonical preview text" in result.warnings
    assert result.metadata["missing_canonical_preview_text"] is True
