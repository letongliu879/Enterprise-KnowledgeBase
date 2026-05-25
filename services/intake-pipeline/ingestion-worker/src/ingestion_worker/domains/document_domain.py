"""Document domain — compatibility shim.

Core DocumentService has been extracted to the reality_rag_documents shared
package so that both ingestion-worker and the standalone document-service can
import it without cross-service boundaries.
"""

from __future__ import annotations

from reality_rag_documents import DocumentService, NoOpScanAdapter, ScanAdapter
from reality_rag_documents.document_domain import _object_id_from_hash

__all__ = [
    "DocumentService",
    "ScanAdapter",
    "NoOpScanAdapter",
    "_object_id_from_hash",
]
