"""Small helpers for translating report status into job status."""

from __future__ import annotations

from reality_rag_contracts import ConversionReport, ConversionStatus, JobStatus


def resolve_job_status(report: ConversionReport) -> JobStatus:
    if report.conversion_status == ConversionStatus.FAILED:
        return JobStatus.FAILED
    if report.conversion_status == ConversionStatus.PARTIAL:
        return JobStatus.PARTIAL
    if report.conversion_status == ConversionStatus.UNSUPPORTED:
        return JobStatus.FAILED
    return JobStatus.COMPLETED


def build_error_message(report: ConversionReport) -> str | None:
    if report.conversion_status == ConversionStatus.PARTIAL:
        return (
            f"Partial conversion: {report.successful}/{report.total_files} "
            f"succeeded, {report.failed} failed, {report.unsupported} unsupported"
        )
    return None
