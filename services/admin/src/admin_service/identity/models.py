"""Identity DTOs for admin auth."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    roles: list[str]
    allowed_tenants: list[str]
    allowed_collections: list[str]
