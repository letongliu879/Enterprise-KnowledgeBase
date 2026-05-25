from __future__ import annotations

from indexing_service.repository import InMemoryIndexingRepository


class IndexRegistry:
    def __init__(self, repository: InMemoryIndexingRepository) -> None:
        self.repository = repository

    def get(self, index_version_id: str):
        return self.repository.get_index_version(index_version_id)
