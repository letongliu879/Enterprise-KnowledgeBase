"""Event adapter registry."""

from .base import EventAdapter
from .intake_adapter import IntakeEventAdapter
from .approval_adapter import ApprovalEventAdapter
from .indexing_adapter import IndexingEventAdapter

ADAPTERS: dict[str, type[EventAdapter]] = {
    "intake": IntakeEventAdapter,
    "approval": ApprovalEventAdapter,
    "indexing": IndexingEventAdapter,
}


def get_adapter(service: str) -> EventAdapter:
    adapter_cls = ADAPTERS.get(service)
    if adapter_cls is None:
        raise ValueError(f"Unknown event service: {service}")
    return adapter_cls()
