from __future__ import annotations

from ragflow_runtime.ports.progress_sink import ProgressSinkPort


class NoOpProgressSink(ProgressSinkPort):
    def emit(self, progress: float | int | None = None, message: str = "") -> None:
        return None

