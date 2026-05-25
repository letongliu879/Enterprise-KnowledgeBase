"""Outbox dispatcher and event publisher.

Re-exported from reality-rag-persistence shared package.
This module is kept for backward compatibility; new code should import
from reality_rag_persistence directly.
"""

from __future__ import annotations

from reality_rag_persistence import EventPublisher, OutboxDispatcher

__all__ = ["EventPublisher", "OutboxDispatcher"]
