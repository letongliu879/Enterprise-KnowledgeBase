"""Tests for unified state machines."""

import pytest

from reality_rag_contracts import (
    DocumentPublishStateMachine,
    IndexRegistryStateMachine,
    IndexStateMachine,
    InvalidTransitionError,
    PublishStatus,
    ReviewDecision,
    IndexStatus,
    IndexRegistryStatus,
    DocumentSupportTier,
)


class TestDocumentPublishStateMachine:
    def test_valid_transitions(self):
        sm = DocumentPublishStateMachine
        assert sm.transition(PublishStatus.DRAFT, "agent_approve") == PublishStatus.PUBLISHED
        assert sm.transition(PublishStatus.DRAFT, "agent_request_changes") == PublishStatus.PENDING_REVIEW
        assert sm.transition(PublishStatus.DRAFT, "agent_reject") == PublishStatus.REJECTED
        assert sm.transition(PublishStatus.DRAFT, "pii_detected") == PublishStatus.QUARANTINED
        assert sm.transition(PublishStatus.PENDING_REVIEW, "human_approve") == PublishStatus.PUBLISHED
        assert sm.transition(PublishStatus.PENDING_REVIEW, "human_reject") == PublishStatus.REJECTED
        assert sm.transition(PublishStatus.REJECTED, "resubmit") == PublishStatus.PENDING_REVIEW
        assert sm.transition(PublishStatus.QUARANTINED, "cleaned") == PublishStatus.PENDING_REVIEW
        assert sm.transition(PublishStatus.PUBLISHED, "archive") == PublishStatus.ARCHIVED
        assert sm.transition(PublishStatus.ARCHIVED, "restore") == PublishStatus.DRAFT

    def test_invalid_transition_raises(self):
        with pytest.raises(InvalidTransitionError):
            DocumentPublishStateMachine.transition(PublishStatus.REJECTED, "agent_approve")

    def test_is_valid(self):
        assert DocumentPublishStateMachine.is_valid(PublishStatus.DRAFT, "agent_approve")
        assert not DocumentPublishStateMachine.is_valid(PublishStatus.REJECTED, "agent_approve")

    def test_allowed_events(self):
        events = DocumentPublishStateMachine.allowed_events(PublishStatus.DRAFT)
        assert "agent_approve" in events
        assert "agent_reject" in events
        assert "human_approve" not in events

    def test_resolve_from_agent_review(self):
        sm = DocumentPublishStateMachine
        assert sm.resolve_from_agent_review(ReviewDecision.REJECT, None, None) == PublishStatus.REJECTED
        assert sm.resolve_from_agent_review(ReviewDecision.QUARANTINE, None, None) == PublishStatus.QUARANTINED
        assert sm.resolve_from_agent_review(ReviewDecision.REQUEST_CHANGES, None, None) == PublishStatus.PENDING_REVIEW
        assert sm.resolve_from_agent_review(None, PublishStatus.PUBLISHED, None) == PublishStatus.PUBLISHED
        assert sm.resolve_from_agent_review(None, None, PublishStatus.QUARANTINED) == PublishStatus.QUARANTINED
        assert sm.resolve_from_agent_review(None, None, None) == PublishStatus.PENDING_REVIEW

    def test_resolve_from_quality_tier(self):
        sm = DocumentPublishStateMachine
        assert sm.resolve_from_quality_tier("A", []) == PublishStatus.PUBLISHED
        assert sm.resolve_from_quality_tier("B", []) == PublishStatus.PUBLISHED
        assert sm.resolve_from_quality_tier("C", []) == PublishStatus.PENDING_REVIEW
        assert sm.resolve_from_quality_tier("D", []) == PublishStatus.QUARANTINED
        assert sm.resolve_from_quality_tier("A", ["bad"]) == PublishStatus.PENDING_REVIEW
        assert sm.resolve_from_quality_tier("B", ["bad", "worse"]) == PublishStatus.QUARANTINED


class TestIndexStateMachine:
    def test_valid_transitions(self):
        sm = IndexStateMachine
        assert sm.transition(IndexStatus.NOT_INDEXED, "start") == IndexStatus.INDEXING
        assert sm.transition(IndexStatus.INDEXING, "complete") == IndexStatus.INDEXED
        assert sm.transition(IndexStatus.INDEXING, "fail") == IndexStatus.FAILED
        assert sm.transition(IndexStatus.INDEXED, "stale") == IndexStatus.STALE
        assert sm.transition(IndexStatus.STALE, "reindex") == IndexStatus.INDEXING
        assert sm.transition(IndexStatus.FAILED, "retry") == IndexStatus.INDEXING
        assert sm.transition(IndexStatus.INDEXED, "unpublish") == IndexStatus.NOT_INDEXED

    def test_invalid_transition_raises(self):
        with pytest.raises(InvalidTransitionError):
            IndexStateMachine.transition(IndexStatus.NOT_INDEXED, "complete")

    def test_derive_from_publish_status(self):
        assert IndexStateMachine.derive_from_publish_status(PublishStatus.PUBLISHED) == IndexStatus.INDEXING
        assert IndexStateMachine.derive_from_publish_status(PublishStatus.DRAFT) == IndexStatus.NOT_INDEXED
        assert IndexStateMachine.derive_from_publish_status(PublishStatus.PENDING_REVIEW) == IndexStatus.NOT_INDEXED


class TestIndexRegistryStateMachine:
    def test_valid_transitions(self):
        sm = IndexRegistryStateMachine
        assert sm.transition(IndexRegistryStatus.INDEXING, "activate") == IndexRegistryStatus.INDEXED
        assert sm.transition(IndexRegistryStatus.INDEXED, "rollback") == IndexRegistryStatus.INDEXED
        assert sm.transition(IndexRegistryStatus.INDEXED, "reindex_start") == IndexRegistryStatus.INDEXING

    def test_invalid_transition_raises(self):
        with pytest.raises(InvalidTransitionError):
            IndexRegistryStateMachine.transition(IndexRegistryStatus.INDEXING, "rollback")
