from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11
    from enum import Enum

    class StrEnum(str, Enum):
        pass
