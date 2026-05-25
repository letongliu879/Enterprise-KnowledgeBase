"""Job repository."""

from sqlalchemy.orm import Session

from reality_rag_contracts import JobInfo, JobStatus

from ..models import JobModel


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: str) -> JobInfo | None:
        row = self._session.get(JobModel, job_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_all(self) -> list[JobInfo]:
        rows = self._session.query(JobModel).all()
        return [self._to_contract(r) for r in rows]

    def save(self, job: JobInfo) -> None:
        row = JobModel(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status.value,
            collection_id=job.collection_id,
            doc_id=job.doc_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
            error_message=job.error_message,
        )
        self._session.merge(row)
        self._session.flush()

    @staticmethod
    def _to_contract(row: JobModel) -> JobInfo:
        return JobInfo(
            job_id=row.job_id,
            job_type=row.job_type,
            status=JobStatus(row.status),
            collection_id=row.collection_id,
            doc_id=row.doc_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            error_message=row.error_message,
        )
