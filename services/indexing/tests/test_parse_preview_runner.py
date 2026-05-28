from __future__ import annotations

from pathlib import Path

from indexing_service.jobs.parse_preview_runner import ParsePreviewRunner
from indexing_service.preview_contracts import ParsePreviewRequestedCommand
from indexing_service.persistent_repository import PersistentIndexingRepository


def test_parse_preview_accepts_manual_overrides() -> None:
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    runner = ParsePreviewRunner(repository=repo)
    accepted = runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_test_parse_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_parse_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            parser_id="qa",
            parser_config={"chunk_token_num": 999},
            trace_id="trc_test_parse_01",
        )
    )

    assert accepted.parser_id == "qa"
    assert "manual_parser_override_accepted:qa" in accepted.warnings
    assert "manual_parser_config_override_ignored" in accepted.warnings


def test_parse_snapshot_keeps_upstream_chunks() -> None:
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-table.csv")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    runner = ParsePreviewRunner(repository=repo)
    accepted = runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_test_parse_02",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_parse_02",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/csv",
            trace_id="trc_test_parse_02",
        )
    )

    snapshot = repo.get_parse_snapshot(accepted.parse_snapshot_id)
    assert snapshot.parser_id == "naive" or snapshot.parser_id == "table"
    assert snapshot.upstream_chunks


def test_table_preview_freezes_upstream_table_parser_config() -> None:
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-table.csv")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    runner = ParsePreviewRunner(repository=repo)
    accepted = runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_test_parse_table_03",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_parse_table_03",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/csv",
            collection_parser_id="table",
            collection_parser_config={
                "table_column_mode": "manual",
                "table_column_roles": {
                    "name": "metadata",
                    "dept": "both",
                    "city": "indexing",
                },
            },
            trace_id="trc_test_parse_table_03",
        )
    )

    snapshot = repo.get_parse_snapshot(accepted.parse_snapshot_id)
    assert snapshot.parser_id == "table"
    assert snapshot.parser_config["table_column_mode"] == "manual"
    assert snapshot.parser_config["table_column_roles"]["name"] == "metadata"
    assert "table_column_names" in snapshot.parser_config
    assert "field_map" in snapshot.parser_config
    assert "dept_tks" in snapshot.parser_config["field_map"]


def test_preview_uses_upstream_default_parser_config() -> None:
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    runner = ParsePreviewRunner(repository=repo)
    accepted = runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_test_parse_defaults_04",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_parse_defaults_04",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_test_parse_defaults_04",
        )
    )

    snapshot = repo.get_parse_snapshot(accepted.parse_snapshot_id)
    assert snapshot.parser_config["table_context_size"] == 0
    assert snapshot.parser_config["image_context_size"] == 0
    assert snapshot.parser_config["layout_recognize"] == "DeepDOC"
    assert snapshot.parser_config["chunk_token_num"] == 512
    assert snapshot.parser_config["delimiter"] == "\n"


def test_preview_freezes_layout_and_media_context_config() -> None:
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    runner = ParsePreviewRunner(repository=repo)
    accepted = runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_test_parse_defaults_05",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_parse_defaults_05",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            collection_parser_config={
                "layout_recognize": "MinerU",
                "table_context_size": 64,
                "image_context_size": 48,
                "chunk_token_num": 256,
            },
            trace_id="trc_test_parse_defaults_05",
        )
    )

    snapshot = repo.get_parse_snapshot(accepted.parse_snapshot_id)
    assert snapshot.parser_config["layout_recognize"] == "MinerU"
    assert snapshot.parser_config["table_context_size"] == 64
    assert snapshot.parser_config["image_context_size"] == 48
    assert snapshot.parser_config["chunk_token_num"] == 256
