"""Chunk edit service."""

import uuid
from datetime import datetime, timezone

from reality_rag_contracts.models import WorkbenchChunkEdit

from ..deps import CurrentUser
from ..downstream_clients import IndexingClient
from ..downstream_clients.errors import DownstreamError
from .models import ChunkEditCreateRequest, ChunkEditUpdateRequest
from .repository import ChunkEditRepository


class ChunkEditService:
    def __init__(self, repository: ChunkEditRepository, indexing_client: IndexingClient | None = None):
        self._repository = repository
        self._indexing_client = indexing_client or IndexingClient()

    def create_chunk_edit(self, parse_snapshot_id: str, source_file_id: str, tenant_id: str, collection_id: str, req: ChunkEditCreateRequest, user: CurrentUser) -> WorkbenchChunkEdit:
        chunk_edit_id = f"ce_{uuid.uuid4().hex[:16]}"
        edit = WorkbenchChunkEdit(
            chunk_edit_id=chunk_edit_id,
            tenant_id=tenant_id,
            collection_id=collection_id,
            source_file_id=source_file_id,
            parse_snapshot_id=parse_snapshot_id,
            base_evidence_id=req.base_evidence_id,
            edit_scope="pre_publish",
            operation=req.operation,
            content=req.content,
            vector_text=req.vector_text,
            section_path=req.section_path,
            metadata_patch=req.metadata_patch,
            citation_payload=req.citation_payload,
            source_block_ids=req.source_block_ids,
            edit_reason=req.edit_reason,
            edited_by=user.user_id,
            status="draft",
        )
        self._repository.save(self._to_model(edit))
        return edit

    def list_chunk_edits(self, parse_snapshot_id: str) -> list[WorkbenchChunkEdit]:
        models = self._repository.list_by_snapshot(parse_snapshot_id)
        return [self._from_model(m) for m in models]

    def get_chunk_edit(self, chunk_edit_id: str) -> WorkbenchChunkEdit | None:
        model = self._repository.get(chunk_edit_id)
        if not model:
            return None
        return self._from_model(model)

    def update_chunk_edit(self, chunk_edit_id: str, req: ChunkEditUpdateRequest, user: CurrentUser) -> WorkbenchChunkEdit | None:
        model = self._repository.get(chunk_edit_id)
        if not model:
            return None
        if model.edited_by != user.user_id:
            return None
        if req.content is not None:
            model.content = req.content
        if req.vector_text is not None:
            model.vector_text = req.vector_text
        if req.section_path is not None:
            model.section_path = req.section_path
        if req.metadata_patch is not None:
            model.metadata_patch = req.metadata_patch
        if req.citation_payload is not None:
            model.citation_payload = req.citation_payload
        if req.source_block_ids is not None:
            model.source_block_ids = req.source_block_ids
        if req.edit_reason is not None:
            model.edit_reason = req.edit_reason
        if req.operation is not None:
            model.operation = req.operation
        model.updated_at = datetime.now(timezone.utc)
        self._repository.save(model)
        return self._from_model(model)

    def delete_chunk_edit(self, chunk_edit_id: str, user: CurrentUser) -> bool:
        model = self._repository.get(chunk_edit_id)
        if not model or model.edited_by != user.user_id:
            return False
        return self._repository.delete(chunk_edit_id)

    async def submit_chunk_edit(self, chunk_edit_id: str, user: CurrentUser) -> WorkbenchChunkEdit | None:
        model = self._repository.get(chunk_edit_id)
        if not model or model.edited_by != user.user_id:
            return None
        if model.status != "draft":
            return self._from_model(model)

        command = {
            "command_id": f"cmd_{uuid.uuid4().hex[:12]}",
            "trace_id": f"trc_{uuid.uuid4().hex[:12]}",
            "idempotency_key": chunk_edit_id,
            "actor": user.user_id,
            "tenant_id": model.tenant_id,
            "collection_id": model.collection_id,
            "target_type": "chunk",
            "target_id": model.base_evidence_id,
            "payload": {
                "evidence_id": model.base_evidence_id,
                "doc_id": model.source_file_id,
                "operation": model.operation,
                "content": model.content,
                "vector_text": model.vector_text,
                "section_path": model.section_path,
                "metadata_patch": model.metadata_patch,
                "citation_payload": model.citation_payload,
            },
        }
        result = await self._indexing_client.create_chunk_revision(model.base_evidence_id, command)
        downstream_revision_id = result.get("revision_id")

        # Atomic update with optimistic lock (status must still be 'draft')
        if not self._repository.submit(chunk_edit_id, downstream_revision_id):
            # Another request already submitted this edit
            model = self._repository.get(chunk_edit_id)
            return self._from_model(model) if model else None

        model.downstream_revision_id = downstream_revision_id
        model.status = "submitted"
        model.updated_at = datetime.now(timezone.utc)
        return self._from_model(model)

    @staticmethod
    def _to_model(edit: WorkbenchChunkEdit) -> object:
        from reality_rag_persistence.models import WorkbenchChunkEditModel
        return WorkbenchChunkEditModel(
            chunk_edit_id=edit.chunk_edit_id,
            tenant_id=edit.tenant_id,
            collection_id=edit.collection_id,
            source_file_id=edit.source_file_id,
            parse_snapshot_id=edit.parse_snapshot_id,
            base_evidence_id=edit.base_evidence_id,
            edit_scope=edit.edit_scope,
            operation=edit.operation,
            content=edit.content,
            vector_text=edit.vector_text,
            section_path=edit.section_path,
            metadata_patch=edit.metadata_patch,
            citation_payload=edit.citation_payload,
            source_block_ids=edit.source_block_ids,
            edit_reason=edit.edit_reason,
            edited_by=edit.edited_by,
            status=edit.status,
            downstream_revision_id=edit.downstream_revision_id,
            created_at=edit.created_at,
            updated_at=edit.updated_at,
        )

    @staticmethod
    def _from_model(model: object) -> WorkbenchChunkEdit:
        return WorkbenchChunkEdit(
            chunk_edit_id=model.chunk_edit_id,
            tenant_id=model.tenant_id,
            collection_id=model.collection_id,
            source_file_id=model.source_file_id,
            parse_snapshot_id=model.parse_snapshot_id,
            base_evidence_id=model.base_evidence_id,
            edit_scope=model.edit_scope,
            operation=model.operation,
            content=model.content,
            vector_text=model.vector_text,
            section_path=model.section_path,
            metadata_patch=model.metadata_patch,
            citation_payload=model.citation_payload,
            source_block_ids=model.source_block_ids,
            edit_reason=model.edit_reason,
            edited_by=model.edited_by,
            status=model.status,
            downstream_revision_id=model.downstream_revision_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
