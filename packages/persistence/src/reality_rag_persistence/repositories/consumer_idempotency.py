"""Consumer idempotency repository — guards against duplicate event delivery."""

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import ConsumerIdempotency

from ..models import ConsumerIdempotencyModel


class ConsumerIdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_processed(
        self,
        consumer_id: str,
        event_id: str,
        idempotency_key: str | None = None,
    ) -> ConsumerIdempotency:
        now = datetime.now(timezone.utc)
        row = ConsumerIdempotencyModel(
            record_id=_generate_record_id(),
            consumer_id=consumer_id,
            event_id=event_id,
            idempotency_key=idempotency_key,
            processed_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def is_processed(self, consumer_id: str, event_id: str) -> bool:
        """Return True if this consumer has already processed the event."""
        row = (
            self._session.query(ConsumerIdempotencyModel)
            .filter(ConsumerIdempotencyModel.consumer_id == consumer_id)
            .filter(ConsumerIdempotencyModel.event_id == event_id)
            .first()
        )
        return row is not None

    def is_processed_by_key(
        self, consumer_id: str, idempotency_key: str
    ) -> bool:
        """Return True if this consumer has already processed this idempotency key."""
        if not idempotency_key:
            return False
        row = (
            self._session.query(ConsumerIdempotencyModel)
            .filter(ConsumerIdempotencyModel.consumer_id == consumer_id)
            .filter(ConsumerIdempotencyModel.idempotency_key == idempotency_key)
            .first()
        )
        return row is not None

    @staticmethod
    def _to_contract(row: ConsumerIdempotencyModel) -> ConsumerIdempotency:
        return ConsumerIdempotency(
            consumer_id=row.consumer_id,
            event_id=row.event_id,
            idempotency_key=row.idempotency_key,
            processed_at=row.processed_at,
        )


def _generate_record_id() -> str:
    return "cidm_" + secrets.token_hex(12)
