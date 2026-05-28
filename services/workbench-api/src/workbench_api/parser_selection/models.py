"""Pydantic DTOs for parser profile selection."""

from pydantic import BaseModel


class ParserProfileItem(BaseModel):
    parser_profile_id: str
    name: str
    parser_id: str
    state: str
    is_default: bool


class ParserProfileListResponse(BaseModel):
    items: list[ParserProfileItem]
    default_parser_profile_id: str
