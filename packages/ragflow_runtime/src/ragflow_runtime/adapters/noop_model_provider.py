from __future__ import annotations

from ragflow_runtime.ports.model_provider import ModelProviderPort, ModelRequest


class NoOpModelProvider(ModelProviderPort):
    def get_model(self, request: ModelRequest) -> object | None:
        return None

