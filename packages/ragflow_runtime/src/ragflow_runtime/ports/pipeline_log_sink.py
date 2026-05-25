from __future__ import annotations

from typing import Protocol


class PipelineLogSinkPort(Protocol):
    def append(self, component_id: str, progress: float | int | None = None, message: str = "") -> None:
        """Persist or relay dataflow component logs."""

