"""Profile registry DTOs."""

from typing import Any

from pydantic import BaseModel, Field

from reality_rag_contracts import ParserProfile, RetrievalProfileAdmin


class ParserProfileCreateRequest(BaseModel):
    parser_profile_id: str
    name: str
    description: str = ""
    parser_id: str = "naive"
    parser_config: dict[str, Any] = Field(default_factory=dict)


class ParserProfileUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    parser_config: dict[str, Any] | None = None


class ParserProfileListResponse(BaseModel):
    items: list[ParserProfile]
    total: int


class RetrievalProfileCreateRequest(BaseModel):
    retrieval_profile_id: str
    name: str
    description: str = ""
    profile_config: dict[str, Any] = Field(default_factory=dict)


class RetrievalProfileUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    profile_config: dict[str, Any] | None = None


class RetrievalProfileListResponse(BaseModel):
    items: list[RetrievalProfileAdmin]
    total: int


class ProfileStateTransitionRequest(BaseModel):
    target_state: str
    reason: str = ""
