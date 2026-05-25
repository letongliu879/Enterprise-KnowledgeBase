"""Approval audit log repository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import ApprovalAction, ApprovalAuditLog

from ..models import ApprovalAuditLogModel


class ApprovalAuditLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, audit_id: str) -> ApprovalAuditLog | None:
        row = self._session.get(ApprovalAuditLogModel, audit_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_ticket(self, ticket_id: str) -> list[ApprovalAuditLog]:
        rows = (
            self._session.query(ApprovalAuditLogModel)
            .filter(ApprovalAuditLogModel.ticket_id == ticket_id)
            .order_by(ApprovalAuditLogModel.created_at.asc())
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def append(
        self,
        *,
        audit_id: str,
        ticket_id: str,
        intake_job_id: str,
        actor_id: str,
        action: ApprovalAction,
        before_state: str | None,
        after_state: str | None,
        reason: str | None,
        payload_hash: str,
    ) -> ApprovalAuditLog:
        now = datetime.now(timezone.utc)
        row = ApprovalAuditLogModel(
            audit_id=audit_id,
            ticket_id=ticket_id,
            intake_job_id=intake_job_id,
            actor_id=actor_id,
            action=action.value,
            before_state=before_state,
            after_state=after_state,
            reason=reason,
            payload_hash=payload_hash,
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    @staticmethod
    def _to_contract(row: ApprovalAuditLogModel) -> ApprovalAuditLog:
        return ApprovalAuditLog(
            audit_id=row.audit_id,
            ticket_id=row.ticket_id,
            intake_job_id=row.intake_job_id,
            actor_id=row.actor_id,
            action=ApprovalAction(row.action),
            before_state=row.before_state,
            after_state=row.after_state,
            reason=row.reason,
            payload_hash=row.payload_hash,
            created_at=row.created_at,
        )
