"""Pydantic DTOs for task projection."""

from pydantic import BaseModel
from typing import Any


class TaskListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
