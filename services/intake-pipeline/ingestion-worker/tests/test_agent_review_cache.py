"""Tests for R1-002 Agent Review cache."""

from __future__ import annotations

from reality_rag_contracts import AgentReview, PublishStatus, QualityReport, ReviewDecision

from ingestion_worker.agent_review_cache import (
    CACHE_KEY_PREFIX,
    CACHE_SCHEMA_VERSION,
    InMemoryAgentReviewCache,
    _ttl_for_review,
    build_cache_key,
    clear_agent_review_cache,
    get_agent_review_cache,
)


def test_build_cache_key_is_deterministic():
    """Same inputs must produce the same key."""
    qr = QualityReport(
        doc_id="doc-1",
        support_tier="A",
        conversion_score=1.0,
        table_extraction_quality=1.0,
        source_canonical_length_mismatch=0.0,
        recommended_review_status=PublishStatus.PUBLISHED,
        blocking_reasons=[],
    )
    key1 = build_cache_key(
        canonical_content="hello world",
        quality_report=qr,
        collection_id="col-1",
        authority_level=5,
        model="deepseek-chat",
    )
    key2 = build_cache_key(
        canonical_content="hello world",
        quality_report=qr,
        collection_id="col-1",
        authority_level=5,
        model="deepseek-chat",
    )
    assert key1 == key2
    assert key1.startswith(f"{CACHE_KEY_PREFIX}:{CACHE_SCHEMA_VERSION}:")


def test_build_cache_key_changes_on_content():
    """Different canonical content must produce different keys."""
    qr = QualityReport(
        doc_id="doc-1",
        support_tier="A",
        conversion_score=1.0,
        table_extraction_quality=1.0,
        source_canonical_length_mismatch=0.0,
        recommended_review_status=PublishStatus.PUBLISHED,
        blocking_reasons=[],
    )
    key1 = build_cache_key(
        canonical_content="hello world",
        quality_report=qr,
        collection_id="col-1",
        authority_level=5,
        model="deepseek-chat",
    )
    key2 = build_cache_key(
        canonical_content="hello world 2",
        quality_report=qr,
        collection_id="col-1",
        authority_level=5,
        model="deepseek-chat",
    )
    assert key1 != key2


def test_build_cache_key_changes_on_collection_context():
    """Different collection or authority_level must produce different keys."""
    qr = QualityReport(
        doc_id="doc-1",
        support_tier="A",
        conversion_score=1.0,
        table_extraction_quality=1.0,
        source_canonical_length_mismatch=0.0,
        recommended_review_status=PublishStatus.PUBLISHED,
        blocking_reasons=[],
    )
    key1 = build_cache_key(
        canonical_content="hello world",
        quality_report=qr,
        collection_id="col-1",
        authority_level=5,
        model="deepseek-chat",
    )
    key2 = build_cache_key(
        canonical_content="hello world",
        quality_report=qr,
        collection_id="col-2",
        authority_level=5,
        model="deepseek-chat",
    )
    key3 = build_cache_key(
        canonical_content="hello world",
        quality_report=qr,
        collection_id="col-1",
        authority_level=3,
        model="deepseek-chat",
    )
    assert key1 != key2
    assert key1 != key3


def test_ttl_for_approve_is_24h():
    review = AgentReview(
        doc_id="d",
        decision=ReviewDecision("approve"),
        confidence=0.9,
        reasons=["ok"],
        risk_tags=[],
        suggested_actions=[],
        publish_recommendation=PublishStatus.PUBLISHED,
        sections_requiring_review=[],
        document_type="policy",
        suggested_authority_level=3,
        detected_pii=[],
        diff_summary="",
    )
    assert _ttl_for_review(review) == 86400


def test_ttl_for_reject_is_permanent():
    review = AgentReview(
        doc_id="d",
        decision=ReviewDecision("reject"),
        confidence=0.9,
        reasons=["bad"],
        risk_tags=[],
        suggested_actions=[],
        publish_recommendation=PublishStatus.REJECTED,
        sections_requiring_review=[],
        document_type="policy",
        suggested_authority_level=3,
        detected_pii=[],
        diff_summary="",
    )
    assert _ttl_for_review(review) is None


def test_ttl_for_quarantine_is_permanent():
    review = AgentReview(
        doc_id="d",
        decision=ReviewDecision("quarantine"),
        confidence=0.9,
        reasons=["pii"],
        risk_tags=[],
        suggested_actions=[],
        publish_recommendation=PublishStatus.QUARANTINED,
        sections_requiring_review=[],
        document_type="policy",
        suggested_authority_level=3,
        detected_pii=[],
        diff_summary="",
    )
    assert _ttl_for_review(review) is None


def test_in_memory_cache_hit_and_miss():
    cache = InMemoryAgentReviewCache()
    review = AgentReview(
        doc_id="",
        decision=ReviewDecision("approve"),
        confidence=0.9,
        reasons=["ok"],
        risk_tags=[],
        suggested_actions=[],
        publish_recommendation=PublishStatus.PUBLISHED,
        sections_requiring_review=[],
        document_type="policy",
        suggested_authority_level=3,
        detected_pii=[],
        diff_summary="",
    )
    cache.set("key-1", review, ttl_seconds=86400)
    assert cache.get("key-1") is not None
    assert cache.get("key-1").decision.value == "approve"
    assert cache.get("key-missing") is None


def test_in_memory_cache_expires():
    cache = InMemoryAgentReviewCache()
    review = AgentReview(
        doc_id="",
        decision=ReviewDecision("approve"),
        confidence=0.9,
        reasons=["ok"],
        risk_tags=[],
        suggested_actions=[],
        publish_recommendation=PublishStatus.PUBLISHED,
        sections_requiring_review=[],
        document_type="policy",
        suggested_authority_level=3,
        detected_pii=[],
        diff_summary="",
    )
    cache.set("key-1", review, ttl_seconds=1)
    assert cache.get("key-1") is not None
    import time
    time.sleep(1.1)
    assert cache.get("key-1") is None


def test_in_memory_cache_permanent_entry():
    cache = InMemoryAgentReviewCache()
    review = AgentReview(
        doc_id="",
        decision=ReviewDecision("reject"),
        confidence=0.9,
        reasons=["bad"],
        risk_tags=[],
        suggested_actions=[],
        publish_recommendation=PublishStatus.REJECTED,
        sections_requiring_review=[],
        document_type="policy",
        suggested_authority_level=3,
        detected_pii=[],
        diff_summary="",
    )
    cache.set("key-1", review, ttl_seconds=None)
    assert cache.get("key-1") is not None
    assert cache.get("key-1").decision.value == "reject"


def test_get_agent_review_cache_returns_singleton():
    clear_agent_review_cache()
    c1 = get_agent_review_cache()
    c2 = get_agent_review_cache()
    assert c1 is c2
