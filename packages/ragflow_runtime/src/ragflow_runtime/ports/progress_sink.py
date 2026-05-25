from __future__ import annotations

from typing import Protocol


class ProgressSinkPort(Protocol):
    def emit(self, progress: float | int | None = None, message: str = "") -> None:
        """Consume parser/chunker progress emitted by the runtime."""

