"""Tests for shared enums."""

import pytest

from reality_rag_contracts.enums import (
    AdminRole,
    BudgetPolicy,
    DocumentSupportTier,
    HumanReviewStatus,
    IndexRegistryStatus,
    IndexStatus,
    JobStatus,
    OutputMode,
    PublishStatus,
    ReviewDecision,
)


class TestPublishStatus:
    def test_all_values_exist(self):
        assert PublishStatus.DRAFT == "draft"
        assert PublishStatus.PENDING_REVIEW == "pending_review"
        assert PublishStatus.PUBLISHED == "published"
        assert PublishStatus.REJECTED == "rejected"
        assert PublishStatus.QUARANTINED == "quarantined"
        assert PublishStatus.ARCHIVED == "archived"

    def test_is_retrievable(self):
        """Only published is retrievable."""
        RETRIEVABLE = {PublishStatus.PUBLISHED}
        for s in PublishStatus:
            if s in RETRIEVABLE:
                assert s == PublishStatus.PUBLISHED
            else:
                assert s != PublishStatus.PUBLISHED


class TestIndexStatus:
    def test_all_values_exist(self):
        assert IndexStatus.NOT_INDEXED == "not_indexed"
        assert IndexStatus.INDEXING == "indexing"
        assert IndexStatus.INDEXED == "indexed"
        assert IndexStatus.FAILED == "failed"
        assert IndexStatus.STALE == "stale"

    def test_is_retrievable(self):
        """Only indexed is retrievable."""
        RETRIEVABLE = {IndexStatus.INDEXED}
        for s in IndexStatus:
            if s in RETRIEVABLE:
                assert s == IndexStatus.INDEXED
            else:
                assert s != IndexStatus.INDEXED


class TestJobStatus:
    def test_all_values_exist(self):
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.PARTIAL == "partial"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"

    def test_terminal_states(self):
        TERMINAL = {JobStatus.COMPLETED, JobStatus.PARTIAL, JobStatus.FAILED, JobStatus.CANCELLED}
        assert JobStatus.PENDING not in TERMINAL
        assert JobStatus.RUNNING not in TERMINAL


class TestOutputMode:
    def test_all_values(self):
        assert OutputMode.EVIDENCE_ONLY == "evidence_only"
        assert OutputMode.WITH_METADATA == "with_metadata"
        assert OutputMode.PROMPT_TEXT == "prompt_text"


class TestBudgetPolicy:
    def test_all_values(self):
        assert BudgetPolicy.FOCUSED == "focused"
        assert BudgetPolicy.BALANCED == "balanced"
        assert BudgetPolicy.COMPREHENSIVE == "comprehensive"
        assert BudgetPolicy.CITATION_ONLY == "citation_only"


class TestDocumentSupportTier:
    def test_tier_values(self):
        assert DocumentSupportTier.A == "A"
        assert DocumentSupportTier.B == "B"
        assert DocumentSupportTier.C == "C"
        assert DocumentSupportTier.D == "D"


class TestReviewDecision:
    def test_all_values(self):
        assert ReviewDecision.APPROVE == "approve"
        assert ReviewDecision.REJECT == "reject"
        assert ReviewDecision.QUARANTINE == "quarantine"
        assert ReviewDecision.REQUEST_CHANGES == "request_changes"


class TestHumanReviewStatus:
    def test_all_values_exist(self):
        assert HumanReviewStatus.PENDING == "pending"
        assert HumanReviewStatus.APPROVED == "approved"
        assert HumanReviewStatus.DEFERRED == "deferred"


class TestIndexRegistryStatus:
    def test_all_values_exist(self):
        assert IndexRegistryStatus.INDEXING == "indexing"
        assert IndexRegistryStatus.INDEXED == "indexed"


class TestAdminRole:
    def test_all_values(self):
        assert AdminRole.PLATFORM_ADMIN == "platform_admin"
        assert AdminRole.KNOWLEDGE_ADMIN == "knowledge_admin"
        assert AdminRole.REVIEWER == "reviewer"
        assert AdminRole.DEVELOPER_OPERATOR == "developer_operator"
        assert AdminRole.AUDITOR == "auditor"
