"""Ops audit service."""

from datetime import datetime, timezone
import hashlib
import secrets

from reality_rag_contracts import OpsAuditLogEntry

from .repository import OpsAuditRepository


class OpsAuditService:
    def __init__(self, repo: OpsAuditRepository, actor_id: str = ""):
        self._repo = repo
        self._actor_id = actor_id

    def log_action(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        before_state: str | None = None,
        after_state: str | None = None,
        reason: str | None = None,
        tenant_id: str = "",
        collection_id: str | None = None,
        command_id: str = "",
        trace_id: str = "",
        idempotency_key: str = "",
        payload: dict | None = None,
    ) -> OpsAuditLogEntry:
        payload_hash = ""
        if payload:
            payload_str = str(sorted(payload.items()))
            payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        entry = OpsAuditLogEntry(
            audit_id=secrets.token_urlsafe(32),
            command_id=command_id or secrets.token_urlsafe(16),
            trace_id=trace_id or secrets.token_urlsafe(16),
            idempotency_key=idempotency_key or f"{target_type}:{target_id}:{action}",
            actor_id=self._actor_id,
            tenant_id=tenant_id,
            collection_id=collection_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_state=before_state,
            after_state=after_state,
            reason=reason,
            payload_hash=payload_hash,
            created_at=datetime.now(timezone.utc),
        )
        self._repo.save(entry)
        return entry

    def query(
        self,
        *,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        tenant_id: str | None = None,
        collection_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[OpsAuditLogEntry], int]:
        items = self._repo.list_all(
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            tenant_id=tenant_id,
            collection_id=collection_id,
            limit=limit,
            offset=offset,
        )
        total = self._repo.count(
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            tenant_id=tenant_id,
            collection_id=collection_id,
        )
        return items, total
