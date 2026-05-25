"""Agent review generation for ingestion-worker.

R1-001: Single-round review is split into 5 parallel subtasks:
  1. document_type          – classify the document
  2. suggested_authority_level – suggest authority_level (0-10)
  3. detected_pii           – scan for PII / sensitive data
  4. diff_summary           – content summary & quality assessment
  5. decision               – final approve/reject/quarantine/request_changes

The public ``review()`` method remains synchronous for backward compatibility.
Internally it dispatches the 5 subtasks via ThreadPoolExecutor so they run in
parallel (I/O-bound HTTP calls to DeepSeek).

LLM call metadata (latency, hashes, token counts) is collected and returned
via ``review_context`` so callers can persist ``llm_call_log`` entries.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
from reality_rag_contracts import AgentReview, PIIItem, PublishStatus, QualityReport, ReviewDecision


@dataclass(frozen=True)
class DeepSeekReviewConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0
    max_workers: int = 5
    provider: str = "deepseek"
    model_version: str = "unknown"
    prompt_version: str = "v1"
    policy_version: str = "v1"


class AgentReviewError(RuntimeError):
    """Base error for non-bypassable agent review failures."""


class AgentReviewConfigurationError(AgentReviewError):
    """Raised when the LLM review backend is not configured."""


class AgentReviewUnavailableError(AgentReviewError):
    """Raised when the LLM review backend cannot be reached."""


class AgentReviewResponseError(AgentReviewError):
    """Raised when the LLM review backend returns an invalid payload."""


@dataclass
class LLMCallRecord:
    """Metadata for a single LLM subtask call."""

    subtask_name: str
    provider: str
    model_name: str
    model_version: str
    prompt_version: str
    policy_version: str
    request_hash: str
    response_hash: str = ""
    input_token_count: int | None = None
    output_token_count: int | None = None
    total_token_count: int | None = None
    latency_ms: int = 0
    timeout_ms: int = 60000
    status: str = "succeeded"
    error_code: str | None = None
    retry_count: int = 0
    json_parse_success: bool = False
    schema_validation_success: bool = False
    redaction_before_send: bool = False
    external_model_used: bool = True


class DeepSeekAgentReviewer:
    def __init__(self, config: DeepSeekReviewConfig) -> None:
        self._config = config

    def review(
        self,
        *,
        doc_id: str,
        canonical_content: str,
        quality_report: QualityReport,
        event_hook: Callable[..., None] | None = None,
    ) -> AgentReview:
        excerpt = canonical_content[:6000]
        if event_hook is not None:
            event_hook(
                event_type="review.started",
                phase="review",
                message=f"Submitting canonical markdown to the review LLM for {doc_id}",
                doc_id=doc_id,
                payload={
                    "model": self._config.model,
                    "prompt_excerpt": f"5 parallel subtasks for {doc_id}",
                    "canonical_excerpt": excerpt,
                },
            )

        prompts = _build_subtask_prompts(
            doc_id=doc_id,
            canonical_content=canonical_content,
            quality_report=quality_report,
        )

        results: dict[str, dict[str, Any]] = {}
        exceptions: list[AgentReviewError] = []
        llm_records: list[LLMCallRecord] = []

        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            futures = {
                executor.submit(
                    self._run_subtask, name, prompt, doc_id
                ): name
                for name, prompt in prompts.items()
            }
            for future in futures:
                name = futures[future]
                try:
                    result, record = future.result()
                    results[name] = result
                    llm_records.append(record)
                except AgentReviewError as exc:
                    exceptions.append(exc)

        if exceptions:
            first_exc = exceptions[0]
            if event_hook is not None:
                event_hook(
                    event_type="review.failed",
                    phase="review",
                    level="error",
                    message=f"Agent review failed for {doc_id}: {first_exc}",
                    doc_id=doc_id,
                    payload={"error": str(first_exc), "model": self._config.model},
                )
            # If all subtasks failed with the same unavailable error, propagate it directly
            # so callers can still catch AgentReviewUnavailableError for retry logic.
            if all(isinstance(e, AgentReviewUnavailableError) for e in exceptions):
                raise first_exc
            raise AgentReviewResponseError(
                f"Subtask failures for {doc_id}: {'; '.join(str(e) for e in exceptions)}"
            )

        review = _aggregate_subtask_results(doc_id, results)

        if event_hook is not None:
            event_hook(
                event_type="review.completed",
                phase="review",
                message=(
                    f"Review LLM returned {review.decision.value if review.decision else 'none'} "
                    f"with confidence={review.confidence:.2f}"
                ),
                doc_id=doc_id,
                payload=review.model_dump(mode="json"),
            )

        # Attach LLM call records so callers can persist llm_call_log
        review._llm_call_records = llm_records  # type: ignore[attr-defined]
        return review

    def _run_subtask(self, name: str, prompt: str, doc_id: str) -> tuple[dict[str, Any], LLMCallRecord]:
        last_payload = ""
        record = LLMCallRecord(
            subtask_name=name,
            provider=self._config.provider,
            model_name=self._config.model,
            model_version=self._config.model_version,
            prompt_version=self._config.prompt_version,
            policy_version=self._config.policy_version,
            request_hash=_sha256(prompt),
            timeout_ms=int(self._config.timeout_seconds * 1000),
            external_model_used=True,
        )
        for attempt in range(2):
            try:
                result, meta = _call_deepseek(self._config, prompt)
                record.response_hash = _sha256(result)
                record.latency_ms = meta.get("latency_ms", 0)
                record.input_token_count = meta.get("input_tokens")
                record.output_token_count = meta.get("output_tokens")
                record.total_token_count = meta.get("total_tokens")
                record.status = "succeeded"
                record.json_parse_success = True
                record.schema_validation_success = True
                last_payload = result
                parsed = _parse_review_payload(last_payload)
                return parsed, record
            except (AgentReviewUnavailableError, AgentReviewResponseError):
                record.status = "failed"
                record.error_code = "subtask_unavailable" if attempt == 0 else "subtask_failed"
                if attempt == 0:
                    continue
                raise
            except json.JSONDecodeError:
                record.status = "failed"
                record.error_code = "json_parse_error"
                record.json_parse_success = False
                if attempt == 0:
                    continue
                raise AgentReviewResponseError(
                    f"Subtask {name} for {doc_id} returned invalid JSON: {last_payload[:500]!r}"
                )
        # Should never reach here
        raise AgentReviewResponseError(
            f"Subtask {name} for {doc_id} exhausted retries"
        )


def build_deepseek_review_config_from_env() -> DeepSeekReviewConfig:
    return DeepSeekReviewConfig(
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        timeout_seconds=float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "60")),
        provider=os.environ.get("LLM_PROVIDER", "deepseek"),
        model_version=os.environ.get("LLM_MODEL_VERSION", "unknown"),
        prompt_version=os.environ.get("REVIEW_PROMPT_VERSION", "v1"),
        policy_version=os.environ.get("REVIEW_POLICY_VERSION", "v1"),
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_agent_reviewer():
    config = build_deepseek_review_config_from_env()
    if not config.api_key:
        raise AgentReviewConfigurationError(
            "Agent review is not configured: DEEPSEEK_API_KEY is required, and ingestion cannot bypass agent review."
        )
    return DeepSeekAgentReviewer(config)


# ── Subtask prompt builders ───────────────────────────────────────────


def _build_subtask_prompts(
    *,
    doc_id: str,
    canonical_content: str,
    quality_report: QualityReport,
) -> dict[str, str]:
    excerpt = canonical_content[:8000]
    quality_json = quality_report.model_dump_json()

    return {
        "document_type": (
            "You are a document classifier. Analyze the following enterprise document and classify it.\n"
            "Return JSON only with keys: document_type, subtype, rationale.\n"
            "Common document_type values: policy, technical_spec, meeting_minutes, "
            "financial_report, contract, employee_record, compliance_document, "
            "training_material, other.\n\n"
            f"doc_id: {doc_id}\n"
            "canonical_excerpt:\n"
            f"{excerpt}\n"
        ),
        "suggested_authority_level": (
            "You are a data governance analyst. Based on the document content, "
            "suggest an authority level (0-10) for access control.\n"
            "0 = public, 3 = internal, 5 = confidential, 7 = restricted, 10 = top secret.\n"
            "Return JSON only with keys: suggested_authority_level, rationale.\n\n"
            f"doc_id: {doc_id}\n"
            "canonical_excerpt:\n"
            f"{excerpt}\n"
        ),
        "detected_pii": (
            "You are a PII (personally identifiable information) detector. "
            "Scan the document for sensitive data.\n"
            "Return JSON only with keys: has_pii (boolean), detected_pii (list of objects).\n"
            "Each detected_pii item must have keys: pii_type, description, severity.\n"
            "Severity levels: low, medium, high, critical.\n"
            "Common pii_type values: name, id_card, phone, email, address, "
            "bank_account, salary, passport, medical_record, other.\n\n"
            f"doc_id: {doc_id}\n"
            "canonical_excerpt:\n"
            f"{excerpt}\n"
        ),
        "diff_summary": (
            "You are a document quality analyst. Summarize the key content and "
            "identify any quality issues in the converted document.\n"
            "Return JSON only with keys: diff_summary, conversion_quality_assessment.\n"
            "diff_summary: concise summary of the document's key points (max 200 words).\n"
            "conversion_quality_assessment: note any suspected truncation, garbled text, "
            "or missing tables based on the quality report.\n\n"
            f"doc_id: {doc_id}\n"
            f"quality_report: {quality_json}\n\n"
            "canonical_excerpt:\n"
            f"{excerpt}\n"
        ),
        "decision": (
            "You are reviewing a converted enterprise document for publication in a governed RAG system.\n"
            "Return JSON only with keys: decision, confidence, reasons, risk_tags, "
            "suggested_actions, publish_recommendation, sections_requiring_review.\n"
            "Allowed decision values: approve, reject, quarantine, request_changes.\n"
            "Allowed publish_recommendation values: draft, pending_review, published, "
            "rejected, quarantined, archived.\n"
            "Confidence must be between 0 and 1.\n\n"
            f"doc_id: {doc_id}\n"
            f"quality_report: {quality_json}\n\n"
            "canonical_excerpt:\n"
            f"{excerpt}\n"
        ),
    }


# ── Aggregation ───────────────────────────────────────────────────────


def _aggregate_subtask_results(doc_id: str, results: dict[str, dict[str, Any]]) -> AgentReview:
    decision_result = results.get("decision", {})
    pii_result = results.get("detected_pii", {})
    doc_type_result = results.get("document_type", {})
    authority_result = results.get("suggested_authority_level", {})
    diff_result = results.get("diff_summary", {})

    # Parse PII items
    detected_pii_raw = pii_result.get("detected_pii", []) if isinstance(pii_result.get("detected_pii"), list) else []
    detected_pii: list[PIIItem] = []
    for item in detected_pii_raw:
        if isinstance(item, dict):
            detected_pii.append(
                PIIItem(
                    pii_type=item.get("pii_type", ""),
                    description=item.get("description", ""),
                    severity=item.get("severity", "low"),
                )
            )

    # Base decision from the decision subtask
    decision_str = decision_result.get("decision", "request_changes")
    confidence = float(decision_result.get("confidence", 0.0))
    reasons = list(decision_result.get("reasons", []))
    risk_tags = list(decision_result.get("risk_tags", []))

    # Cross-subtask guard: if critical PII is detected but decision is approve,
    # auto-elevate to quarantine.
    has_critical_pii = any(
        item.get("severity") in ("high", "critical") for item in detected_pii_raw
    )
    if has_critical_pii and decision_str == "approve":
        decision_str = "quarantine"
        reasons.append("Auto-elevated to quarantine: critical PII detected by subtask")
        risk_tags.append("critical_pii_detected")

    return AgentReview(
        doc_id=doc_id,
        decision=ReviewDecision(decision_str) if decision_str else None,
        confidence=confidence,
        reasons=reasons,
        risk_tags=risk_tags,
        suggested_actions=list(decision_result.get("suggested_actions", [])),
        publish_recommendation=PublishStatus(decision_result.get("publish_recommendation", "pending_review"))
        if decision_result.get("publish_recommendation")
        else None,
        sections_requiring_review=list(decision_result.get("sections_requiring_review", [])),
        document_type=doc_type_result.get("document_type", ""),
        suggested_authority_level=int(authority_result.get("suggested_authority_level", 0)),
        detected_pii=detected_pii,
        diff_summary=diff_result.get("diff_summary", ""),
    )


# ── DeepSeek HTTP client ──────────────────────────────────────────────


def _call_deepseek(config: DeepSeekReviewConfig, prompt: str) -> tuple[str, dict[str, Any]]:
    base = config.base_url.rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": "You must return valid JSON only. No markdown fences.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=config.timeout_seconds, trust_env=False) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError as exc:
        raise AgentReviewUnavailableError(
            f"LLM connection failed: unable to connect to the DeepSeek endpoint at {url}."
        ) from exc
    except httpx.TimeoutException as exc:
        raise AgentReviewUnavailableError(
            f"LLM request timed out while connecting to the DeepSeek endpoint at {url}."
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        raise AgentReviewUnavailableError(
            f"LLM request failed: DeepSeek endpoint returned status {status_code} at {url}."
        ) from exc
    except httpx.HTTPError as exc:
        raise AgentReviewUnavailableError(
            f"LLM request failed at {url}: {exc}"
        ) from exc
    latency_ms = int((time.perf_counter() - start) * 1000)

    usage = data.get("usage", {}) if isinstance(data, dict) else {}
    meta: dict[str, Any] = {
        "latency_ms": latency_ms,
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
    try:
        return data["choices"][0]["message"]["content"], meta
    except (KeyError, IndexError, TypeError) as exc:
        raise AgentReviewResponseError(
            "Review LLM returned an invalid response payload."
        ) from exc


def _parse_review_payload(payload: str) -> dict:
    stripped = payload.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
