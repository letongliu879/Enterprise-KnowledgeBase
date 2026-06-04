"""Deterministic hash utilities for stage input/output schemas."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)


def sha256_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_input_hash(input_data: Any) -> str:
    return sha256_hash(canonical_json(input_data))


def compute_result_hash(result_data: Any) -> str:
    data = asdict(result_data) if is_dataclass(result_data) else dict(result_data)
    data.pop("input_hash", None)
    data.pop("result_hash", None)
    return sha256_hash(canonical_json(data))

