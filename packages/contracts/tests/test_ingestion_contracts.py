"""Tests for ingestion contracts: ConversionRequest, ConversionResult,
ConversionReport, IngestionJob, and ConversionStatus enum."""

import json

import pytest

from reality_rag_contracts import (
    ConversionReport,
    ConversionRequest,
    ConversionResult,
    ConversionStatus,
    IngestionJob,
    JobStatus,
)


class TestConversionStatus:
    def test_enum_values(self):
        assert ConversionStatus.SUCCESS.value == "success"
        assert ConversionStatus.FAILED.value == "failed"
        assert ConversionStatus.PARTIAL.value == "partial"
        assert ConversionStatus.UNSUPPORTED.value == "unsupported"

    def test_enum_is_string_enum(self):
        assert isinstance(ConversionStatus.SUCCESS, str)
        assert ConversionStatus.SUCCESS == "success"


class TestConversionRequest:
    def test_required_fields(self):
        req = ConversionRequest(
            source_file_path="/data/raw/test.pdf",
            collection_id="col-1",
        )
        assert req.source_file_path == "/data/raw/test.pdf"
        assert req.collection_id == "col-1"
        assert req.options == {}

    def test_with_options(self):
        req = ConversionRequest(
            source_file_path="/data/raw/test.docx",
            collection_id="col-hr",
            options={"ocr": True, "language": "zh"},
        )
        assert req.options["ocr"] is True
        assert req.options["language"] == "zh"

    def test_default_options_is_empty_dict(self):
        req = ConversionRequest(
            source_file_path="/data/raw/test.pdf",
            collection_id="col-1",
        )
        assert isinstance(req.options, dict)
        assert len(req.options) == 0

    def test_json_roundtrip(self):
        req = ConversionRequest(
            source_file_path="/data/raw/test.pdf",
            collection_id="col-1",
            options={"ocr": False},
        )
        json_str = req.model_dump_json()
        re_parsed = ConversionRequest.model_validate_json(json_str)
        assert re_parsed.source_file_path == req.source_file_path
        assert re_parsed.collection_id == req.collection_id
        assert re_parsed.options == req.options


class TestConversionResult:
    def test_success_result(self):
        result = ConversionResult(
            source_file_path="/data/raw/test.pdf",
            conversion_status=ConversionStatus.SUCCESS,
            canonical_md="# Hello\n\nThis is converted markdown.",
        )
        assert result.conversion_status == ConversionStatus.SUCCESS
        assert "# Hello" in result.canonical_md
        assert result.error_message == ""
        assert result.warnings == []

    def test_failed_result(self):
        result = ConversionResult(
            source_file_path="/data/raw/corrupted.pdf",
            conversion_status=ConversionStatus.FAILED,
            error_message="PDF is encrypted and cannot be read",
        )
        assert result.conversion_status == ConversionStatus.FAILED
        assert result.error_message == "PDF is encrypted and cannot be read"
        assert result.canonical_md == ""

    def test_unsupported_result(self):
        result = ConversionResult(
            source_file_path="/data/raw/data.bin",
            conversion_status=ConversionStatus.UNSUPPORTED,
            error_message="No converter available for .bin files",
            metadata={"extension": ".bin"},
        )
        assert result.conversion_status == ConversionStatus.UNSUPPORTED
        assert result.metadata["extension"] == ".bin"

    def test_partial_result_with_warnings(self):
        result = ConversionResult(
            source_file_path="/data/raw/scanned.pdf",
            conversion_status=ConversionStatus.PARTIAL,
            canonical_md="# Partial output",
            warnings=["Low OCR confidence on page 3", "Possible missing table on page 5"],
            metadata={"ocr_quality": 0.72},
        )
        assert result.conversion_status == ConversionStatus.PARTIAL
        assert len(result.warnings) == 2
        assert result.metadata["ocr_quality"] == 0.72

    def test_json_roundtrip(self):
        result = ConversionResult(
            source_file_path="/data/raw/test.pdf",
            conversion_status=ConversionStatus.SUCCESS,
            canonical_md="# Markdown content",
            metadata={"converter": "ragflow-naive", "file_size_bytes": 204857},
        )
        json_str = result.model_dump_json()
        re_parsed = ConversionResult.model_validate_json(json_str)
        assert re_parsed.source_file_path == result.source_file_path
        assert re_parsed.conversion_status == ConversionStatus.SUCCESS
        assert re_parsed.canonical_md == result.canonical_md
        assert re_parsed.metadata == result.metadata


class TestConversionReport:
    def test_aggregates_multiple_results(self):
        results = [
            ConversionResult(
                source_file_path="/data/raw/success.pdf",
                conversion_status=ConversionStatus.SUCCESS,
                canonical_md="# A",
            ),
            ConversionResult(
                source_file_path="/data/raw/fail.pdf",
                conversion_status=ConversionStatus.FAILED,
                error_message="Bad file",
            ),
            ConversionResult(
                source_file_path="/data/raw/unsupported.bin",
                conversion_status=ConversionStatus.UNSUPPORTED,
                error_message="No converter",
            ),
        ]
        report = ConversionReport(
            report_id="rpt-001",
            job_id="job-001",
            source_file_path="/data/raw/",
            conversion_status=ConversionStatus.PARTIAL,
            total_files=3,
            successful=1,
            failed=1,
            unsupported=1,
            details=results,
        )
        assert report.report_id == "rpt-001"
        assert report.job_id == "job-001"
        assert report.conversion_status == ConversionStatus.PARTIAL
        assert report.total_files == 3
        assert report.successful == 1
        assert report.failed == 1
        assert report.unsupported == 1
        assert len(report.details) == 3

    def test_defaults(self):
        report = ConversionReport(
            report_id="rpt-002",
            job_id="job-002",
            source_file_path="/data/raw/",
            conversion_status=ConversionStatus.SUCCESS,
        )
        assert report.total_files == 1
        assert report.successful == 0
        assert report.failed == 0
        assert report.unsupported == 0
        assert report.details == []

    def test_json_roundtrip(self):
        results = [
            ConversionResult(
                source_file_path="/data/raw/one.pdf",
                conversion_status=ConversionStatus.SUCCESS,
                canonical_md="# One",
            ),
        ]
        report = ConversionReport(
            report_id="rpt-003",
            job_id="job-003",
            source_file_path="/data/raw/",
            conversion_status=ConversionStatus.SUCCESS,
            total_files=1,
            successful=1,
            details=results,
        )
        json_str = report.model_dump_json()
        re_parsed = ConversionReport.model_validate_json(json_str)
        assert re_parsed.report_id == report.report_id
        assert re_parsed.details[0].conversion_status == ConversionStatus.SUCCESS
        assert re_parsed.details[0].canonical_md == "# One"


class TestIngestionJob:
    def test_uses_existing_job_status(self):
        job = IngestionJob(
            job_id="job-001",
            status=JobStatus.PENDING,
            collection_id="col-1",
        )
        assert job.status == JobStatus.PENDING
        assert job.job_type == "ingestion"

    def test_all_job_status_values(self):
        for status in JobStatus:
            job = IngestionJob(
                job_id=f"job-{status.value}",
                status=status,
                collection_id="col-1",
            )
            assert job.status == status

    def test_with_conversion_report(self):
        report = ConversionReport(
            report_id="rpt-001",
            job_id="job-001",
            source_file_path="/data/raw/",
            conversion_status=ConversionStatus.SUCCESS,
            total_files=2,
            successful=2,
            details=[
                ConversionResult(
                    source_file_path="/data/raw/a.pdf",
                    conversion_status=ConversionStatus.SUCCESS,
                    canonical_md="# A",
                ),
                ConversionResult(
                    source_file_path="/data/raw/b.docx",
                    conversion_status=ConversionStatus.SUCCESS,
                    canonical_md="# B",
                ),
            ],
        )
        job = IngestionJob(
            job_id="job-001",
            status=JobStatus.COMPLETED,
            collection_id="col-1",
            source_files=["/data/raw/a.pdf", "/data/raw/b.docx"],
            conversion_report=report,
        )
        assert job.status == JobStatus.COMPLETED
        assert len(job.source_files) == 2
        assert job.conversion_report is not None
        assert job.conversion_report.report_id == "rpt-001"
        assert len(job.conversion_report.details) == 2

    def test_defaults(self):
        job = IngestionJob(
            job_id="job-002",
            status=JobStatus.PENDING,
            collection_id="col-hr",
        )
        assert job.job_type == "ingestion"
        assert job.source_files == []
        assert job.conversion_report is None
        assert job.error_message is None

    def test_json_roundtrip(self):
        job = IngestionJob(
            job_id="job-010",
            status=JobStatus.RUNNING,
            collection_id="col-1",
            source_files=["/data/raw/x.pdf"],
        )
        json_str = job.model_dump_json()
        re_parsed = IngestionJob.model_validate_json(json_str)
        assert re_parsed.job_id == job.job_id
        assert re_parsed.status == JobStatus.RUNNING
        assert re_parsed.source_files == job.source_files

    def test_full_lifecycle_json_roundtrip(self):
        """Simulate a complete ingestion job lifecycle through JSON."""
        job_data = {
            "job_id": "job-lifecycle-001",
            "job_type": "ingestion",
            "status": "completed",
            "collection_id": "col-finance",
            "source_files": ["/data/raw/a.pdf", "/data/raw/b.docx"],
            "conversion_report": {
                "report_id": "rpt-lifecycle-001",
                "job_id": "job-lifecycle-001",
                "source_file_path": "/data/raw/",
                "conversion_status": "success",
                "total_files": 2,
                "successful": 2,
                "failed": 0,
                "unsupported": 0,
                "error_message": "",
                "warnings": [],
                "details": [
                    {
                        "source_file_path": "/data/raw/a.pdf",
                        "conversion_status": "success",
                        "canonical_md": "# Policy A",
                        "error_message": "",
                        "warnings": [],
                        "metadata": {"file_size_bytes": 1000},
                    },
                    {
                        "source_file_path": "/data/raw/b.docx",
                        "conversion_status": "success",
                        "canonical_md": "# Policy B",
                        "error_message": "",
                        "warnings": [],
                        "metadata": {"file_size_bytes": 2000},
                    },
                ],
                "created_at": "2026-05-15T10:30:00Z",
            },
            "created_at": "2026-05-15T10:25:00Z",
            "updated_at": "2026-05-15T10:30:00Z",
            "error_message": None,
        }
        job = IngestionJob.model_validate(job_data)
        assert job.job_id == "job-lifecycle-001"
        assert job.status == JobStatus.COMPLETED
        assert job.conversion_report is not None
        assert job.conversion_report.conversion_status == ConversionStatus.SUCCESS
        assert len(job.conversion_report.details) == 2

        # Serialize back to JSON
        output = json.loads(job.model_dump_json())
        assert output["status"] == "completed"
        assert output["conversion_report"]["conversion_status"] == "success"


class TestFieldSerialization:
    """Verify all new model types can be serialized to JSON."""

    def test_conversion_request_serializable(self):
        req = ConversionRequest(
            source_file_path="/data/raw/test.pdf",
            collection_id="col-1",
        )
        json_str = req.model_dump_json()
        assert isinstance(json_str, str)
        assert json.loads(json_str)

    def test_conversion_result_serializable(self):
        result = ConversionResult(
            source_file_path="/data/raw/test.pdf",
            conversion_status=ConversionStatus.SUCCESS,
            canonical_md="# Markdown",
            metadata={"key": "value"},
        )
        json_str = result.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["conversion_status"] == "success"

    def test_conversion_report_serializable(self):
        report = ConversionReport(
            report_id="rpt-001",
            job_id="job-001",
            source_file_path="/data/raw/",
            conversion_status=ConversionStatus.SUCCESS,
            details=[
                ConversionResult(
                    source_file_path="/data/raw/test.pdf",
                    conversion_status=ConversionStatus.SUCCESS,
                    canonical_md="# Test",
                ),
            ],
        )
        json_str = report.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["report_id"] == "rpt-001"

    def test_ingestion_job_serializable(self):
        job = IngestionJob(
            job_id="job-001",
            status=JobStatus.COMPLETED,
            collection_id="col-1",
        )
        json_str = job.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["job_type"] == "ingestion"
        assert parsed["status"] == "completed"
