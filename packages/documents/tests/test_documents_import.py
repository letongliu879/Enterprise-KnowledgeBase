"""Smoke test for reality_rag_documents package import."""

from reality_rag_documents import DocumentService, NoOpScanAdapter, ScanAdapter


def test_imports():
    assert DocumentService is not None
    assert NoOpScanAdapter is not None
    assert ScanAdapter is not None
