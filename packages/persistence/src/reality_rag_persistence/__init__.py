"""Reality-RAG Persistence — shared storage layer.

Provides SQLAlchemy models, session factory, and repositories.
All services access PostgreSQL through this package.
No service may define its own ORM models or duplicate repo logic.
"""

from .ingestion_monitor import IngestionMonitorStore, TERMINAL_RUN_STATUSES
from .outbox import EventPublisher, OutboxDispatcher

__all__ = [
    "IngestionMonitorStore",
    "TERMINAL_RUN_STATUSES",
    "EventPublisher",
    "OutboxDispatcher",
]
