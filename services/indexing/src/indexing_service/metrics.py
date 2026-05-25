from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class InMemoryIndexingMetrics:
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    timings_ms: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))

    def incr(self, name: str, value: int = 1) -> None:
        self.counters[name] += int(value)

    def observe_ms(self, name: str, duration_ms: int) -> None:
        self.timings_ms[name].append(max(int(duration_ms), 0))

    def snapshot(self) -> dict[str, object]:
        return {
            "counters": dict(self.counters),
            "timings_ms": {
                name: {
                    "count": len(values),
                    "avg": int(sum(values) / len(values)) if values else 0,
                    "max": max(values) if values else 0,
                    "p95_approx": _p95(values),
                }
                for name, values in self.timings_ms.items()
            },
        }


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))
    return ordered[index]
