"""Outbox event repository — each owner schema has its own outbox."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from reality_rag_contracts import OutboxEvent, OutboxStatus

from ..models import OutboxEventModel


class OutboxEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        event_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload_json: dict[str, Any],
        payload_hash: str = "",
        idempotency_key: str | None = None,
        trace_id: str = "",
        schema_version: str = "2026-05-21.v1",
        next_attempt_at: datetime | None = None,
    ) -> OutboxEvent:
        now = datetime.now(timezone.utc)
        row = OutboxEventModel(
            event_id=event_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            schema_version=schema_version,
            payload_json=payload_json,
            payload_hash=payload_hash,
            idempotency_key=idempotency_key,
            trace_id=trace_id or event_id,
            status=OutboxStatus.PENDING.value,
            attempt_count=0,
            next_attempt_at=next_attempt_at or now,
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def get(self, event_id: str) -> OutboxEvent | None:
        row = self._session.get(OutboxEventModel, event_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_pending(
        self,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[OutboxEvent]:
        now = before or datetime.now(timezone.utc)
        # SQLite may return naive datetimes; compare without tzinfo to be safe
        compare_time = now.replace(tzinfo=None) if now.tzinfo else now
        rows = (
            self._session.query(OutboxEventModel)
            .filter(OutboxEventModel.status == OutboxStatus.PENDING.value)
            .filter(OutboxEventModel.next_attempt_at <= compare_time)
            .order_by(OutboxEventModel.next_attempt_at)
            .limit(limit)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def mark_sent(self, event_id: str) -> bool:
        row = self._session.get(OutboxEventModel, event_id)
        if row is None:
            return False
        row.status = OutboxStatus.SENT.value
        row.sent_at = datetime.now(timezone.utc)
        row.updated_at = row.sent_at
        self._session.flush()
        return True

    def mark_failed(
        self,
        event_id: str,
        next_attempt_at: datetime | None = None,
    ) -> bool:
        row = self._session.get(OutboxEventModel, event_id)
        if row is None:
            return False
        row.status = OutboxStatus.FAILED.value
        row.attempt_count += 1
        row.next_attempt_at = next_attempt_at or datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def reset_pending(self, event_id: str) -> bool:
        """Reset a failed event back to pending (e.g. for replay)."""
        row = self._session.get(OutboxEventModel, event_id)
        if row is None:
            return False
        row.status = OutboxStatus.PENDING.value
        row.next_attempt_at = datetime.now(timezone.utc)
        row.updated_at = row.next_attempt_at
        self._session.flush()
        return True

    @staticmethod
    def _to_contract(row: OutboxEventModel) -> OutboxEvent:
        return OutboxEvent(
            event_id=row.event_id,
            event_type=row.event_type,
            aggregate_type=row.aggregate_type,
            aggregate_id=row.aggregate_id,
            schema_version=row.schema_version,
            payload_json=row.payload_json,
            payload_hash=row.payload_hash,
            idempotency_key=row.idempotency_key,
            trace_id=row.trace_id,
            status=row.status,
            attempt_count=row.attempt_count,
            next_attempt_at=row.next_attempt_at,
            created_at=row.created_at,
            sent_at=row.sent_at,
        )
