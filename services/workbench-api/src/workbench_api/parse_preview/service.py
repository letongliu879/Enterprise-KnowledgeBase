"""Parse preview service."""

import hashlib
import uuid

from ..deps import CurrentUser
from ..downstream_clients import IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable
from .models import ParsePreviewCreateRequest, ParsePreviewResponse


class ParsePreviewService:
    def __init__(self, indexing_client: IndexingClient):
        self._indexing_client = indexing_client

    async def create_preview(self, req: ParsePreviewCreateRequest, user: CurrentUser) -> ParsePreviewResponse:
        if not user.can_access_collection(req.collection_id):
            raise ValueError("Collection access denied")

        # Idempotency key: upload_id + parser_profile_id + hash(override)
        override_str = str(req.parser_override_json) if req.parser_override_json else ""
        idempotency_key = f"{req.upload_id}:{req.parser_profile_id}:{hashlib.sha256(override_str.encode()).hexdigest()[:16]}"
        trace_id = f"trc_{uuid.uuid4().hex[:16]}"

        command = {
            "command_id": f"cmd_{uuid.uuid4().hex[:16]}",
            "trace_id": trace_id,
            "idempotency_key": idempotency_key,
            "actor": req.actor,
            "tenant_id": req.tenant_id,
            "collection_id": req.collection_id,
            "target_type": "parse_preview",
            "target_id": req.upload_id,
            "payload": {
                "upload_id": req.upload_id,
                "source_file_id": req.source_file_id,
                "parser_profile_id": req.parser_profile_id,
                "parser_override_json": req.parser_override_json,
            },
        }

        try:
            result = await self._indexing_client.create_parse_preview(command)
            return ParsePreviewResponse(
                request_id=result.get("request_id", idempotency_key),
                trace_id=trace_id,
                status="accepted",
                parse_snapshot_id=result.get("parse_snapshot_id"),
            )
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Parse preview API not yet implemented in indexing service")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Indexing service unavailable")
            raise
