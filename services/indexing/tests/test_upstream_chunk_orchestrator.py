from __future__ import annotations

import asyncio

from indexing_service.upstream_chunk_orchestrator import UpstreamChunkOrchestrator


def test_orchestrator_infers_metadata_tags_and_toc() -> None:
    orchestrator = UpstreamChunkOrchestrator()
    chunks = [
        {
            "content_with_weight": "# Expense Policy\n\nQ: Reimbursement deadline\nA: Submit receipts to finance within 30 days.",
            "docnm_kwd": "expense-policy.txt",
            "title_tks": "expense - policy",
            "page_num_int": [1],
            "top_int": [1],
        }
    ]

    result = asyncio.run(
        orchestrator.process(
            parser_id="naive",
            parser_config={
                "enable_metadata": True,
                "metadata": ["department", "doc_type", "summary"],
                "built_in_metadata": ["title"],
                "tag_kb_ids": ["kb_policy"],
                "available_tags": ["finance", "policy", "hr"],
                "toc_extraction": True,
            },
            chunks=chunks,
            tenant_id="tnt_default",
            language="Chinese",
        )
    )

    assert result.document_metadata["title"] == "expense-policy"
    assert result.document_metadata["doc_type"] == "qa"
    assert result.document_metadata["department"] == "finance"
    assert result.document_metadata["summary"]
    assert result.outline
    assert any(item["title"] == "Expense Policy" for item in result.document_metadata["outline"])
    assert result.chunks[0]["tag_feas"]
    assert "finance" in result.chunks[0]["tag_feas"] or "policy" in result.chunks[0]["tag_feas"]


def test_orchestrator_table_metadata_aggregation() -> None:
    orchestrator = UpstreamChunkOrchestrator()
    chunks = [
        {
            "content_with_weight": "- name: Alice\n- dept: HR",
            "name_tks": "Alice",
            "name_raw": "Alice",
            "dept_raw": "HR",
            "dept_tks": "HR",
        },
        {
            "content_with_weight": "- name: Bob\n- dept: Finance",
            "name_tks": "Bob",
            "name_raw": "Bob",
            "dept_raw": "Finance",
            "dept_tks": "Finance",
        },
    ]

    result = asyncio.run(
        orchestrator.process(
            parser_id="table",
            parser_config={
                "table_column_mode": "manual",
                "table_column_roles": {"name": "metadata", "dept": "both"},
                "table_column_names": ["name", "dept", "city"],
            },
            chunks=chunks,
            tenant_id="tnt_default",
            language="Chinese",
        )
    )

    assert result.document_metadata["name"] == ["Alice", "Bob"]
    assert result.document_metadata["dept"] == ["HR", "Finance"]


def test_orchestrator_merges_metadata_like_upstream_update_metadata_to() -> None:
    orchestrator = UpstreamChunkOrchestrator()
    chunks = [
        {
            "content_with_weight": "Expense reimbursement policy for finance.",
            "docnm_kwd": "expense-policy.txt",
        },
        {
            "content_with_weight": "Budget approval workflow for finance leaders.",
            "docnm_kwd": "expense-policy.txt",
        },
    ]

    result = asyncio.run(
        orchestrator.process(
            parser_id="naive",
            parser_config={
                "enable_metadata": True,
                "metadata": [
                    {"key": "department", "description": "business department"},
                    {"key": "summary", "description": "document summary"},
                ],
            },
            chunks=chunks,
            tenant_id="tnt_default",
            language="Chinese",
        )
    )

    assert result.document_metadata["department"] == "finance"
    assert isinstance(result.document_metadata["summary"], str)
