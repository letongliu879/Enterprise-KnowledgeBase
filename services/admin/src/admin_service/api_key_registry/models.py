"""API key registry DTOs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from reality_rag_contracts import ApiKeyRegistryEntryAdmin


class ApiKeyCreateRequest(BaseModel):
    api_key_id: str
    tenant_id: str
    display_name: str = ""
    knowledge_scopes: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    debug_permission: bool = False
    token_budget_limit: int = Field(default=4096, gt=0)
    expires_at: datetime | None = None


class ApiKeyUpdateRequest(BaseModel):
    display_name: str | None = None
    knowledge_scopes: list[str] | None = None
    roles: list[str] | None = None
    debug_permission: bool | None = None
    token_budget_limit: int | None = Field(default=None, gt=0)
    expires_at: datetime | None = None


class ApiKeyCreateResponse(BaseModel):
    entry: ApiKeyRegistryEntryAdmin
    plaintext_key: str


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyRegistryEntryAdmin]
    total: int


class ApiKeyRotateResponse(BaseModel):
    entry: ApiKeyRegistryEntryAdmin
    plaintext_key: str
