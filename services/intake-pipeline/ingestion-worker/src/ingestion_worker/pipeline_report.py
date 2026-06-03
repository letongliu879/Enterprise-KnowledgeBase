"""Pipeline report builder — builds ConversionReport from StageContext list."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from intake_runtime.stages.protocol import StageContext
from reality_rag_contracts import ConversionReport, ConversionResult, ConversionStatus, JobStatus


def build_conversion_report(job_id: str, contexts: list[StageContext]) -> ConversionReport:
    """Build ConversionReport from a list of StageContext objects."""
    details = []
    for ctx in contexts:
        if ctx.result is not None:
            detail = ctx.result.model_copy(update={
                "doc_id": ctx.doc_id,
                "canonical_asset_path": ctx.asset_paths.get("canonical_md", ""),
            })
            details.append(detail)
        elif ctx.skipped:
            # File was skipped (e.g., dedup) — report as success since the
            # duplicate is already in the system.
            details.append(ConversionResult(
                source_file_path=ctx.source_file_path or "",
                conversion_status=ConversionStatus.SUCCESS,
                doc_id=ctx.doc_id,
                canonical_asset_path=ctx.asset_paths.get("canonical_md", ""),
                error_message=f"Skipped: {ctx.skip_reason}" if ctx.skip_reason else "",
            ))

    successful = sum(1 for d in details if d.conversion_status == ConversionStatus.SUCCESS)
    failed = sum(1 for d in details if d.conversion_status == ConversionStatus.FAILED)
    unsupported = sum(1 for d in details if d.conversion_status == ConversionStatus.UNSUPPORTED)

    if len(details) == 0:
        overall = ConversionStatus.UNSUPPORTED
    elif failed > 0 and successful == 0 and unsupported == 0:
        overall = ConversionStatus.FAILED
    elif unsupported == len(details):
        overall = ConversionStatus.UNSUPPORTED
    elif failed > 0 or unsupported > 0:
        overall = ConversionStatus.PARTIAL
    else:
        overall = ConversionStatus.SUCCESS

    warnings: list[str] = []
    if unsupported > 0:
        warnings.append(f"{unsupported} file(s) have unsupported extensions")
    if failed > 0:
        warnings.append(f"{failed} file(s) failed conversion")

    return ConversionReport(
        report_id=f"rpt-{uuid4().hex[:8]}",
        job_id=job_id,
        source_file_path=f"batch:{len(details)}_files",
        conversion_status=overall,
        total_files=len(details),
        successful=successful,
        failed=failed,
        unsupported=unsupported,
        warnings=warnings,
        details=details,
        created_at=datetime.now(timezone.utc),
    )


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
