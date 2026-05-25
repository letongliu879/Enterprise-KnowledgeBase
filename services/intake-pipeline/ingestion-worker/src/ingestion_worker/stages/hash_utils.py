"""Deterministic hash utilities for stage input/output schemas.

Follows intake-pipeline.md idempotency rules:
  idempotency_key = "{intake_job_id}:{stage_name}:{schema_version}:{input_hash}"

input_hash  : SHA-256 of canonical JSON of stage input (excluding schema_version)
result_hash : SHA-256 of canonical JSON of stage output
              (excluding input_hash and result_hash themselves)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any


def _json_default(obj: Any) -> Any:
    """Serialize objects that json.dumps doesn't know about."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    # Pydantic models
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json(value: Any) -> str:
    """Return a canonical JSON string with sorted keys and no whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)


def sha256_hash(text: str) -> str:
    """SHA-256 hex digest of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_input_hash(input_data: Any) -> str:
    """Compute input_hash for a stage input object.

    Uses the canonical JSON representation.
    """
    return sha256_hash(canonical_json(input_data))


def compute_result_hash(result_data: Any) -> str:
    """Compute result_hash for a stage output object.

    Strips input_hash and result_hash fields so that
    re-execution with the same business result produces
    the same hash even if the wrapper hashes differ.
    """
    d = asdict(result_data) if is_dataclass(result_data) else dict(result_data)
    # Remove hash fields to avoid circular dependency
    d.pop("input_hash", None)
    d.pop("result_hash", None)
    return sha256_hash(canonical_json(d))
