"""Approval domain facade.

`approval-service` is the approval owner. `ingestion-worker` may use a
same-process fallback only in tests or explicit compat smoke.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from ingestion_worker.split_service_policy import require_explicit_owner_url

from reality_rag_contracts import (
    AgentReview,
    ApprovalTicket,
    PublishStatus,
    QualityReport,
    VersionDecision,
)

__all__ = [
    "system_decide",
    "ApprovalService",
]

_REMOTE_URL: str | None = None


def _get_remote_url() -> str | None:
    global _REMOTE_URL
    if _REMOTE_URL is None:
        _REMOTE_URL = os.environ.get("APPROVAL_SERVICE_URL", "").rstrip("/") or None
    return _REMOTE_URL


def _url(path: str) -> str:
    base = _get_remote_url()
    assert base is not None
    return f"{base}{path}"


# ── Pure function (always local) ──────────────────────────────────────

def system_decide(
    quality_report: QualityReport | None,
    agent_review: AgentReview | None,
) -> PublishStatus:
    """Resolve publish_status from quality report and agent review.

    Pure function — always executed locally; never forwarded.
    """
    from approval_service.approval_domain import system_decide as _native

    return _native(quality_report, agent_review)


# ── Remote client ─────────────────────────────────────────────────────

class _RemoteApprovalService:
    """HTTP client facade that mirrors ApprovalService API."""

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(_url(path), json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(resp.text)
            return resp.json()

    def submit_auto_approve(
        self,
        *,
        intake_job_id: str,
        preliminary_doc_id: str,
        collection_id: str,
        logical_document_id: str,
        version: int,
        confirmed_tags: list[str] | None = None,
        version_conflict: dict | None = None,
    ) -> ApprovalTicket:
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            self._post(
                "/internal/approval/auto-approve",
                {
                    "intake_job_id": intake_job_id,
                    "preliminary_doc_id": preliminary_doc_id,
                    "collection_id": collection_id,
                    "logical_document_id": logical_document_id,
                    "version": version,
                    "confirmed_tags": confirmed_tags or [],
                },
            )
        )
        return ApprovalTicket.model_validate(result)

    def submit_auto_reject(
        self,
        *,
        intake_job_id: str,
        preliminary_doc_id: str,
        collection_id: str,
        rejection_reason: str,
    ) -> ApprovalTicket:
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            self._post(
                "/internal/approval/auto-reject",
                {
                    "intake_job_id": intake_job_id,
                    "preliminary_doc_id": preliminary_doc_id,
                    "collection_id": collection_id,
                    "rejection_reason": rejection_reason,
                },
            )
        )
        return ApprovalTicket.model_validate(result)

    def create_pending(
        self,
        *,
        intake_job_id: str,
        preliminary_doc_id: str,
        collection_id: str,
        routing_recommendation: str = "require_approval",
    ) -> ApprovalTicket:
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            self._post(
                "/internal/approval/pending",
                {
                    "intake_job_id": intake_job_id,
                    "preliminary_doc_id": preliminary_doc_id,
                    "collection_id": collection_id,
                    "routing_recommendation": routing_recommendation,
                },
            )
        )
        return ApprovalTicket.model_validate(result)

    def approve(
        self,
        *,
        ticket_id: str,
        actor_id: str,
        confirmed_tags: list[str] | None = None,
        version_decision: VersionDecision | None = None,
        supersedes_final_doc_id: str | None = None,
    ) -> ApprovalTicket:
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            self._post(
                f"/internal/approval/{ticket_id}/approve",
                {
                    "actor_id": actor_id,
                    "confirmed_tags": confirmed_tags or [],
                    "version_decision": version_decision.value if version_decision else None,
                    "supersedes_final_doc_id": supersedes_final_doc_id,
                },
            )
        )
        return ApprovalTicket.model_validate(result)

    def reject(
        self,
        *,
        ticket_id: str,
        actor_id: str,
        rejection_reason: str,
    ) -> ApprovalTicket:
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            self._post(
                f"/internal/approval/{ticket_id}/reject",
                {
                    "actor_id": actor_id,
                    "rejection_reason": rejection_reason,
                },
            )
        )
        return ApprovalTicket.model_validate(result)

    def return_to_stage(
        self,
        *,
        ticket_id: str,
        actor_id: str,
        return_target_stage: str,
        return_reason: str,
    ) -> tuple[ApprovalTicket, ApprovalTicket]:
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            self._post(
                f"/internal/approval/{ticket_id}/return",
                {
                    "actor_id": actor_id,
                    "return_target_stage": return_target_stage,
                    "return_reason": return_reason,
                },
            )
        )
        return (
            ApprovalTicket.model_validate(result["returned"]),
            ApprovalTicket.model_validate(result["new_pending"]),
        )

    def expire(self, *, ticket_id: str) -> ApprovalTicket:
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            self._post(
                f"/internal/approval/{ticket_id}/expire",
                {},
            )
        )
        return ApprovalTicket.model_validate(result)

    def get_ticket_history(self, intake_job_id: str) -> list[ApprovalTicket]:
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            self._get(f"/internal/approval/{intake_job_id}/history")
        )
        return [ApprovalTicket.model_validate(t) for t in result]

    async def _get(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(_url(path))
            if resp.status_code >= 400:
                raise RuntimeError(resp.text)
            return resp.json()


# ── Fallback facade ───────────────────────────────────────────────────

class ApprovalService:
    """Dispatches to remote HTTP or, only in tests, a local compat fallback."""

    def __init__(self, session=None) -> None:
        self._session = session
        self._local = None
        self._remote: _RemoteApprovalService | None = None

    def _use_remote(self) -> bool:
        return _get_remote_url() is not None

    def _get_local(self):
        if self._local is None:
            from approval_service.approval_domain import ApprovalService as _NativeApprovalService

            if self._session is None:
                raise RuntimeError("ApprovalService requires a session in local mode")
            require_explicit_owner_url(
                env_var="APPROVAL_SERVICE_URL",
                owner_name="approval-service",
            )
            self._local = _NativeApprovalService(self._session)
        return self._local

    def _get_remote(self) -> _RemoteApprovalService:
        if self._remote is None:
            self._remote = _RemoteApprovalService()
        return self._remote

    def submit_auto_approve(self, **kwargs: Any) -> ApprovalTicket:
        if self._use_remote():
            return self._get_remote().submit_auto_approve(**kwargs)
        return self._get_local().submit_auto_approve(**kwargs)

    def submit_auto_reject(self, **kwargs: Any) -> ApprovalTicket:
        if self._use_remote():
            return self._get_remote().submit_auto_reject(**kwargs)
        return self._get_local().submit_auto_reject(**kwargs)

    def create_pending(self, **kwargs: Any) -> ApprovalTicket:
        if self._use_remote():
            return self._get_remote().create_pending(**kwargs)
        return self._get_local().create_pending(**kwargs)

    def approve(self, **kwargs: Any) -> ApprovalTicket:
        if self._use_remote():
            return self._get_remote().approve(**kwargs)
        return self._get_local().approve(**kwargs)

    def reject(self, **kwargs: Any) -> ApprovalTicket:
        if self._use_remote():
            return self._get_remote().reject(**kwargs)
        return self._get_local().reject(**kwargs)

    def return_to_stage(self, **kwargs: Any) -> tuple[ApprovalTicket, ApprovalTicket]:
        if self._use_remote():
            return self._get_remote().return_to_stage(**kwargs)
        return self._get_local().return_to_stage(**kwargs)

    def expire(self, **kwargs: Any) -> ApprovalTicket:
        if self._use_remote():
            return self._get_remote().expire(**kwargs)
        return self._get_local().expire(**kwargs)

    def get_ticket_history(self, intake_job_id: str) -> list[ApprovalTicket]:
        if self._use_remote():
            return self._get_remote().get_ticket_history(intake_job_id)
        return self._get_local().get_ticket_history(intake_job_id)

    def _generate_final_doc_id(self, **kwargs: Any) -> str:
        return self._get_local()._generate_final_doc_id(**kwargs)
