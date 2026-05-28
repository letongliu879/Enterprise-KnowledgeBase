from __future__ import annotations

from indexing_service.domain import IndexVersionActionReceipt
from indexing_service.repository import IndexingRepository


class RollbackService:
    def __init__(self, repository: IndexingRepository) -> None:
        self.repository = repository

    def rollback(self, index_version_id: str) -> IndexVersionActionReceipt:
        version = self.repository.rollback(index_version_id)
        return IndexVersionActionReceipt(
            index_version_id=index_version_id,
            action="rollback",
            reactivated_index_version_id=version.previous_active_index_version_id,
        )
