"""Shared document domain logic for Reality-RAG.

Extracted from ingestion-worker to break the cross-service import boundary.
Both ingestion-worker and document-service depend on this package.
"""

from .document_domain import DocumentService, ScanAdapter, NoOpScanAdapter, object_id_from_hash

__all__ = [
    "DocumentService",
    "ScanAdapter",
    "NoOpScanAdapter",
    "object_id_from_hash",
]
