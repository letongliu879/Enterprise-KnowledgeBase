"""Task projection service."""

from reality_rag_contracts.models import WorkbenchTaskView

from ..deps import CurrentUser
from ..downstream_clients import IntakeClient, ApprovalClient, IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..upload_sessions.repository import UploadSessionRepository


class TaskProjectionService:
    def __init__(
        self,
        repository: UploadSessionRepository,
        intake_client: IntakeClient,
        approval_client: ApprovalClient,
        indexing_client: IndexingClient,
    ):
        self._repository = repository
        self._intake_client = intake_client
        self._approval_client = approval_client
        self._indexing_client = indexing_client

    async def list_tasks(self, user: CurrentUser, collection_id: str | None = None, status: str | None = None) -> list[WorkbenchTaskView]:
        uploads = self._repository.list_by_user(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            collection_id=collection_id,
            status=status,
        )
        tasks = []
        for u in uploads:
            task = await self._derive_task_view(u)
            tasks.append(task)
        return tasks

    async def get_task(self, upload_id: str, user: CurrentUser) -> WorkbenchTaskView | None:
        upload = self._repository.get(upload_id)
        if not upload or upload.user_id != user.user_id:
            return None
        return await self._derive_task_view(upload)

    async def _derive_task_view(self, upload) -> WorkbenchTaskView:
        """Derive task view from upload session and downstream owner states."""
        source_file_state = None
        intake_job_state = None
        parse_snapshot_state = None
        ticket_state = None
        published_document_state = None
        index_build_state = None
        active_index_version = None

        # Query intake-pipeline for source file and intake job states
        if upload.source_file_id:
            try:
                sf = await self._intake_client.get_source_file(upload.source_file_id)
                source_file_state = sf.get("state")
            except DownstreamError:
                pass

            # Derive intake job state from source file response (it includes intake_job_id)
            try:
                sf = await self._intake_client.get_source_file(upload.source_file_id)
                intake_job_id = sf.get("intake_job_id")
                if intake_job_id:
                    job = await self._intake_client.get_intake_job(intake_job_id)
                    intake_job_state = job.get("state")
                    # Parse snapshot state derived from presence of parse_snapshot_id
                    parse_snapshot_id = job.get("parse_snapshot_id")
                    if parse_snapshot_id:
                        parse_snapshot_state = "PARSED"
                    elif intake_job_state in ("CREATED", "PARSING"):
                        parse_snapshot_state = "PARSING"
                    elif intake_job_state == "FAILED":
                        parse_snapshot_state = "FAILED"
                    else:
                        parse_snapshot_state = "CREATED"

                    # Query approval ticket if ticket_id present
                    ticket_id = job.get("ticket_id")
                    if ticket_id:
                        try:
                            ticket = await self._approval_client.get_ticket(ticket_id)
                            ticket_state = ticket.get("state")
                        except DownstreamError:
                            pass

                    # Query published document if published_document_id present
                    published_document_id = job.get("published_document_id")
                    if published_document_id:
                        try:
                            pd = await self._intake_client.get_published_document(published_document_id)
                            published_document_state = pd.get("state")
                        except DownstreamError:
                            pass

                    # Query indexing service for index state
                    final_doc_id = job.get("final_doc_id")
                    if final_doc_id:
                        try:
                            indexed_docs = await self._indexing_client.get_indexed_documents(
                                collection_id=upload.collection_id,
                                final_doc_id=final_doc_id,
                            )
                            if indexed_docs:
                                # Get the most recent active or candidate document
                                active_doc = next(
                                    (d for d in indexed_docs if d.get("state") == "ACTIVE"),
                                    None,
                                )
                                if active_doc:
                                    index_build_state = "ACTIVE"
                                    active_index_version = active_doc.get("index_version")
                                else:
                                    # Check for candidate (building) state
                                    candidate_doc = next(
                                        (d for d in indexed_docs if d.get("state") == "CANDIDATE"),
                                        None,
                                    )
                                    if candidate_doc:
                                        index_build_state = "BUILDING"
                                    else:
                                        index_build_state = indexed_docs[0].get("state")
                        except DownstreamError:
                            pass
            except DownstreamError:
                pass

        # Derive overall status from owner states
        status = self._derive_status(
            source_file_state=source_file_state,
            intake_job_state=intake_job_state,
            ticket_state=ticket_state,
            published_document_state=published_document_state,
            index_build_state=index_build_state,
            active_index_version=active_index_version,
        )

        # Derive progress percentage
        progress_pct = self._derive_progress(
            source_file_state=source_file_state,
            intake_job_state=intake_job_state,
            parse_snapshot_state=parse_snapshot_state,
            ticket_state=ticket_state,
            published_document_state=published_document_state,
            index_build_state=index_build_state,
            active_index_version=active_index_version,
        )

        return WorkbenchTaskView(
            upload_id=upload.upload_id,
            status=status,
            progress_pct=progress_pct,
            source_file_state=source_file_state,
            intake_job_state=intake_job_state,
            parse_snapshot_state=parse_snapshot_state,
            ticket_state=ticket_state,
            published_document_state=published_document_state,
            index_build_state=index_build_state,
            active_index_version=active_index_version,
            filename=upload.filename,
            collection_id=upload.collection_id,
            created_at=upload.created_at,
            updated_at=upload.updated_at,
        )

    @staticmethod
    def _derive_status(
        source_file_state: str | None,
        intake_job_state: str | None,
        ticket_state: str | None,
        published_document_state: str | None,
        index_build_state: str | None,
        active_index_version: str | None,
    ) -> str:
        if published_document_state == "ARCHIVED":
            return "archived"
        if published_document_state == "RETRACTED":
            return "retracted"
        if active_index_version:
            return "published"
        if index_build_state == "BUILDING":
            return "indexing"
        if published_document_state == "PUBLISH_SUCCEEDED":
            return "published"
        if ticket_state == "approved":
            return "approved"
        if ticket_state == "rejected":
            return "rejected"
        if ticket_state == "pending":
            return "reviewing"
        if intake_job_state == "FAILED":
            return "failed"
        if intake_job_state == "PUBLISHED":
            return "published"
        if intake_job_state == "AWAITING_APPROVAL":
            return "reviewing"
        if intake_job_state in ("CREATED", "PARSING"):
            return "parsing"
        if source_file_state == "READY":
            return "uploading"
        return "uploading"

    @staticmethod
    def _derive_progress(
        source_file_state: str | None,
        intake_job_state: str | None,
        parse_snapshot_state: str | None,
        ticket_state: str | None,
        published_document_state: str | None,
        index_build_state: str | None,
        active_index_version: str | None,
    ) -> int:
        if active_index_version:
            return 100
        if index_build_state == "BUILDING":
            return 95
        if published_document_state == "PUBLISH_SUCCEEDED":
            return 100
        if ticket_state == "approved":
            return 90
        if ticket_state == "rejected":
            return 100
        if ticket_state == "pending":
            return 70
        if parse_snapshot_state == "PARSED":
            return 50
        if parse_snapshot_state == "PARSING":
            return 40
        if intake_job_state == "FAILED":
            return 100
        if source_file_state == "READY":
            return 20
        return 0
