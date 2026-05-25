"""Unified state machines for Reality-RAG V2.

All state transitions MUST go through these state machines.
No service may perform ad-hoc status assignment without validation.
"""

from __future__ import annotations

from typing import ClassVar

from .enums import IndexRegistryStatus, IndexStatus, PublishStatus, ReviewDecision


class InvalidTransitionError(ValueError):
    """Raised when a state transition is not allowed."""


class DocumentPublishStateMachine:
    """Unified document publish status state machine.

    Transition table (from_status + event -> to_status):
    - DRAFT + agent_approve        -> PUBLISHED
    - DRAFT + agent_request_changes-> PENDING_REVIEW
    - DRAFT + agent_reject         -> REJECTED
    - DRAFT + pii_detected         -> QUARANTINED
    - PENDING_REVIEW + human_approve -> PUBLISHED
    - PENDING_REVIEW + human_reject  -> REJECTED
    - PENDING_REVIEW + human_defer   -> PENDING_REVIEW (no-op, audit only)
    - PENDING_REVIEW + pii_detected  -> QUARANTINED
    - REJECTED + resubmit          -> PENDING_REVIEW
    - QUARANTINED + cleaned        -> PENDING_REVIEW
    - PUBLISHED + archive          -> ARCHIVED
    - ARCHIVED + restore           -> DRAFT
    """

    TRANSITIONS: ClassVar[dict[tuple[PublishStatus, str], PublishStatus]] = {
        (PublishStatus.DRAFT, "agent_approve"): PublishStatus.PUBLISHED,
        (PublishStatus.DRAFT, "agent_request_changes"): PublishStatus.PENDING_REVIEW,
        (PublishStatus.DRAFT, "agent_reject"): PublishStatus.REJECTED,
        (PublishStatus.DRAFT, "pii_detected"): PublishStatus.QUARANTINED,
        (PublishStatus.PENDING_REVIEW, "human_approve"): PublishStatus.PUBLISHED,
        (PublishStatus.PENDING_REVIEW, "human_reject"): PublishStatus.REJECTED,
        (PublishStatus.PENDING_REVIEW, "human_defer"): PublishStatus.PENDING_REVIEW,
        (PublishStatus.PENDING_REVIEW, "pii_detected"): PublishStatus.QUARANTINED,
        (PublishStatus.REJECTED, "resubmit"): PublishStatus.PENDING_REVIEW,
        (PublishStatus.QUARANTINED, "cleaned"): PublishStatus.PENDING_REVIEW,
        (PublishStatus.PUBLISHED, "archive"): PublishStatus.ARCHIVED,
        (PublishStatus.ARCHIVED, "restore"): PublishStatus.DRAFT,
    }

    @classmethod
    def transition(cls, from_status: PublishStatus, event: str) -> PublishStatus:
        """Validate and return the next status.

        Raises:
            InvalidTransitionError: If the transition is not allowed.
        """
        key = (from_status, event)
        if key not in cls.TRANSITIONS:
            raise InvalidTransitionError(
                f"Cannot transition from {from_status.value!r} via event {event!r}. "
                f"Allowed events from {from_status.value!r}: "
                f"{[e for s, e in cls.TRANSITIONS if s == from_status]}"
            )
        return cls.TRANSITIONS[key]

    @classmethod
    def is_valid(cls, from_status: PublishStatus, event: str) -> bool:
        """Check if a transition is valid without raising."""
        return (from_status, event) in cls.TRANSITIONS

    @classmethod
    def allowed_events(cls, from_status: PublishStatus) -> list[str]:
        """Return all allowed events from a given status."""
        return [event for status, event in cls.TRANSITIONS if status == from_status]

    @classmethod
    def resolve_from_agent_review(
        cls,
        decision: ReviewDecision | None,
        recommendation: PublishStatus | None,
        quality_recommendation: PublishStatus | None,
    ) -> PublishStatus:
        """Resolve publish status from agent review decision and recommendation.

        This is the canonical implementation of the decision logic previously
        scattered in DecisionStage and quality_stage.
        """
        if decision == ReviewDecision.REJECT:
            return PublishStatus.REJECTED
        if decision == ReviewDecision.QUARANTINE:
            return PublishStatus.QUARANTINED
        if decision == ReviewDecision.REQUEST_CHANGES:
            return PublishStatus.PENDING_REVIEW
        if recommendation is not None:
            return recommendation
        return quality_recommendation if quality_recommendation is not None else PublishStatus.PENDING_REVIEW

    @classmethod
    def resolve_from_quality_tier(
        cls,
        support_tier: str,
        blocking_reasons: list[str],
    ) -> PublishStatus:
        """Resolve recommended publish status from quality assessment.

        Args:
            support_tier: DocumentSupportTier value (A/B/C/D).
            blocking_reasons: List of blocking quality issues.
        """
        if support_tier in ("A", "B") and not blocking_reasons:
            return PublishStatus.PUBLISHED
        if support_tier == "D" or len(blocking_reasons) >= 2:
            return PublishStatus.QUARANTINED
        return PublishStatus.PENDING_REVIEW


class IndexStateMachine:
    """Document-level index status state machine.

    Transition table:
    - NOT_INDEXED + start -> INDEXING
    - INDEXING + complete   -> INDEXED
    - INDEXING + fail       -> FAILED
    - INDEXED + stale       -> STALE
    - STALE + reindex       -> INDEXING
    - FAILED + retry        -> INDEXING
    - ANY + unpublish       -> NOT_INDEXED
    """

    TRANSITIONS: ClassVar[dict[tuple[IndexStatus, str], IndexStatus]] = {
        (IndexStatus.NOT_INDEXED, "start"): IndexStatus.INDEXING,
        (IndexStatus.INDEXING, "complete"): IndexStatus.INDEXED,
        (IndexStatus.INDEXING, "fail"): IndexStatus.FAILED,
        (IndexStatus.INDEXED, "stale"): IndexStatus.STALE,
        (IndexStatus.STALE, "reindex"): IndexStatus.INDEXING,
        (IndexStatus.FAILED, "retry"): IndexStatus.INDEXING,
        (IndexStatus.NOT_INDEXED, "unpublish"): IndexStatus.NOT_INDEXED,
        (IndexStatus.INDEXING, "unpublish"): IndexStatus.NOT_INDEXED,
        (IndexStatus.INDEXED, "unpublish"): IndexStatus.NOT_INDEXED,
        (IndexStatus.FAILED, "unpublish"): IndexStatus.NOT_INDEXED,
        (IndexStatus.STALE, "unpublish"): IndexStatus.NOT_INDEXED,
    }

    @classmethod
    def transition(cls, from_status: IndexStatus, event: str) -> IndexStatus:
        """Validate and return the next index status.

        Raises:
            InvalidTransitionError: If the transition is not allowed.
        """
        key = (from_status, event)
        if key not in cls.TRANSITIONS:
            raise InvalidTransitionError(
                f"Cannot transition from {from_status.value!r} via event {event!r}. "
                f"Allowed events from {from_status.value!r}: "
                f"{[e for s, e in cls.TRANSITIONS if s == from_status]}"
            )
        return cls.TRANSITIONS[key]

    @classmethod
    def is_valid(cls, from_status: IndexStatus, event: str) -> bool:
        """Check if a transition is valid without raising."""
        return (from_status, event) in cls.TRANSITIONS

    @classmethod
    def allowed_events(cls, from_status: IndexStatus) -> list[str]:
        """Return all allowed events from a given status."""
        return [event for status, event in cls.TRANSITIONS if status == from_status]

    @classmethod
    def derive_from_publish_status(cls, publish_status: PublishStatus) -> IndexStatus:
        """Derive the expected index status from publish status.

        - PUBLISHED -> INDEXING (ready for indexing)
        - Other     -> NOT_INDEXED
        """
        return IndexStatus.INDEXING if publish_status == PublishStatus.PUBLISHED else IndexStatus.NOT_INDEXED


class IndexRegistryStateMachine:
    """Index registry (collection-level) state machine.

    Transition table:
    - INDEXING + activate -> INDEXED
    - INDEXED + rollback  -> INDEXED (version switch)
    """

    TRANSITIONS: ClassVar[dict[tuple[IndexRegistryStatus, str], IndexRegistryStatus]] = {
        (IndexRegistryStatus.INDEXING, "activate"): IndexRegistryStatus.INDEXED,
        (IndexRegistryStatus.INDEXED, "rollback"): IndexRegistryStatus.INDEXED,
        (IndexRegistryStatus.INDEXED, "reindex_start"): IndexRegistryStatus.INDEXING,
    }

    @classmethod
    def transition(cls, from_status: IndexRegistryStatus, event: str) -> IndexRegistryStatus:
        key = (from_status, event)
        if key not in cls.TRANSITIONS:
            raise InvalidTransitionError(
                f"Cannot transition from {from_status.value!r} via event {event!r}. "
                f"Allowed events from {from_status.value!r}: "
                f"{[e for s, e in cls.TRANSITIONS if s == from_status]}"
            )
        return cls.TRANSITIONS[key]

    @classmethod
    def is_valid(cls, from_status: IndexRegistryStatus, event: str) -> bool:
        return (from_status, event) in cls.TRANSITIONS

    @classmethod
    def allowed_events(cls, from_status: IndexRegistryStatus) -> list[str]:
        return [event for status, event in cls.TRANSITIONS if status == from_status]
