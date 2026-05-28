"""Collection catalog DTOs."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from reality_rag_contracts import AdminCollection, CollectionProfileBinding
from reality_rag_contracts.enums import CollectionLifecycleState


class CollectionCreateRequest(BaseModel):
    collection_id: str
    tenant_id: str
    name: str
    description: str = ""
    authority_level: int = Field(default=0, ge=0, le=10)
    access_policy: dict[str, Any] = Field(default_factory=dict)
    default_parser_profile_id: str = ""
    default_retrieval_profile_id: str = ""
    default_approval_policy_id: str = ""


class CollectionUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    authority_level: int | None = Field(default=None, ge=0, le=10)
    access_policy: dict[str, Any] | None = None
    default_parser_profile_id: str | None = None
    default_retrieval_profile_id: str | None = None
    default_approval_policy_id: str | None = None


class CollectionListResponse(BaseModel):
    items: list[AdminCollection]
    total: int


class CollectionLifecycleTransitionRequest(BaseModel):
    target_state: CollectionLifecycleState
    reason: str = ""


class ProfileBindingCreateRequest(BaseModel):
    parser_profile_id: str = ""
    retrieval_profile_id: str = ""
    approval_policy_id: str = ""


class ProfileBindingResponse(BaseModel):
    binding: CollectionProfileBinding
    previous_binding_id: str | None = None
