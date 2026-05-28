from __future__ import annotations

from indexing_service.domain import IndexVersionActionReceipt
from indexing_service.repository import IndexingRepository


class CleanupService:
    def __init__(self, repository: IndexingRepository) -> None:
        self.repository = repository

    def cleanup(self, index_version_id: str) -> IndexVersionActionReceipt:
        _, removed_chunk_count = self.repository.cleanup(index_version_id)
        return IndexVersionActionReceipt(
            index_version_id=index_version_id,
            action="cleanup",
            removed_chunk_count=removed_chunk_count,
        )
