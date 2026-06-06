"""Agent review generation for intake runtime.

The formal reviewer architecture is:
  - one main review per document
  - one conditional findings-extraction pass per document

This keeps document-level judgment separate from anchored evidence extraction.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx
from reality_rag_contracts import (
    AgentReview,
    AnchoredFinding,
    PIIItem,
    PublishStatus,
    QualityReport,
    ReviewDecision,
)


@dataclass(frozen=True)
class DeepSeekReviewConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0
    provider: str = "deepseek"
    model_version: str = "unknown"
    prompt_version: str = "v2"
    policy_version: str = "v2"
    findings_confidence_threshold: float = 0.85
    findings_required_tags: tuple[str, ...] = ()
    artifact_schema_version: str = "v2"


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
    """Metadata for a single LLM review call."""

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
                    "prompt_excerpt": f"single-document main review with conditional findings extraction for {doc_id}",
                    "canonical_excerpt": excerpt,
                },
            )

        llm_records: list[LLMCallRecord] = []
        try:
            main_prompt = _build_main_review_prompt(
                doc_id=doc_id,
                canonical_content=canonical_content,
                quality_report=quality_report,
            )
            main_result, main_record = self._run_prompt("main_review", main_prompt, doc_id)
            llm_records.append(main_record)
            review = _build_review_from_main_result(doc_id, main_result)

            if _should_extract_findings(review, self._config):
                findings_prompt = _build_findings_extraction_prompt(
                    doc_id=doc_id,
                    canonical_content=canonical_content,
                    quality_report=quality_report,
                    main_review=review,
                )
                findings_result, findings_record = self._run_prompt(
                    "findings_extraction",
                    findings_prompt,
                    doc_id,
                )
                llm_records.append(findings_record)
                review = review.model_copy(
                    update={
                        "anchored_findings": _dedupe_findings(
                            _parse_anchored_findings(findings_result.get("anchored_findings"))
                        )
                    }
                )
        except AgentReviewError as exc:
            if event_hook is not None:
                event_hook(
                    event_type="review.failed",
                    phase="review",
                    level="error",
                    message=f"Agent review failed for {doc_id}: {exc}",
                    doc_id=doc_id,
                    payload={"error": str(exc), "model": self._config.model},
                )
            raise

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

        review._llm_call_records = llm_records  # type: ignore[attr-defined]
        return review

    def _run_prompt(self, name: str, prompt: str, doc_id: str) -> tuple[dict[str, Any], LLMCallRecord]:
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
                record.error_code = "review_unavailable" if attempt == 0 else "review_failed"
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
                    f"Review step {name} for {doc_id} returned invalid JSON: {last_payload[:500]!r}"
                )
        raise AgentReviewResponseError(f"Review step {name} for {doc_id} exhausted retries")


def build_deepseek_review_config_from_env() -> DeepSeekReviewConfig:
    required_tags_raw = os.environ.get("REVIEW_FINDINGS_REQUIRED_TAGS", "")
    required_tags = tuple(tag.strip() for tag in required_tags_raw.split(",") if tag.strip())
    return DeepSeekReviewConfig(
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        timeout_seconds=float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "60")),
        provider=os.environ.get("LLM_PROVIDER", "deepseek"),
        model_version=os.environ.get("LLM_MODEL_VERSION", "unknown"),
        prompt_version=os.environ.get("REVIEW_PROMPT_VERSION", "v2"),
        policy_version=os.environ.get("REVIEW_POLICY_VERSION", "v2"),
        findings_confidence_threshold=float(os.environ.get("REVIEW_FINDINGS_THRESHOLD", "0.85")),
        findings_required_tags=required_tags,
        artifact_schema_version=os.environ.get("REVIEW_ARTIFACT_SCHEMA_VERSION", "v2"),
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


def _build_main_review_prompt(
    *,
    doc_id: str,
    canonical_content: str,
    quality_report: QualityReport,
) -> str:
    excerpt = canonical_content[:8000]
    quality_json = quality_report.model_dump_json()
    return (
        "You are a single-pass enterprise document reviewer for a governed RAG system.\n"
        "Analyze the document and return JSON only with keys:\n"
        "document_type, suggested_authority_level, detected_pii, diff_summary, "
        "decision, confidence, reasons, risk_tags, suggested_actions, "
        "publish_recommendation, sections_requiring_review.\n"
        "Allowed decision values: approve, reject, quarantine, request_changes.\n"
        "Allowed publish_recommendation values: draft, pending_review, published, "
        "rejected, quarantined, archived.\n"
        "detected_pii must be a list of objects with keys: pii_type, description, severity.\n"
        "Confidence must be between 0 and 1.\n"
        "Do not emit anchored findings in this step.\n\n"
        f"doc_id: {doc_id}\n"
        f"quality_report: {quality_json}\n\n"
        "canonical_excerpt:\n"
        f"{excerpt}\n"
    )


def _build_findings_extraction_prompt(
    *,
    doc_id: str,
    canonical_content: str,
    quality_report: QualityReport,
    main_review: AgentReview,
) -> str:
    excerpt = canonical_content[:8000]
    quality_json = quality_report.model_dump_json()
    main_review_json = json.dumps(main_review.model_dump(mode="json"), ensure_ascii=False)
    return (
        "You are extracting anchored findings for a previously reviewed enterprise document.\n"
        "Return JSON only with key anchored_findings, whose value is a list of objects.\n"
        "Each finding object must contain: source_quote, problem_summary, severity, confidence.\n"
        "Rules:\n"
        "1. Output all major issues for the document in one response.\n"
        "2. Order findings by severity.\n"
        "3. If multiple issues are substantively the same, keep only one finding.\n"
        "4. If multiple passages support the same issue, choose the most representative source_quote.\n"
        "5. If you cannot stably locate source evidence, do not invent a finding.\n"
        "6. If risk exists but no stable evidence can be extracted, anchored_findings may be an empty list.\n"
        "7. source_quote should contain the problematic text with roughly 50 characters of surrounding context when available.\n\n"
        f"doc_id: {doc_id}\n"
        f"quality_report: {quality_json}\n"
        f"main_review: {main_review_json}\n\n"
        "canonical_excerpt:\n"
        f"{excerpt}\n"
    )


def _parse_authority_level(value: Any) -> int:
    """Coerce suggested_authority_level to int, handling string values like 'low'."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        mapping = {"low": 2, "medium": 5, "high": 8, "critical": 10}
        if lowered in mapping:
            return mapping[lowered]
        try:
            return int(lowered)
        except ValueError:
            return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _build_review_from_main_result(doc_id: str, result: dict[str, Any]) -> AgentReview:
    detected_pii = _parse_detected_pii(result.get("detected_pii"))
    decision_str = str(result.get("decision", "request_changes") or "request_changes")
    confidence = _coerce_confidence(result.get("confidence"))
    reasons = _as_string_list(result.get("reasons"))
    risk_tags = _as_string_list(result.get("risk_tags"))

    has_critical_pii = any(item.severity in ("high", "critical") for item in detected_pii)
    if has_critical_pii and decision_str == "approve":
        decision_str = "quarantine"
        reasons.append("Auto-elevated to quarantine: critical PII detected by review.")
        risk_tags.append("critical_pii_detected")

    return AgentReview(
        doc_id=doc_id,
        decision=ReviewDecision(decision_str) if decision_str else None,
        confidence=confidence,
        reasons=reasons,
        risk_tags=risk_tags,
        suggested_actions=_as_string_list(result.get("suggested_actions")),
        publish_recommendation=(
            PublishStatus(str(result.get("publish_recommendation")))
            if result.get("publish_recommendation")
            else None
        ),
        sections_requiring_review=_as_string_list(result.get("sections_requiring_review")),
        document_type=str(result.get("document_type", "") or ""),
        suggested_authority_level=_parse_authority_level(result.get("suggested_authority_level")),
        detected_pii=detected_pii,
        diff_summary=str(result.get("diff_summary", "") or ""),
        anchored_findings=[],
    )


def _should_extract_findings(review: AgentReview, config: DeepSeekReviewConfig) -> bool:
    if review.decision is not None and review.decision != ReviewDecision.APPROVE:
        return True
    if review.publish_recommendation is not None and review.publish_recommendation != PublishStatus.PUBLISHED:
        return True
    if review.confidence < config.findings_confidence_threshold:
        return True
    if set(review.risk_tags).intersection(config.findings_required_tags):
        return True
    return False


def _parse_detected_pii(raw: Any) -> list[PIIItem]:
    if not isinstance(raw, list):
        return []
    parsed: list[PIIItem] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        parsed.append(
            PIIItem(
                pii_type=str(item.get("pii_type", "") or ""),
                description=str(item.get("description", "") or ""),
                severity=str(item.get("severity", "low") or "low"),
            )
        )
    return parsed


def _parse_anchored_findings(raw: Any) -> list[AnchoredFinding]:
    if not isinstance(raw, list):
        return []
    findings: list[AnchoredFinding] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        source_quote = str(item.get("source_quote", "") or "").strip()
        problem_summary = str(item.get("problem_summary", "") or "").strip()
        if not source_quote or not problem_summary:
            continue
        findings.append(
            AnchoredFinding(
                finding_id="",
                source_quote=source_quote,
                problem_summary=problem_summary,
                severity=str(item.get("severity", "medium") or "medium"),
                confidence=_coerce_confidence(item.get("confidence")),
            )
        )
    return findings


def _dedupe_findings(findings: list[AnchoredFinding]) -> list[AnchoredFinding]:
    deduped: dict[str, AnchoredFinding] = {}
    for finding in findings:
        key = _normalize_text(finding.problem_summary)
        if not key:
            continue
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = finding
            continue
        if len(finding.source_quote) > len(existing.source_quote):
            deduped[key] = finding
            continue
        if finding.confidence > existing.confidence:
            deduped[key] = finding
    return list(deduped.values())


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _as_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


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
        raise AgentReviewUnavailableError(f"LLM request failed at {url}: {exc}") from exc
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
