from __future__ import annotations

from datetime import datetime, timezone

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11
    from enum import Enum

    class StrEnum(str, Enum):
        pass


UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)
