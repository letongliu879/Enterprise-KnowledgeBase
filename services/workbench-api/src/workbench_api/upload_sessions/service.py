"""Upload session service."""

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from reality_rag_contracts.models import WorkbenchUploadSession

from ..deps import CurrentUser
from ..downstream_clients import DocumentServiceClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, conflict
from ..projections.projector import ProjectionProjector
from .repository import UploadSessionRepository


def _visibility_from_access_scope(access_scope_json: dict | None) -> str:
    if (access_scope_json or {}).get("scope_type") == "external":
        return "EXTERNAL"
    return "INTERNAL"


class UploadSessionService:
    def __init__(
        self,
        repository: UploadSessionRepository,
        document_client: DocumentServiceClient,
        actor_id: str,
        db_session: Session | None = None,
    ):
        self._repository = repository
        self._document_client = document_client
        self._actor_id = actor_id
        self._db_session = db_session

    async def create_upload(self, req: dict, user: CurrentUser) -> WorkbenchUploadSession:
        upload_id = f"upload_{uuid.uuid4().hex[:16]}"

        session = WorkbenchUploadSession(
            upload_id=upload_id,
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            collection_id=req["collection_id"],
            source_file_id=None,
            status="uploading",
            progress_pct=0,
            filename=req["filename"],
            mime_type=req["mime_type"],
            size_bytes=req["size_bytes"],
            error_message=None,
            selected_parser_profile_id=req.get("selected_parser_profile_id"),
            parser_override_json=req.get("parser_override_json"),
            access_scope_json=req.get("access_scope_json"),
        )
        self._repository.save(self._to_model(session))

        # Write initial task projection row
        if self._db_session is not None:
            projector = ProjectionProjector(self._db_session)
            now = datetime.now(timezone.utc)
            event = {
                "event_id": f"ev_{upload_id}_created",
                "event_type": "TASK_CREATED",
                "tenant_id": session.tenant_id,
                "collection_id": session.collection_id,
                "aggregate_type": "task",
                "aggregate_id": upload_id,
                "aggregate_version": 1,
                "occurred_at": now,
                "payload": {
                    "projection_id": upload_id,
                    "tenant_id": session.tenant_id,
                    "user_id": session.user_id,
                    "collection_id": session.collection_id,
                    "upload_id": upload_id,
                    "filename": session.filename,
                    "mime_type": session.mime_type,
                    "size_bytes": session.size_bytes,
                    "source_file_id": session.source_file_id,
                    "overall_status": session.status,
                    "progress_pct": session.progress_pct,
                },
                "trace_id": upload_id,
            }
            projector.record_and_apply(event)

        return session

    def list_uploads(self, user: CurrentUser, collection_id: str | None = None, status: str | None = None) -> list[WorkbenchUploadSession]:
        models = self._repository.list_by_user(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            collection_id=collection_id,
            status=status,
        )
        return [self._from_model(m) for m in models]

    def get_upload(self, upload_id: str, user: CurrentUser) -> WorkbenchUploadSession | None:
        model = self._repository.get(upload_id)
        if not model:
            return None
        if model.user_id != user.user_id:
            return None
        return self._from_model(model)

    def delete_upload(self, upload_id: str, user: CurrentUser) -> bool:
        model = self._repository.get(upload_id)
        if not model or model.user_id != user.user_id:
            return False
        return self._repository.delete(upload_id)

    async def upload_content(
        self,
        upload_id: str,
        user: CurrentUser,
        collection_id: str,
        filename: str,
        mime_type: str,
        content_bytes: bytes,
        access_scope_json: dict | None = None,
    ) -> WorkbenchUploadSession:
        model = self._repository.get(upload_id)
        if not model or model.user_id != user.user_id:
            raise ValueError("Upload not found or access denied")

        effective_access_scope = access_scope_json if access_scope_json is not None else model.access_scope_json
        visibility = _visibility_from_access_scope(effective_access_scope)

        try:
            result = await self._document_client.upload_file(
                collection_id=collection_id,
                visibility=visibility,
                filename=filename,
                content_bytes=content_bytes,
                mime_type=mime_type,
                upload_id=upload_id,
            )
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Document service upload API not yet implemented") from e
            elif e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Document service unavailable") from e
            else:
                raise downstream_unavailable(f"Document service error: {e.message}") from e

        if not model.source_file_id:
            model.source_file_id = result.get("source_file_id") or model.source_file_id
        model.access_scope_json = effective_access_scope
        raw_status = result.get("status")
        model.status = raw_status.lower() if isinstance(raw_status, str) else "uploaded"
        model.progress_pct = 100
        model.error_message = None
        if result.get("duplicate"):
            model.status = "duplicate"
        self._repository.save(model)

        updated = self._from_model(model)

        # Update task projection row
        if self._db_session is not None:
            projector = ProjectionProjector(self._db_session)
            now = datetime.now(timezone.utc)
            event = {
                "event_id": f"ev_{upload_id}_content_uploaded",
                "event_type": "TASK_CONTENT_UPLOADED",
                "tenant_id": updated.tenant_id,
                "collection_id": updated.collection_id,
                "aggregate_type": "task",
                "aggregate_id": upload_id,
                "aggregate_version": 2,
                "occurred_at": now,
                "payload": {
                    "projection_id": upload_id,
                    "tenant_id": updated.tenant_id,
                    "user_id": updated.user_id,
                    "collection_id": updated.collection_id,
                    "upload_id": upload_id,
                    "filename": updated.filename,
                    "mime_type": updated.mime_type,
                    "size_bytes": updated.size_bytes,
                    "source_file_id": updated.source_file_id,
                    "overall_status": updated.status,
                    "progress_pct": updated.progress_pct,
                },
                "trace_id": upload_id,
            }
            projector.record_and_apply(event)

        return updated

    @staticmethod
    def _to_model(session: WorkbenchUploadSession) -> object:
        from reality_rag_persistence.models import WorkbenchUploadSessionModel
        return WorkbenchUploadSessionModel(
            upload_id=session.upload_id,
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            collection_id=session.collection_id,
            source_file_id=session.source_file_id,
            intake_job_id=session.intake_job_id,
            parse_snapshot_id=session.parse_snapshot_id,
            ticket_id=session.ticket_id,
            selected_parser_profile_id=session.selected_parser_profile_id,
            parser_override_json=session.parser_override_json,
            access_scope_json=session.access_scope_json,
            status=session.status,
            progress_pct=session.progress_pct,
            filename=session.filename,
            mime_type=session.mime_type,
            size_bytes=session.size_bytes,
            error_message=session.error_message,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    @staticmethod
    def _from_model(model: object) -> WorkbenchUploadSession:
        return WorkbenchUploadSession(
            upload_id=model.upload_id,
            user_id=model.user_id,
            tenant_id=model.tenant_id,
            collection_id=model.collection_id,
            source_file_id=model.source_file_id,
            intake_job_id=model.intake_job_id,
            parse_snapshot_id=model.parse_snapshot_id,
            ticket_id=model.ticket_id,
            selected_parser_profile_id=model.selected_parser_profile_id,
            parser_override_json=model.parser_override_json,
            access_scope_json=model.access_scope_json,
            status=model.status,
            progress_pct=model.progress_pct,
            filename=model.filename,
            mime_type=model.mime_type,
            size_bytes=model.size_bytes,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
