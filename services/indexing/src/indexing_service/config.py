"""Indexing configuration — re-exports from contracts for backward compatibility.

New code should import from reality_rag_contracts directly.
"""

from __future__ import annotations

from reality_rag_contracts.config import (  # noqa: F401
    IndexBackendConfig,
    IndexingConfig,
    IndexingModelConfig,
    load_indexing_config,
    normalize_chat_model,
    normalize_embedding_model,
)
