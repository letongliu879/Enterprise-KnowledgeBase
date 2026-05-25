from __future__ import annotations

from sqlalchemy.orm import Session

from indexing_service.domain import ParseSnapshotRecord

from ..models import ParseSnapshotModel


class ParseSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, parse_snapshot_id: str) -> ParseSnapshotRecord | None:
        row = self._session.get(ParseSnapshotModel, parse_snapshot_id)
        if row is None:
            return None
        return self._to_record(row)

    def save(self, snapshot: ParseSnapshotRecord) -> ParseSnapshotRecord:
        row = ParseSnapshotModel(
            parse_snapshot_id=snapshot.parse_snapshot_id,
            request_id=snapshot.request_id,
            tenant_id=snapshot.tenant_id,
            collection_id=snapshot.collection_id,
            source_file_id=snapshot.source_file_id,
            source_binary_ref=snapshot.source_binary_ref,
            source_filename=snapshot.source_filename,
            source_suffix=snapshot.source_suffix,
            parser_id=snapshot.parser_id,
            parser_backend=snapshot.parser_backend,
            collection_parser_config=snapshot.collection_parser_config,
            parser_config=snapshot.parser_config,
            input_hash=snapshot.input_hash,
            preview_text=snapshot.preview_text,
            upstream_chunks=snapshot.upstream_chunks,
            outline=snapshot.outline,
            document_metadata=snapshot.document_metadata,
            chunk_preview=snapshot.chunk_preview,
            warnings=snapshot.warnings,
            decision_reason=snapshot.decision_reason,
            created_at=snapshot.created_at,
        )
        self._session.merge(row)
        self._session.flush()
        return snapshot

    @staticmethod
    def _to_record(row: ParseSnapshotModel) -> ParseSnapshotRecord:
        return ParseSnapshotRecord(
            parse_snapshot_id=row.parse_snapshot_id,
            request_id=row.request_id,
            tenant_id=row.tenant_id,
            collection_id=row.collection_id,
            source_file_id=row.source_file_id,
            source_binary_ref=row.source_binary_ref,
            source_filename=row.source_filename,
            source_suffix=row.source_suffix,
            parser_id=row.parser_id,
            parser_backend=row.parser_backend,
            collection_parser_config=row.collection_parser_config or {},
            parser_config=row.parser_config or {},
            input_hash=row.input_hash,
            preview_text=row.preview_text or "",
            upstream_chunks=row.upstream_chunks or [],
            outline=row.outline or [],
            document_metadata=row.document_metadata or {},
            chunk_preview=row.chunk_preview or [],
            warnings=row.warnings or [],
            decision_reason=row.decision_reason or "",
            created_at=row.created_at,
        )
