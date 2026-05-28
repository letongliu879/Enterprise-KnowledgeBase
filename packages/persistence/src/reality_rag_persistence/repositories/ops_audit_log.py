"""Ops audit log repository."""

from sqlalchemy.orm import Session

from reality_rag_contracts import OpsAuditLogEntry

from ..models import OpsAuditLogModel


class OpsAuditLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, audit_id: str) -> OpsAuditLogEntry | None:
        row = self._session.get(OpsAuditLogModel, audit_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_all(
        self,
        *,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        tenant_id: str | None = None,
        collection_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OpsAuditLogEntry]:
        query = self._session.query(OpsAuditLogModel)
        if actor_id:
            query = query.filter(OpsAuditLogModel.actor_id == actor_id)
        if target_type:
            query = query.filter(OpsAuditLogModel.target_type == target_type)
        if target_id:
            query = query.filter(OpsAuditLogModel.target_id == target_id)
        if tenant_id:
            query = query.filter(OpsAuditLogModel.tenant_id == tenant_id)
        if collection_id:
            query = query.filter(OpsAuditLogModel.collection_id == collection_id)
        rows = (
            query.order_by(OpsAuditLogModel.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [self._to_contract(row) for row in rows]

    def count(
        self,
        *,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        tenant_id: str | None = None,
        collection_id: str | None = None,
    ) -> int:
        query = self._session.query(OpsAuditLogModel)
        if actor_id:
            query = query.filter(OpsAuditLogModel.actor_id == actor_id)
        if target_type:
            query = query.filter(OpsAuditLogModel.target_type == target_type)
        if target_id:
            query = query.filter(OpsAuditLogModel.target_id == target_id)
        if tenant_id:
            query = query.filter(OpsAuditLogModel.tenant_id == tenant_id)
        if collection_id:
            query = query.filter(OpsAuditLogModel.collection_id == collection_id)
        return query.count()

    def save(self, entry: OpsAuditLogEntry) -> None:
        row = OpsAuditLogModel(
            audit_id=entry.audit_id,
            command_id=entry.command_id,
            trace_id=entry.trace_id,
            idempotency_key=entry.idempotency_key,
            actor_id=entry.actor_id,
            tenant_id=entry.tenant_id,
            collection_id=entry.collection_id,
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            before_state=entry.before_state,
            after_state=entry.after_state,
            reason=entry.reason,
            payload_hash=entry.payload_hash,
            created_at=entry.created_at,
        )
        self._session.add(row)
        self._session.flush()

    @staticmethod
    def _to_contract(row: OpsAuditLogModel) -> OpsAuditLogEntry:
        return OpsAuditLogEntry(
            audit_id=row.audit_id,
            command_id=row.command_id or "",
            trace_id=row.trace_id or "",
            idempotency_key=row.idempotency_key or "",
            actor_id=row.actor_id,
            tenant_id=row.tenant_id or "",
            collection_id=row.collection_id,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            before_state=row.before_state,
            after_state=row.after_state,
            reason=row.reason,
            payload_hash=row.payload_hash or "",
            created_at=row.created_at,
        )
