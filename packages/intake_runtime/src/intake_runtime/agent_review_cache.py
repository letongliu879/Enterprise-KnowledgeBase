"""Agent review result cache for intake runtime."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Protocol

from reality_rag_contracts import AgentReview, QualityReport


CACHE_SCHEMA_VERSION = "v2"
CACHE_KEY_PREFIX = "reality-rag:agent-review"


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def build_cache_key(
    *,
    canonical_content: str,
    quality_report: QualityReport,
    collection_id: str,
    authority_level: int,
    model: str,
) -> str:
    content_hash = _sha256(canonical_content)
    quality_json = json.dumps(quality_report.model_dump(mode="json"), sort_keys=True)
    quality_hash = _sha256(quality_json)
    context_hash = _sha256(f"{collection_id}:{authority_level}")
    return (
        f"{CACHE_KEY_PREFIX}:{CACHE_SCHEMA_VERSION}:"
        f"{content_hash}:{quality_hash}:{context_hash}:{model}"
    )


def _ttl_for_review(review: AgentReview) -> int | None:
    raw = review.decision
    decision = raw.value if hasattr(raw, "value") else (raw or "")
    if decision == "approve":
        return 86400
    return None


class AgentReviewCache(Protocol):
    def get(self, key: str) -> AgentReview | None: ...

    def set(self, key: str, review: AgentReview, ttl_seconds: int | None = None) -> None: ...


@dataclass
class _InMemoryEntry:
    review: AgentReview
    expires_at: float | None


class InMemoryAgentReviewCache:
    def __init__(self) -> None:
        self._entries: dict[str, _InMemoryEntry] = {}

    def get(self, key: str) -> AgentReview | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and entry.expires_at < time.time():
            self._entries.pop(key, None)
            return None
        return entry.review

    def set(self, key: str, review: AgentReview, ttl_seconds: int | None = None) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds is not None else None
        self._entries[key] = _InMemoryEntry(review=review, expires_at=expires_at)


class RedisAgentReviewCache:
    def __init__(self, *, redis_url: str, key_prefix: str = CACHE_KEY_PREFIX) -> None:
        from redis import Redis

        self._client = Redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix

    def _full_key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    def get(self, key: str) -> AgentReview | None:
        try:
            payload = self._client.get(self._full_key(key))
        except Exception:
            return None
        if not payload:
            return None
        try:
            return AgentReview.model_validate_json(payload)
        except Exception:
            try:
                self._client.delete(self._full_key(key))
            except Exception:
                pass
            return None

    def set(self, key: str, review: AgentReview, ttl_seconds: int | None = None) -> None:
        try:
            full_key = self._full_key(key)
            payload = review.model_dump_json()
            if ttl_seconds is not None:
                self._client.setex(full_key, ttl_seconds, payload)
            else:
                self._client.set(full_key, payload)
        except Exception:
            pass


_DEFAULT_CACHE: AgentReviewCache | None = None


def get_agent_review_cache() -> AgentReviewCache:
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is not None:
        return _DEFAULT_CACHE

    cache_mode = os.environ.get("AGENT_REVIEW_CACHE_MODE", "memory").lower()
    app_env = os.environ.get("APP_ENV", "development").lower()

    if cache_mode == "redis":
        redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
        _DEFAULT_CACHE = RedisAgentReviewCache(redis_url=redis_url)
        return _DEFAULT_CACHE

    if app_env == "production" and cache_mode != "memory":
        raise RuntimeError(
            "AGENT_REVIEW_CACHE_MODE must be 'redis' or 'memory' in production mode"
        )

    _DEFAULT_CACHE = InMemoryAgentReviewCache()
    return _DEFAULT_CACHE


def clear_agent_review_cache() -> None:
    global _DEFAULT_CACHE
    _DEFAULT_CACHE = None

