"""Upload session service."""

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from reality_rag_contracts.models import WorkbenchUploadSession

from ..deps import CurrentUser
from ..downstream_clients import IntakeClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, conflict
from .repository import UploadSessionRepository


class UploadSessionService:
    def __init__(self, repository: UploadSessionRepository, intake_client: IntakeClient, actor_id: str):
        self._repository = repository
        self._intake_client = intake_client
        self._actor_id = actor_id

    async def create_upload(self, req: dict, user: CurrentUser) -> WorkbenchUploadSession:
        upload_id = f"upload_{uuid.uuid4().hex[:16]}"
        trace_id = f"trc_{uuid.uuid4().hex[:16]}"

        # Build command envelope for intake
        command = {
            "command_id": f"cmd_{uuid.uuid4().hex[:16]}",
            "trace_id": trace_id,
            "idempotency_key": upload_id,
            "actor": self._actor_id,
            "tenant_id": user.tenant_id,
            "collection_id": req["collection_id"],
            "target_type": "source_file",
            "target_id": upload_id,
            "payload": {
                "upload_id": upload_id,
                "filename": req["filename"],
                "mime_type": req["mime_type"],
                "size_bytes": req["size_bytes"],
                "selected_parser_profile_id": req.get("selected_parser_profile_id"),
                "parser_override_json": req.get("parser_override_json"),
            },
        }

        # Call intake to register source file
        source_file_id: str | None = None
        error_message: str | None = None
        try:
            result = await self._intake_client.create_source_file(command)
            source_file_id = result.get("source_file_id")
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                error_message = "Intake source-files API not yet implemented"
            elif e.code == "DOWNSTREAM_UNAVAILABLE":
                error_message = "Intake service unavailable"
            else:
                error_message = f"Intake error: {e.message}"

        session = WorkbenchUploadSession(
            upload_id=upload_id,
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            collection_id=req["collection_id"],
            source_file_id=source_file_id,
            status="uploading" if not error_message else "failed",
            progress_pct=0,
            filename=req["filename"],
            mime_type=req["mime_type"],
            size_bytes=req["size_bytes"],
            error_message=error_message,
            selected_parser_profile_id=req.get("selected_parser_profile_id"),
            parser_override_json=req.get("parser_override_json"),
        )
        self._repository.save(self._to_model(session))
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
            status=model.status,
            progress_pct=model.progress_pct,
            filename=model.filename,
            mime_type=model.mime_type,
            size_bytes=model.size_bytes,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
