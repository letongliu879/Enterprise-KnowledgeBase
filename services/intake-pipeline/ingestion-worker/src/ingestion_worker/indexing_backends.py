"""Indexing backends — re-exported from reality-rag-indexing shared package.

In phase 8 the core backend implementations moved to packages/indexing so
they can be shared between ingestion-worker (same-process fallback) and
indexing-service (remote process).  This module remains as a thin
compatibility shim.
"""

from __future__ import annotations

from reality_rag_indexing import (
    get_index_backend,
    IndexBackend,
    NoopIndexBackend,
    HybridIndexBackend,
)
from reality_rag_indexing.backends import (
    OpenSearchIndexWriter,
    QdrantPointWriter,
)

__all__ = [
    "get_index_backend",
    "IndexBackend",
    "NoopIndexBackend",
    "HybridIndexBackend",
    "OpenSearchIndexWriter",
    "QdrantPointWriter",
]
