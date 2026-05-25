from __future__ import annotations

from indexing_service.domain import IndexVersionActionReceipt
from indexing_service.repository import InMemoryIndexingRepository


class ActivationService:
    def __init__(self, repository: InMemoryIndexingRepository) -> None:
        self.repository = repository

    def activate(self, index_version_id: str) -> IndexVersionActionReceipt:
        activated = self.repository.activate(index_version_id)
        return IndexVersionActionReceipt(
            index_version_id=index_version_id,
            action="activate",
            deactivated_index_version_id=activated.previous_active_index_version_id,
        )
