import httpx
import pytest

from reality_rag_contracts import PublishStatus, QualityReport

from intake_runtime.agent_reviewer import (
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

    monkeypatch.setattr("intake_runtime.agent_reviewer.httpx.Client", _FailingClient)
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
    """Fake _call_deepseek that returns predefined JSON per prompt keyword."""

    def __init__(self, responses):
        self._responses = responses
        self.call_count = 0

    def __call__(self, config, prompt):
        self.call_count += 1
        for keyword, response in self._responses:
            if keyword in prompt:
                return response, {"latency_ms": 0}
        return "{}", {"latency_ms": 0}


def test_reviewer_runs_main_review_and_conditional_findings(monkeypatch):
    """The formal reviewer runs one main review, then one findings extraction pass."""
    backend = _FakeDeepSeekBackend([
        ("single-pass enterprise document reviewer", '{"document_type": "policy", "suggested_authority_level": 5, "detected_pii": [{"pii_type": "email", "description": "user@example.com", "severity": "medium"}], "diff_summary": "Travel policy doc", "decision": "request_changes", "confidence": 0.95, "reasons": ["clean"], "risk_tags": [], "suggested_actions": [], "publish_recommendation": "pending_review", "sections_requiring_review": []}'),
        ("extracting anchored findings", '{"anchored_findings": [{"source_quote": "...travel reimbursement policy...", "problem_summary": "Policy wording needs review.", "severity": "medium", "confidence": 0.81}]}'),
    ])
    monkeypatch.setattr("intake_runtime.agent_reviewer._call_deepseek", backend)

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

    assert backend.call_count == 2

    assert review.doc_id == "doc-5-subtasks"
    assert review.decision.value == "request_changes"
    assert review.confidence == 0.95
    assert review.document_type == "policy"
    assert review.suggested_authority_level == 5
    assert len(review.detected_pii) == 1
    assert review.detected_pii[0].pii_type == "email"
    assert review.detected_pii[0].severity == "medium"
    assert review.diff_summary == "Travel policy doc"
    assert len(review.anchored_findings) == 1
    assert [event["event_type"] for event in events] == ["review.started", "review.completed"]


def test_reviewer_auto_elevates_critical_pii(monkeypatch):
    """Critical PII still auto-elevates an approve decision to quarantine."""
    backend = _FakeDeepSeekBackend([
        ("single-pass enterprise document reviewer", '{"document_type": "employee_record", "suggested_authority_level": 7, "detected_pii": [{"pii_type": "salary", "description": "salary 100k", "severity": "critical"}], "diff_summary": "", "decision": "approve", "confidence": 0.9, "reasons": ["looks ok"], "risk_tags": [], "suggested_actions": [], "publish_recommendation": "published", "sections_requiring_review": []}'),
    ])
    monkeypatch.setattr("intake_runtime.agent_reviewer._call_deepseek", backend)

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
