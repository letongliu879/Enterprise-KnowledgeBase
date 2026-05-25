import httpx
import pytest

from reality_rag_contracts import PublishStatus, QualityReport

from ingestion_worker.agent_reviewer import (
    AgentReviewConfigurationError,
    AgentReviewUnavailableError,
    DeepSeekAgentReviewer,
    DeepSeekReviewConfig,
    get_agent_reviewer,
)


def test_get_agent_reviewer_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(AgentReviewConfigurationError) as exc:
        get_agent_reviewer()

    message = str(exc.value).lower()
    assert "not configured" in message
    assert "deepseek_api_key" in message
    assert "cannot bypass" in message


def test_reviewer_surfaces_connection_failure(monkeypatch):
    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):
            raise httpx.ConnectError("connect failed", request=httpx.Request("POST", url))

    monkeypatch.setattr("ingestion_worker.agent_reviewer.httpx.Client", _FailingClient)
    reviewer = DeepSeekAgentReviewer(
        DeepSeekReviewConfig(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_seconds=1,
        )
    )
    events = []

    with pytest.raises(AgentReviewUnavailableError) as exc:
        reviewer.review(
            doc_id="doc-connect-fail",
            canonical_content="hello world",
            quality_report=QualityReport(
                doc_id="doc-connect-fail",
                support_tier="A",
                conversion_score=1.0,
                table_extraction_quality=1.0,
                source_canonical_length_mismatch=0.0,
                recommended_review_status=PublishStatus.PUBLISHED,
                blocking_reasons=[],
            ),
            event_hook=lambda **event: events.append(event),
        )

    message = str(exc.value).lower()
    assert "llm connection failed" in message
    assert "unable to connect" in message
    assert [event["event_type"] for event in events] == ["review.started", "review.failed"]


class _FakeDeepSeekBackend:
    """Fake _call_deepseek that returns predefined JSON per subtask keyword."""

    def __init__(self, responses):
        self._responses = responses
        self.call_count = 0

    def __call__(self, config, prompt):
        self.call_count += 1
        for keyword, response in self._responses:
            if keyword in prompt:
                return response, {"latency_ms": 0}
        return "{}", {"latency_ms": 0}


def test_reviewer_runs_5_parallel_subtasks(monkeypatch):
    """R1-001: review() should dispatch 5 parallel subtasks and aggregate results."""
    backend = _FakeDeepSeekBackend([
        ("document classifier", '{"document_type": "policy", "subtype": "travel", "rationale": "travel rules"}'),
        ("governance analyst", '{"suggested_authority_level": 5, "rationale": "confidential"}'),
        ("personally identifiable information", '{"has_pii": true, "detected_pii": [{"pii_type": "email", "description": "user@example.com", "severity": "medium"}]}'),
        ("quality analyst", '{"diff_summary": "Travel policy doc", "conversion_quality_assessment": "good"}'),
        ("governed RAG system", '{"decision": "approve", "confidence": 0.95, "reasons": ["clean"], "risk_tags": [], "suggested_actions": [], "publish_recommendation": "published", "sections_requiring_review": []}'),
    ])
    monkeypatch.setattr("ingestion_worker.agent_reviewer._call_deepseek", backend)

    reviewer = DeepSeekAgentReviewer(
        DeepSeekReviewConfig(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_seconds=1,
        )
    )
    events = []

    review = reviewer.review(
        doc_id="doc-5-subtasks",
        canonical_content="This is a travel reimbursement policy document.",
        quality_report=QualityReport(
            doc_id="doc-5-subtasks",
            support_tier="A",
            conversion_score=1.0,
            table_extraction_quality=1.0,
            source_canonical_length_mismatch=0.0,
            recommended_review_status=PublishStatus.PUBLISHED,
            blocking_reasons=[],
        ),
        event_hook=lambda **event: events.append(event),
    )

    # All 5 subtasks should have been dispatched
    assert backend.call_count == 5

    # Verify aggregated review fields
    assert review.doc_id == "doc-5-subtasks"
    assert review.decision.value == "approve"
    assert review.confidence == 0.95
    assert review.document_type == "policy"
    assert review.suggested_authority_level == 5
    assert len(review.detected_pii) == 1
    assert review.detected_pii[0].pii_type == "email"
    assert review.detected_pii[0].severity == "medium"
    assert review.diff_summary == "Travel policy doc"

    # Event sequence
    assert [event["event_type"] for event in events] == ["review.started", "review.completed"]


def test_reviewer_auto_elevates_critical_pii(monkeypatch):
    """R1-001: If critical PII is detected but decision subtask says approve,
    the aggregator should auto-elevate to quarantine."""
    backend = _FakeDeepSeekBackend([
        ("document classifier", '{"document_type": "employee_record", "subtype": "", "rationale": ""}'),
        ("governance analyst", '{"suggested_authority_level": 7, "rationale": ""}'),
        ("personally identifiable information", '{"has_pii": true, "detected_pii": [{"pii_type": "salary", "description": "salary 100k", "severity": "critical"}]}'),
        ("quality analyst", '{"diff_summary": "", "conversion_quality_assessment": ""}'),
        ("governed RAG system", '{"decision": "approve", "confidence": 0.9, "reasons": ["looks ok"], "risk_tags": [], "suggested_actions": [], "publish_recommendation": "published", "sections_requiring_review": []}'),
    ])
    monkeypatch.setattr("ingestion_worker.agent_reviewer._call_deepseek", backend)

    reviewer = DeepSeekAgentReviewer(
        DeepSeekReviewConfig(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_seconds=1,
        )
    )

    review = reviewer.review(
        doc_id="doc-pii-elevate",
        canonical_content="Employee salary data included.",
        quality_report=QualityReport(
            doc_id="doc-pii-elevate",
            support_tier="A",
            conversion_score=1.0,
            table_extraction_quality=1.0,
            source_canonical_length_mismatch=0.0,
            recommended_review_status=PublishStatus.PUBLISHED,
            blocking_reasons=[],
        ),
    )

    assert review.decision.value == "quarantine"
    assert "critical_pii_detected" in review.risk_tags
    assert any("Auto-elevated" in r for r in review.reasons)
