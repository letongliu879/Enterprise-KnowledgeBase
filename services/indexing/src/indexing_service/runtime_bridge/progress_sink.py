from __future__ import annotations

from dataclasses import dataclass, field

from ragflow_runtime.ports.progress_sink import ProgressSinkPort


@dataclass
class IndexingProgressCollector(ProgressSinkPort):
    events: list[dict[str, object]] = field(default_factory=list)

    def emit(self, progress: float | int | None = None, message: str = "") -> None:
        self.events.append({"progress": progress, "message": message})

