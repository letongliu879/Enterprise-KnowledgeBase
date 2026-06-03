"""Smoke test for reality_rag_documents package import."""

from reality_rag_documents import DocumentService, NoOpScanAdapter, ScanAdapter, object_id_from_hash


def test_imports():
    assert DocumentService is not None
    assert NoOpScanAdapter is not None
    assert ScanAdapter is not None
    assert object_id_from_hash("sha256:abcd") == "obj_sha256_abcd"
