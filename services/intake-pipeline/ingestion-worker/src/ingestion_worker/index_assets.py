"""Build index-ready assets from canonical markdown.

Re-exported from reality-rag-indexing shared package.
This module is kept for backward compatibility; new code should import
from reality_rag_indexing directly.
"""

from __future__ import annotations

from reality_rag_indexing import build_index_asset_bundle, retarget_index_asset_bundle

__all__ = [
    "build_index_asset_bundle",
    "retarget_index_asset_bundle",
]
