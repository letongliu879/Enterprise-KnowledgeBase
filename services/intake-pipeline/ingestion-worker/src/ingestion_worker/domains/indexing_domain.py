"""Indexing domain compatibility shim.

Re-export through ingestion_worker.indexing_service so remote-only deployments
do not require the local reality_rag_indexing package at import time.
"""

from __future__ import annotations

from ..indexing_service import (
    IndexBuildInput,
    IndexBuildOutput,
    IndexJobError,
    IndexingService,
    PerDocumentIndexResult,
)

__all__ = [
    "IndexBuildInput",
    "IndexBuildOutput",
    "IndexJobError",
    "IndexingService",
    "PerDocumentIndexResult",
]
