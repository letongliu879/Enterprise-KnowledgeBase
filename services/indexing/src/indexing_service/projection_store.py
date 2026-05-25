from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _target_path(env_name: str) -> Path | None:
    raw = os.getenv(env_name)
    if not raw:
        return None
    return Path(raw)


def write_jsonl(env_name: str, records: list[dict[str, Any]]) -> None:
    path = _target_path(env_name)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(record, ensure_ascii=True) + "\n" for record in records)
    path.write_text(payload, encoding="utf-8")
