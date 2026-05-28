"""Approval ticket repository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import ApprovalTicket, ApprovalTicketState, VersionDecision

from ..models import ApprovalTicketModel


class ApprovalTicketRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, ticket_id: str) -> ApprovalTicket | None:
        row = self._session.get(ApprovalTicketModel, ticket_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_intake_job(self, intake_job_id: str) -> list[ApprovalTicket]:
        rows = (
            self._session.query(ApprovalTicketModel)
            .filter(ApprovalTicketModel.intake_job_id == intake_job_id)
            .order_by(ApprovalTicketModel.created_at.asc())
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def create(self, ticket: ApprovalTicket) -> ApprovalTicket:
        row = ApprovalTicketModel(
            ticket_id=ticket.ticket_id,
            intake_job_id=ticket.intake_job_id,
            tenant_id=ticket.tenant_id,
            approval_round=ticket.approval_round,
            preliminary_doc_id=ticket.preliminary_doc_id,
            collection_id=ticket.collection_id,
            state=ticket.state.value,
            routing_recommendation=ticket.routing_recommendation,
            decision=ticket.decision,
            decision_actor=ticket.decision_actor,
            decision_reason=ticket.decision_reason,
            final_doc_id=ticket.final_doc_id,
            confirmed_tags=ticket.confirmed_tags,
            return_target_stage=ticket.return_target_stage,
            return_reason=ticket.return_reason,
            version_decision=ticket.version_decision.value if ticket.version_decision else None,
            supersedes_final_doc_id=ticket.supersedes_final_doc_id,
            created_at=ticket.created_at or datetime.now(timezone.utc),
            decided_at=ticket.decided_at,
            expires_at=ticket.expires_at,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(self, ticket_id: str, new_state: ApprovalTicketState, **fields) -> ApprovalTicket | None:
        row = self._session.get(ApprovalTicketModel, ticket_id)
        if row is None:
            return None
        row.state = new_state.value
        row.decided_at = datetime.now(timezone.utc)
        for key, value in fields.items():
            if hasattr(row, key):
                setattr(row, key, value)
        self._session.flush()
        return self._to_contract(row)

    def list_all(self) -> list[ApprovalTicket]:
        rows = self._session.query(ApprovalTicketModel).all()
        return [self._to_contract(r) for r in rows]

    @staticmethod
    def _to_contract(row: ApprovalTicketModel) -> ApprovalTicket:
        return ApprovalTicket(
            ticket_id=row.ticket_id,
            intake_job_id=row.intake_job_id,
            tenant_id=row.tenant_id,
            approval_round=row.approval_round,
            preliminary_doc_id=row.preliminary_doc_id,
            collection_id=row.collection_id,
            state=ApprovalTicketState(row.state),
            routing_recommendation=row.routing_recommendation,
            decision=row.decision,
            decision_actor=row.decision_actor,
            decision_reason=row.decision_reason,
            final_doc_id=row.final_doc_id,
            confirmed_tags=row.confirmed_tags or [],
            return_target_stage=row.return_target_stage,
            return_reason=row.return_reason,
            version_decision=VersionDecision(row.version_decision) if row.version_decision else None,
            supersedes_final_doc_id=row.supersedes_final_doc_id,
            created_at=row.created_at,
            decided_at=row.decided_at,
            expires_at=row.expires_at,
        )
