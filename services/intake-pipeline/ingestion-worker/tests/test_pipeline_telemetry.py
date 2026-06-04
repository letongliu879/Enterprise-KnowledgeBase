"""Tests for Phase 9 telemetry wiring into the ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from reality_rag_contracts import (
    AgentReview,
    LLMCallLog,
    PublishStatus,
    ReviewQualityFeedback,
)
from reality_rag_persistence.telemetry import TelemetryStore

from ingestion_worker.pipeline import IngestionPipeline
from intake_runtime.stages.protocol import StageContext


class FakeTelemetryStore(TelemetryStore):
    """In-memory telemetry store for testing."""

    def __init__(self):
        super().__init__(session_factory=None)
        self.llm_calls: list[LLMCallLog] = []
        self.feedbacks: list[ReviewQualityFeedback] = []
        self.events: list = []

    def log_llm_call(self, log, *, session=None):
        self.llm_calls.append(log)

    def record_review_feedback(self, feedback, *, session=None):
        self.feedbacks.append(feedback)

    def emit_event(self, event, *, session=None):
        self.events.append(event)


class TestPipelineTelemetry:
    def _make_pipeline(self, store):
        mock_reviewer = MagicMock()
        mock_cache = MagicMock()
        return IngestionPipeline(
            converters=[],
            agent_reviewer=mock_reviewer,
            agent_review_cache=mock_cache,
            telemetry_store=store,
        )

    def test_persists_llm_call_logs_after_review_stage(self, tmp_path):
        store = FakeTelemetryStore()
        pipeline = self._make_pipeline(store)

        ctx = StageContext(
            collection_id="col-1",
            source_file_path=str(tmp_path / "doc.md"),
            job_id="job-001",
            intake_job_id="intake-001",
            content_hash="sha256:abc",
            source_hash="sha256:abc",
        )
        ctx.agent_review = AgentReview(doc_id="doc-001", risk_tags=["pii"])
        ctx.review_context = {
            "llm_call_records": [
                {
                    "subtask_name": "pii_detection",
                    "provider": "deepseek",
                    "model_name": "deepseek-chat",
                    "model_version": "v3",
                    "prompt_version": "pii-v2",
                    "policy_version": "policy-v1",
                    "request_hash": "sha256:req1",
                    "response_hash": "sha256:resp1",
                    "input_token_count": 100,
                    "output_token_count": 50,
                    "total_token_count": 150,
                    "latency_ms": 1200,
                    "status": "succeeded",
                }
            ]
        }

        pipeline._persist_review_telemetry(ctx, review_task=None)

        assert len(store.llm_calls) == 1
        log = store.llm_calls[0]
        assert log.provider == "deepseek"
        assert log.model_name == "deepseek-chat"
        assert log.request_hash == "sha256:req1"
        assert log.input_token_count == 100
        assert log.intake_job_id == "intake-001"
        assert log.trace_id == "job-001"

    def test_persists_review_quality_feedback_after_approval(self, tmp_path):
        store = FakeTelemetryStore()
        pipeline = self._make_pipeline(store)

        ctx = StageContext(
            collection_id="col-1",
            source_file_path=str(tmp_path / "doc.md"),
            job_id="job-002",
            intake_job_id="intake-002",
            content_hash="sha256:abc",
            source_hash="sha256:abc",
            ticket_id="ticket-001",
            publish_status=PublishStatus.PUBLISHED,
        )
        ctx.agent_review = AgentReview(doc_id="doc-002", risk_tags=["pii"])

        pipeline._persist_review_feedback(ctx)

        assert len(store.feedbacks) == 1
        fb = store.feedbacks[0]
        assert fb.intake_job_id == "intake-002"
        assert fb.ticket_id == "ticket-001"
        assert fb.approval_decision == "approve"
        assert fb.auto_approved is True

    def test_telemetry_is_noop_when_store_is_none(self, tmp_path):
        pipeline = self._make_pipeline(None)

        ctx = StageContext(
            collection_id="col-1",
            source_file_path=str(tmp_path / "doc.md"),
            job_id="job-003",
            intake_job_id="intake-003",
        )
        ctx.agent_review = AgentReview(doc_id="doc-003")
        ctx.review_context = {
            "llm_call_records": [{"provider": "deepseek", "model_name": "test"}]
        }

        # Should not raise
        pipeline._persist_review_telemetry(ctx, review_task=None)
        pipeline._persist_review_feedback(ctx)

    def test_telemetry_skips_when_no_agent_review(self, tmp_path):
        store = FakeTelemetryStore()
        pipeline = self._make_pipeline(store)

        ctx = StageContext(
            collection_id="col-1",
            source_file_path=str(tmp_path / "doc.md"),
            job_id="job-004",
        )
        # No agent_review set

        pipeline._persist_review_feedback(ctx)
        assert len(store.feedbacks) == 0

    def test_telemetry_skips_when_no_llm_records(self, tmp_path):
        store = FakeTelemetryStore()
        pipeline = self._make_pipeline(store)

        ctx = StageContext(
            collection_id="col-1",
            source_file_path=str(tmp_path / "doc.md"),
            job_id="job-005",
        )
        ctx.agent_review = AgentReview(doc_id="doc-005")
        ctx.review_context = {}  # No llm_call_records

        pipeline._persist_review_telemetry(ctx, review_task=None)
        assert len(store.llm_calls) == 0
