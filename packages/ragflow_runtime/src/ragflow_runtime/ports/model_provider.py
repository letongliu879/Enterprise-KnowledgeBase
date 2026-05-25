from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelRequest:
    tenant_id: str | None
    model_type: str
    model_name: str | None = None
    language: str | None = None


class ModelProviderPort(Protocol):
    def get_model(self, request: ModelRequest) -> object | None:
        """Return a runtime model object or None when the backend is unavailable."""

