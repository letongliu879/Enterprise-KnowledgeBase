"""Document ops DTOs."""

from pydantic import BaseModel


class DocumentLifecycleRequest(BaseModel):
    command_id: str = ""
    trace_id: str = ""
    idempotency_key: str = ""
    actor: str = ""
    reason: str = ""


class DocumentReindexRequest(BaseModel):
    command_id: str = ""
    trace_id: str = ""
    idempotency_key: str = ""
    actor: str = ""
    reason: str = ""
    collection_id: str
    tenant_id: str
    parse_snapshot_id: str
    index_profile_id: str = "ragflow"


class DocumentLifecycleResponse(BaseModel):
    success: bool
    final_doc_id: str
    previous_state: str | None = None
    new_state: str | None = None
    job_id: str | None = None
