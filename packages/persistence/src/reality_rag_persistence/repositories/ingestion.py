"""Ingestion repository — shared by ingestion-worker (write) and admin-api (read)."""

from sqlalchemy.orm import Session

from reality_rag_contracts import ConversionReport, IngestionJob, JobStatus

from ..models import IngestionJobModel


class IngestionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: str) -> IngestionJob | None:
        row = self._session.get(IngestionJobModel, job_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_all(self) -> list[IngestionJob]:
        rows = self._session.query(IngestionJobModel).all()
        return [self._to_contract(r) for r in rows]

    def list_by_collection(self, collection_id: str) -> list[IngestionJob]:
        rows = (
            self._session.query(IngestionJobModel)
            .filter(IngestionJobModel.collection_id == collection_id)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def save(self, job: IngestionJob) -> None:
        report_json = None
        if job.conversion_report is not None:
            report_json = self._to_summary_json(job.conversion_report)

        row = IngestionJobModel(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status.value,
            collection_id=job.collection_id,
            source_files=job.source_files,
            source_file_ids=job.source_file_ids,
            conversion_report=report_json,
            report_asset_path=job.report_asset_path,
            created_at=job.created_at,
            updated_at=job.updated_at,
            error_message=job.error_message,
        )
        self._session.merge(row)
        self._session.flush()

    @staticmethod
    def _to_summary_json(report: ConversionReport) -> dict:
        data = report.model_dump(mode="json")
        details = []
        for detail in report.details:
            detail_json = detail.model_dump(mode="json")
            detail_json["canonical_md"] = ""
            details.append(detail_json)
        data["details"] = details
        return data

    @staticmethod
    def _to_contract(row: IngestionJobModel) -> IngestionJob:
        report = None
        if row.conversion_report:
            report = ConversionReport(**row.conversion_report)
        return IngestionJob(
            job_id=row.job_id,
            job_type=row.job_type,
            status=JobStatus(row.status),
            collection_id=row.collection_id,
            source_files=row.source_files or [],
            source_file_ids=row.source_file_ids or [],
            conversion_report=report,
            report_asset_path=row.report_asset_path,
            created_at=row.created_at,
            updated_at=row.updated_at,
            error_message=row.error_message,
        )
