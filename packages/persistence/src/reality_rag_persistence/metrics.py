"""Prometheus metrics for Reality-RAG intake pipeline.

Metrics labels are controlled to avoid cardinality explosions.
High-cardinality IDs (intake_job_id, source_file_id, final_doc_id)
MUST NOT be used as labels.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


class _NoOpMetric:
    """No-op metric when prometheus_client is not installed."""

    def inc(self, amount: float = 1) -> None:
        pass

    def observe(self, amount: float) -> None:
        pass

    def set(self, amount: float) -> None:
        pass


class IntakeMetrics:
    """Centralised intake-pipeline metrics.

    All counters/histograms use low-cardinality labels only:
    component, stage_name, status, visibility, provider, model_name, prompt_version.

    Singleton — subsequent instantiations reuse the already-registered metrics
    so that tests and duplicate imports don't raise ``ValueError: Duplicated
    timeseries`` from the Prometheus default registry.
    """

    _initialized = False

    def __init__(self) -> None:
        if IntakeMetrics._initialized:
            return
        IntakeMetrics._initialized = True

        if not _PROMETHEUS_AVAILABLE:
            self._noop = _NoOpMetric()
            return

        self.intake_jobs_created_total = Counter(
            "intake_jobs_created_total",
            "Total intake jobs created",
            ["collection_id"],
        )
        self.intake_jobs_published_total = Counter(
            "intake_jobs_published_total",
            "Total intake jobs that reached PUBLISHED",
            ["collection_id", "visibility"],
        )
        self.intake_jobs_failed_total = Counter(
            "intake_jobs_failed_total",
            "Total intake jobs that reached FAILED",
            ["collection_id", "error_code"],
        )
        self.stage_duration_seconds = Histogram(
            "stage_duration_seconds",
            "Stage execution duration in seconds",
            ["stage_name", "status"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
        )
        self.stage_retry_total = Counter(
            "stage_retry_total",
            "Total stage retry attempts",
            ["stage_name"],
        )
        self.stage_failed_total = Counter(
            "stage_failed_total",
            "Total stage failures",
            ["stage_name", "error_code"],
        )
        self.outbox_pending_total = Gauge(
            "outbox_pending_total",
            "Number of pending outbox events",
            ["event_type"],
        )
        self.dead_letter_total = Gauge(
            "dead_letter_total",
            "Number of dead-lettered tasks",
            ["stage_name"],
        )
        self.approval_pending_total = Gauge(
            "approval_pending_total",
            "Number of pending approval tickets",
            ["collection_id"],
        )
        self.auto_approve_total = Counter(
            "auto_approve_total",
            "Total auto-approved documents",
            ["collection_id", "visibility"],
        )
        self.manual_decision_total = Counter(
            "manual_decision_total",
            "Total manual decisions",
            ["decision"],
        )
        self.manual_approve_total = Counter(
            "manual_approve_total",
            "Total manual approvals",
            ["collection_id"],
        )
        self.manual_reject_total = Counter(
            "manual_reject_total",
            "Total manual rejections",
            ["collection_id"],
        )
        self.manual_return_total = Counter(
            "manual_return_total",
            "Total manual returns",
            ["collection_id"],
        )
        self.publish_failure_total = Counter(
            "publish_failure_total",
            "Total publish failures",
            ["failure_type"],
        )
        self.llm_call_total = Counter(
            "llm_call_total",
            "Total LLM calls",
            ["provider", "model_name", "prompt_version", "status"],
        )
        self.llm_token_total = Counter(
            "llm_token_total",
            "Total LLM tokens consumed",
            ["provider", "model_name", "token_type"],
        )
        self.llm_error_total = Counter(
            "llm_error_total",
            "Total LLM call errors",
            ["provider", "model_name", "error_type"],
        )
        self.llm_schema_validation_failure_total = Counter(
            "llm_schema_validation_failure_total",
            "Total LLM response schema validation failures",
            ["provider", "model_name", "prompt_version"],
        )
        self.review_degraded_total = Counter(
            "review_degraded_total",
            "Total degraded reviews",
            ["collection_id", "visibility"],
        )
        self.manual_override_total = Counter(
            "manual_override_total",
            "Total manual overrides of auto-approve",
            ["collection_id"],
        )
        self.end_to_end_intake_duration_seconds = Histogram(
            "end_to_end_intake_duration_seconds",
            "End-to-end intake duration from CREATED to PUBLISHED",
            ["collection_id", "visibility"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0],
        )

    def __getattr__(self, name: str) -> _NoOpMetric:
        if not _PROMETHEUS_AVAILABLE:
            return self._noop
        raise AttributeError(name)

    def metrics_response(self) -> tuple[bytes, str]:
        """Return (body, content_type) for the /metrics endpoint."""
        if _PROMETHEUS_AVAILABLE:
            return generate_latest(), CONTENT_TYPE_LATEST
        return b"# prometheus_client not installed\n", "text/plain"


# Global singleton — services import this instance
intake_metrics = IntakeMetrics()


@contextmanager
def stage_timer(stage_name: str) -> Generator[None, None, None]:
    """Context manager that records stage_duration_seconds.

    Usage::

        with stage_timer("conversion"):
            run_conversion(...)
    """
    if not _PROMETHEUS_AVAILABLE:
        yield
        return

    start = time.perf_counter()
    try:
        yield
        status = "succeeded"
    except Exception:
        status = "failed"
        raise
    finally:
        elapsed = time.perf_counter() - start
        intake_metrics.stage_duration_seconds.labels(
            stage_name=stage_name, status=status
        ).observe(elapsed)
