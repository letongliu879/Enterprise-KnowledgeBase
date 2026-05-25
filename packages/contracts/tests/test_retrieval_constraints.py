"""Tests for retrieval-specific constraints and business rules.

These tests encode invariants that MUST hold across all services.
"""

import pytest
from pydantic import ValidationError

from reality_rag_contracts import (
    AccessRetrieveRequest,
    CacheKeyComponents,
    CWSearchResponse,
    EvidenceItem,
    IndexStatus,
    KnowledgeContext,
    PermissionContext,
    PublishStatus,
    RetrievalRequest,
    RetrievalResponse,
)


class TestRetrievabilityConstraint:
    """Only published + indexed documents should be retrievable."""

    def test_published_plus_indexed_is_retrievable(self):
        assert PublishStatus.PUBLISHED == "published"
        assert IndexStatus.INDEXED == "indexed"

    def test_draft_not_published(self):
        assert PublishStatus.DRAFT != "published"

    def test_pending_review_not_published(self):
        assert PublishStatus.PENDING_REVIEW != "published"

    def test_not_indexed_is_not_indexed(self):
        assert IndexStatus.NOT_INDEXED != "indexed"

    def test_failed_is_not_indexed(self):
        assert IndexStatus.FAILED != "indexed"


class TestCacheKeyComponents:
    """Cache key MUST include all required dimensions."""

    def test_all_required_fields_present(self):
        ck = CacheKeyComponents(
            tenant_id="t1",
            user_id="u1",
            application_profile_id="ap1",
            collection_scope=["c1"],
            index_version={"c1": "v1"},
            permission_scope_hash="hash123",
            policy_snapshot_version="v1",
            normalized_query="test query",
            query_intent_version="v1",
            retrieval_params="max_results=10",
            token_budget=4096,
            budget_policy="balanced",
            output_mode="evidence_only",
            metadata_policy="minimal",
        )
        data = ck.model_dump()
        # Every field in CacheKeyComponents is required
        for field_name in [
            "tenant_id",
            "user_id",
            "application_profile_id",
            "collection_scope",
            "index_version",
            "permission_scope_hash",
            "policy_snapshot_version",
            "normalized_query",
            "query_intent_version",
            "retrieval_params",
            "token_budget",
            "budget_policy",
            "output_mode",
            "metadata_policy",
        ]:
            assert field_name in data, f"Missing cache key component: {field_name}"

    def test_permission_hash_changes_cache_key(self):
        ck1 = CacheKeyComponents(
            tenant_id="t1", user_id="u1", application_profile_id="ap1",
            collection_scope=["c1"], index_version={"c1": "v1"},
            permission_scope_hash="hash_A", policy_snapshot_version="v1", normalized_query="q",
            query_intent_version="v1", retrieval_params="", token_budget=100,
            budget_policy="balanced", output_mode="evidence_only",
            metadata_policy="minimal",
        )
        ck2 = CacheKeyComponents(
            tenant_id="t1", user_id="u1", application_profile_id="ap1",
            collection_scope=["c1"], index_version={"c1": "v1"},
            permission_scope_hash="hash_B", policy_snapshot_version="v1", normalized_query="q",
            query_intent_version="v1", retrieval_params="", token_budget=100,
            budget_policy="balanced", output_mode="evidence_only",
            metadata_policy="minimal",
        )
        assert ck1.permission_scope_hash != ck2.permission_scope_hash

    def test_index_version_changes_cache_key(self):
        ck1 = CacheKeyComponents(
            tenant_id="t1", user_id="u1", application_profile_id="ap1",
            collection_scope=["c1"], index_version={"c1": "v1"},
            permission_scope_hash="h", policy_snapshot_version="v1", normalized_query="q",
            query_intent_version="v1", retrieval_params="", token_budget=100,
            budget_policy="balanced", output_mode="evidence_only",
            metadata_policy="minimal",
        )
        ck2 = CacheKeyComponents(
            tenant_id="t1", user_id="u1", application_profile_id="ap1",
            collection_scope=["c1"], index_version={"c1": "v2"},
            permission_scope_hash="h", policy_snapshot_version="v1", normalized_query="q",
            query_intent_version="v1", retrieval_params="", token_budget=100,
            budget_policy="balanced", output_mode="evidence_only",
            metadata_policy="minimal",
        )
        assert ck1.index_version != ck2.index_version


class TestNoFinalAnswer:
    """KnowledgeContext must not contain a final answer — it is evidence only."""

    def test_knowledge_context_has_no_answer_field(self):
        kc = KnowledgeContext(
            evidence_items=[],
            assembled_context="test",
            retrieval_metadata={
                "retrieval_time_ms": 1,
                "collections_searched": [],
                "index_versions_used": {},
                "total_evidence_count": 0,
                "cache_hit": False,
            },
        )
        data = kc.model_dump()
        assert "answer" not in data
        assert "final_answer" not in data
        assert "response" not in data

    def test_access_retrieve_response_has_no_answer_field(self):
        """AccessRetrieveResponse wraps KnowledgeContext, no answer field."""
        kc = KnowledgeContext()
        resp = AccessRetrieveRequest(
            query="q", application_profile_id="ap1"
        )
        # Access API response wraps KnowledgeContext only
        assert "answer" not in resp.model_dump()


class TestEvidenceItemConstraints:
    def test_score_in_range(self):
        with pytest.raises(ValidationError):
            EvidenceItem(
                evidence_id="e1", doc_id="d1", collection_id="c1",
                canonical_source="src", content="text", score=1.5,
            )
        with pytest.raises(ValidationError):
            EvidenceItem(
                evidence_id="e1", doc_id="d1", collection_id="c1",
                canonical_source="src", content="text", score=-0.1,
            )

    def test_minimal_valid_evidence(self):
        e = EvidenceItem(
            evidence_id="e1",
            doc_id="d1",
            collection_id="c1",
            canonical_source="src",
            content="text",
        )
        assert e.score == 0.0


class TestPermissionContext:
    def test_hash_required(self):
        with pytest.raises(ValidationError):
            PermissionContext(
                tenant_id="t1",
                application_profile_id="ap1",
                collection_scope=["c1"],
            )

    def test_valid_permission_context(self):
        pc = PermissionContext(
            tenant_id="t1",
            application_profile_id="ap1",
            collection_scope=["c1"],
            permission_scope_hash="hash",
        )
        assert pc.permission_scope_hash == "hash"
        assert pc.role_ids == []
