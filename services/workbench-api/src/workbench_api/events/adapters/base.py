"""Event adapter base classes."""

from abc import ABC, abstractmethod
from typing import Any

from ..models import ProjectionEvent


class EventAdapter(ABC):
    """Base class for downstream service event adapters.

    Each downstream service (intake, approval, indexing) implements its own
    adapter to convert native domain events into workbench projection events.
    """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the service identifier (e.g., 'intake', 'approval')."""

    @abstractmethod
    def adapt(self, native_event: dict[str, Any]) -> list[ProjectionEvent]:
        """Convert a single native event into zero or more projection events.

        A native event may generate multiple projection events when it
        affects multiple aggregates (e.g., an intake job update may
        update both task and document projections).
        """

    def adapt_batch(self, native_events: list[dict[str, Any]]) -> list[ProjectionEvent]:
        """Convert a batch of native events."""
        results: list[ProjectionEvent] = []
        for event in native_events:
            results.extend(self.adapt(event))
        return results
