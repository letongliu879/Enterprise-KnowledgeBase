"""Approval service tests — Phase 8 (moved from ingestion-worker).

These tests verify:
  - auto approve creates SYSTEM_DECIDED ticket + audit + final_doc_id
  - reject does NOT generate final_doc_id
  - return creates new ticket with incremented approval_round
  - manual approve/reject lifecycle
  - audit log is append-only
  - version_conflict decisions
"""

from __future__ import annotations

import pytest

from reality_rag_contracts import (
    ApprovalAction,
    ApprovalTicketState,
    EventType,
    PublishStatus,
    VersionDecision,
)
from reality_rag_persistence.database import create_all, drop_all, override_url_for_testing
from reality_rag_persistence.models import StageResultModel
from reality_rag_persistence.repositories.approval_audit_log import ApprovalAuditLogRepository
from reality_rag_persistence.repositories.approval_tickets import ApprovalTicketRepository
from reality_rag_persistence.repositories.outbox_events import OutboxEventRepository

from approval_service.approval_domain import ApprovalService, system_decide


@pytest.fixture(autouse=True)
def _db():
    override_url_for_testing("sqlite:///:memory:")
    create_all()
    yield
    drop_all()


@pytest.fixture
def session():
    from reality_rag_persistence.database import get_session

    s = get_session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def approval_svc(session):
    return ApprovalService(session)


# ── system_decide pure function (unchanged from Phase 3) ───────────────


class TestSystemDecide:
    def test_approve_uses_publish_recommendation(self):
        from reality_rag_contracts import AgentReview, QualityReport, ReviewDecision

        qr = QualityReport(doc_id="d", recommended_review_status=PublishStatus.PENDING_REVIEW)
        ar = AgentReview(
            doc_id="d",
            decision=ReviewDecision.APPROVE,
            publish_recommendation=PublishStatus.PUBLISHED,
        )
        assert system_decide(qr, ar) == PublishStatus.PUBLISHED

    def test_reject_maps_to_rejected(self):
        from reality_rag_contracts import AgentReview, QualityReport, ReviewDecision

        qr = QualityReport(doc_id="d", recommended_review_status=PublishStatus.PUBLISHED)
        ar = AgentReview(
            doc_id="d",
            decision=ReviewDecision.REJECT,
            publish_recommendation=PublishStatus.REJECTED,
        )
        assert system_decide(qr, ar) == PublishStatus.REJECTED

    def test_high_authority_policy_requires_pending_review(self):
        from reality_rag_contracts import AgentReview, QualityReport, ReviewDecision

        qr = QualityReport(doc_id="d", recommended_review_status=PublishStatus.PUBLISHED)
        ar = AgentReview(
            doc_id="d",
            decision=ReviewDecision.APPROVE,
            publish_recommendation=PublishStatus.PUBLISHED,
            document_type="privacy_policy",
            suggested_authority_level=7,
        )
        assert system_decide(qr, ar) == PublishStatus.PENDING_REVIEW


# ── Auto approve / auto reject ─────────────────────────────────────────


class TestAutoApprove:
    def test_creates_system_decided_ticket(self, approval_svc):
        ticket = approval_svc.submit_auto_approve(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
            logical_document_id="test-abc",
            version=1,
        )
        assert ticket is not None
        assert ticket.state == ApprovalTicketState.SYSTEM_DECIDED
        assert ticket.decision == "approve"
        assert ticket.decision_actor == "system"
        assert ticket.approval_round == 1

    def test_generates_final_doc_id(self, approval_svc):
        ticket = approval_svc.submit_auto_approve(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
            logical_document_id="test-abc",
            version=1,
        )
        assert ticket.final_doc_id == "doc-test-v1"
        assert ticket.final_doc_id is not None

    def test_creates_audit_log(self, approval_svc, session):
        ticket = approval_svc.submit_auto_approve(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
            logical_document_id="test-abc",
            version=1,
        )
        audits = ApprovalAuditLogRepository(session).get_by_ticket(ticket.ticket_id)
        assert len(audits) == 1
        assert audits[0].action == ApprovalAction.SYSTEM_APPROVE
        assert audits[0].after_state == ApprovalTicketState.SYSTEM_DECIDED.value

    def test_confirmed_tags_persisted(self, approval_svc):
        ticket = approval_svc.submit_auto_approve(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
            logical_document_id="test-abc",
            version=1,
            confirmed_tags=["financial_report"],
        )
        assert ticket.confirmed_tags == ["financial_report"]

    def test_pending_event_includes_artifact_findings(self, approval_svc, session):
        session.add(
            StageResultModel(
                stage_result_id="res_review_001",
                stage_task_id="task_review_001",
                stage_attempt_id="att_review_001",
                intake_job_id="ij-1",
                stage_name="agent_review",
                idempotency_key="review:key",
                result_hash="hash:review",
                summary_json={
                    "agent_review": {
                        "decision": "request_changes",
                        "anchored_findings": [
                            {
                                "finding_id": "finding_001",
                                "source_quote": "Original quote",
                                "problem_summary": "Needs correction",
                                "severity": "high",
                                "confidence": 0.91,
                            }
                        ],
                    },
                    "review_context": {
                        "artifact_metadata": {
                            "source_file_id": "sf_001",
                            "parse_snapshot_id": "ps_001",
                        }
                    },
                },
            )
        )
        session.flush()
        ticket = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        events = OutboxEventRepository(session).list_pending(limit=20)
        evt = next(
            e for e in events
            if e.event_type == EventType.APPROVAL_PENDING.value and e.payload["ticket_id"] == ticket.ticket_id
        )
        assert evt.payload["source_file_id"] == "sf_001"
        assert evt.payload["parse_snapshot_id"] == "ps_001"
        assert evt.payload["agent_finding_count"] == 1
        assert evt.payload["findings"][0]["finding_id"] == "finding_001"


class TestAutoReject:
    def test_creates_system_decided_ticket_without_final_doc_id(self, approval_svc):
        ticket = approval_svc.submit_auto_reject(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
            rejection_reason="质量不达标",
        )
        assert ticket is not None
        assert ticket.state == ApprovalTicketState.SYSTEM_DECIDED
        assert ticket.decision == "reject"
        assert ticket.final_doc_id is None

    def test_creates_audit_log(self, approval_svc, session):
        ticket = approval_svc.submit_auto_reject(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
            rejection_reason="质量不达标",
        )
        audits = ApprovalAuditLogRepository(session).get_by_ticket(ticket.ticket_id)
        assert len(audits) == 1
        assert audits[0].action == ApprovalAction.SYSTEM_REJECT
        assert audits[0].reason == "质量不达标"


# ── Manual approval lifecycle ──────────────────────────────────────────


class TestManualApprove:
    def test_approve_generates_final_doc_id(self, approval_svc):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        approved = approval_svc.approve(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
            confirmed_tags=["report"],
        )
        assert approved.state == ApprovalTicketState.APPROVED
        assert approved.final_doc_id == "doc-test-v1"
        assert approved.confirmed_tags == ["report"]

    def test_approve_creates_audit(self, approval_svc, session):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        approval_svc.approve(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
        )
        audits = ApprovalAuditLogRepository(session).get_by_ticket(pending.ticket_id)
        assert len(audits) == 1
        assert audits[0].action == ApprovalAction.APPROVE
        assert audits[0].before_state == ApprovalTicketState.PENDING.value
        assert audits[0].after_state == ApprovalTicketState.APPROVED.value

    def test_approve_emits_approval_decided_event(self, approval_svc, session):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        approved = approval_svc.approve(ticket_id=pending.ticket_id, actor_id="user_1")
        events = OutboxEventRepository(session).list_pending(limit=20)
        evt = next(
            e for e in events
            if e.event_type == EventType.APPROVAL_DECIDED.value and e.payload["ticket_id"] == pending.ticket_id
        )
        assert evt.payload["decision"] == "approve"
        assert evt.payload["final_doc_id"] == approved.final_doc_id

    def test_reject_no_final_doc_id(self, approval_svc):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        rejected = approval_svc.reject(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
            rejection_reason="敏感内容",
        )
        assert rejected.state == ApprovalTicketState.REJECTED
        assert rejected.final_doc_id is None

    def test_reject_creates_audit(self, approval_svc, session):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        approval_svc.reject(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
            rejection_reason="敏感内容",
        )
        audits = ApprovalAuditLogRepository(session).get_by_ticket(pending.ticket_id)
        assert len(audits) == 1
        assert audits[0].action == ApprovalAction.REJECT
        assert audits[0].reason == "敏感内容"


class TestReturn:
    def test_return_creates_returned_ticket_and_new_pending(self, approval_svc):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        returned, new_pending = approval_svc.return_to_stage(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
            return_target_stage="conversion",
            return_reason="需要补充内容",
        )
        assert returned.state == ApprovalTicketState.RETURNED
        assert returned.return_target_stage == "conversion"
        assert new_pending.state == ApprovalTicketState.PENDING
        assert new_pending.approval_round == 2
        assert new_pending.preliminary_doc_id == pending.preliminary_doc_id

    def test_return_creates_audit(self, approval_svc, session):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        approval_svc.return_to_stage(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
            return_target_stage="conversion",
            return_reason="需要补充内容",
        )
        audits = ApprovalAuditLogRepository(session).get_by_ticket(pending.ticket_id)
        assert len(audits) == 1
        assert audits[0].action == ApprovalAction.RETURN

    def test_return_preserves_history(self, approval_svc):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        approval_svc.return_to_stage(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
            return_target_stage="conversion",
            return_reason="需要补充内容",
        )
        history = approval_svc.get_ticket_history("ij-1")
        assert len(history) == 2
        assert history[0].state == ApprovalTicketState.RETURNED
        assert history[1].state == ApprovalTicketState.PENDING


class TestExpire:
    def test_expire_pending_ticket(self, approval_svc):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        expired = approval_svc.expire(ticket_id=pending.ticket_id)
        assert expired.state == ApprovalTicketState.EXPIRED

    def test_expire_creates_audit(self, approval_svc, session):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        approval_svc.expire(ticket_id=pending.ticket_id)
        audits = ApprovalAuditLogRepository(session).get_by_ticket(pending.ticket_id)
        assert len(audits) == 1
        assert audits[0].action == ApprovalAction.EXPIRE


# ── Audit log ──────────────────────────────────────────────────────────


class TestAuditLog:
    def test_append_only(self, approval_svc, session):
        ticket = approval_svc.submit_auto_approve(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
            logical_document_id="test-abc",
            version=1,
        )
        audits = ApprovalAuditLogRepository(session).get_by_ticket(ticket.ticket_id)
        assert len(audits) == 1
        first_audit = audits[0]
        assert first_audit.created_at is not None

    def test_tracks_state_transitions(self, approval_svc, session):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-test-v1",
            collection_id="col-1",
        )
        approval_svc.approve(ticket_id=pending.ticket_id, actor_id="user_1")
        audits = ApprovalAuditLogRepository(session).get_by_ticket(pending.ticket_id)
        assert len(audits) == 1
        assert audits[0].before_state == ApprovalTicketState.PENDING.value
        assert audits[0].after_state == ApprovalTicketState.APPROVED.value


# ── Version conflict ───────────────────────────────────────────────────


class TestVersionConflict:
    def test_new_version_uses_preliminary_doc_id(self, approval_svc):
        ticket = approval_svc.submit_auto_approve(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-contract-v2",
            collection_id="col-1",
            logical_document_id="contract",
            version=2,
        )
        assert ticket.final_doc_id == "doc-contract-v2"

    def test_independent_document_generates_new_doc_id(self, approval_svc):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-contract-v2",
            collection_id="col-1",
        )
        approved = approval_svc.approve(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
            version_decision=VersionDecision.INDEPENDENT_DOCUMENT,
        )
        assert approved.final_doc_id != "doc-contract-v2"
        assert "-v1" in approved.final_doc_id

    def test_business_duplicate_raises(self, approval_svc):
        with pytest.raises(ValueError, match="business_duplicate"):
            approval_svc._generate_final_doc_id(
                preliminary_doc_id="doc-contract-v2",
                logical_document_id="contract",
                version=2,
                version_decision=VersionDecision.BUSINESS_DUPLICATE,
            )

    def test_manual_approve_with_version_conflict_new_version(self, approval_svc, session):
        pending = approval_svc.create_pending(
            intake_job_id="ij-1",
            preliminary_doc_id="doc-contract-v2",
            collection_id="col-1",
        )
        approved = approval_svc.approve(
            ticket_id=pending.ticket_id,
            actor_id="user_1",
            version_decision=VersionDecision.NEW_VERSION,
            supersedes_final_doc_id="doc-contract-v1",
        )
        assert approved.final_doc_id == "doc-contract-v2"
        assert approved.version_decision == VersionDecision.NEW_VERSION
        assert approved.supersedes_final_doc_id == "doc-contract-v1"
