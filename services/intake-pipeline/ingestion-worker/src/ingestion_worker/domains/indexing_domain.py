"""Indexing domain — re-exported from reality-rag-indexing shared package.

In phase 8 the core logic moved to packages/indexing so it can be shared
between ingestion-worker (same-process fallback) and indexing-service
(remote process).  This module remains as a thin compatibility shim.
"""

from __future__ import annotations

from reality_rag_indexing import (
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
