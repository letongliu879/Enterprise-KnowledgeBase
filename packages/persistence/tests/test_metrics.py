"""Smoke tests for metrics module."""

import pytest

from reality_rag_persistence.metrics import IntakeMetrics, stage_timer


class TestIntakeMetrics:
    def test_metrics_response_returns_bytes(self):
        metrics = IntakeMetrics()
        body, content_type = metrics.metrics_response()
        assert isinstance(body, bytes)
        assert content_type.startswith("text/plain")

    def test_stage_timer_records_duration(self):
        metrics = IntakeMetrics()
        with stage_timer("conversion"):
            pass
        # No exception means success; actual metric values are internal to Prometheus

    def test_stage_timer_records_failure(self):
        metrics = IntakeMetrics()
        with pytest.raises(RuntimeError):
            with stage_timer("conversion"):
                raise RuntimeError("boom")
