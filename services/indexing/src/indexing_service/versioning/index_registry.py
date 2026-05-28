from __future__ import annotations

from indexing_service.repository import IndexingRepository


class IndexRegistry:
    def __init__(self, repository: IndexingRepository) -> None:
        self.repository = repository

    def get(self, index_version_id: str):
        return self.repository.get_index_version(index_version_id)
