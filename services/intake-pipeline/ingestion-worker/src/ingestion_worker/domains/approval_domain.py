"""Approval domain facade.

`approval-service` is the approval owner and must be reached through its split
service HTTP API from ingestion-worker code.
"""

from __future__ import annotations

from typing import Any

from reality_rag_contracts import (
    AgentReview,
    ApprovalTicket,
    PublishStatus,
    QualityReport,
)

__all__ = [
    "system_decide",
    "ApprovalService",
]


def system_decide(
    quality_report: QualityReport | None,
    agent_review: AgentReview | None,
) -> PublishStatus:
    """Resolve publish_status from quality report and agent review."""
    from approval_service.approval_domain import system_decide as _native

    return _native(quality_report, agent_review)


class ApprovalService:
    """Local facade for the approval-service owner.

    Since services are co-located (not independently deployed), methods delegate
directly to the approval-service domain layer rather than going through HTTP.
    """

    def __init__(self, session=None) -> None:
        self._session = session

    def _get_service(self):
        from approval_service.approval_domain import ApprovalService as _NativeApprovalService
        return _NativeApprovalService(self._session)

    def submit_auto_approve(self, **kwargs: Any) -> ApprovalTicket:
        return self._get_service().submit_auto_approve(**kwargs)

    def submit_auto_reject(self, **kwargs: Any) -> ApprovalTicket:
        return self._get_service().submit_auto_reject(**kwargs)

    def create_pending(self, **kwargs: Any) -> ApprovalTicket:
        return self._get_service().create_pending(**kwargs)

    def approve(self, **kwargs: Any) -> ApprovalTicket:
        return self._get_service().approve(**kwargs)

    def reject(self, **kwargs: Any) -> ApprovalTicket:
        return self._get_service().reject(**kwargs)

    def return_to_stage(self, **kwargs: Any) -> tuple[ApprovalTicket, ApprovalTicket]:
        return self._get_service().return_to_stage(**kwargs)

    def expire(self, **kwargs: Any) -> ApprovalTicket:
        return self._get_service().expire(**kwargs)

    def get_ticket_history(self, intake_job_id: str) -> list[ApprovalTicket]:
        return self._get_service().get_ticket_history(intake_job_id)
