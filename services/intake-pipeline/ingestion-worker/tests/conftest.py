"""Shared test fixtures for ingestion-worker tests."""

from __future__ import annotations

import tempfile

import pytest

import reality_rag_persistence.database as db
from reality_rag_persistence.database import get_session
from reality_rag_persistence.seed import seed_dev_dataset, seed_minimal_for_tests


@pytest.fixture(autouse=True)
def _setup_database():
    db.override_url_for_testing("sqlite:///:memory:")
    db.create_all()
    yield
    db.drop_all()


@pytest.fixture
def db_session():
    session = get_session()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def seeded_db(db_session):
    seed_minimal_for_tests(session=db_session)
    db_session.commit()
    return db_session


@pytest.fixture
def seeded_session(seeded_db):
    return seeded_db


@pytest.fixture
def dev_seeded_db(db_session):
    seed_dev_dataset(session=db_session)
    db_session.commit()
    return db_session


@pytest.fixture
def dev_seeded_session(dev_seeded_db):
    return dev_seeded_db


@pytest.fixture(autouse=True)
def _clear_workbench_env(monkeypatch):
    monkeypatch.delenv("WORKBENCH_API_BASE_URL", raising=False)
    monkeypatch.delenv("WORKBENCH_BASE_URL", raising=False)


@pytest.fixture(autouse=True)
def _setup_sidecar_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", tmp)
        yield


class InProcessDocumentOwnerClient:
    def __init__(self, session=None) -> None:
        self._session = session

    def _service(self, session):
        from reality_rag_documents import DocumentService

        return DocumentService(session)

    def _call_with_session(self, fn):
        if self._session is not None:
            return fn(self._session)
        session = get_session()
        try:
            result = fn(session)
            session.commit()
            return result
        finally:
            session.close()

    def create_source_file(self, collection_id: str, object_id: str, content_hash: str):
        sf = self._call_with_session(
            lambda session: self._service(session).create_source_file(
                collection_id=collection_id,
                object_id=object_id,
                content_hash=content_hash,
            )
        )
        return {
            "source_file_id": sf.source_file_id,
            "collection_id": sf.collection_id,
            "object_id": sf.object_id,
            "content_hash": sf.content_hash,
            "state": sf.state.value if hasattr(sf.state, "value") else str(sf.state),
        }

    def claim(self, source_file_id: str, job_id: str) -> bool:
        return self._call_with_session(
            lambda session: self._service(session).claim_source_file(source_file_id, job_id)
        )

    def mark_consumed(self, source_file_id: str, job_id: str) -> bool:
        return self._call_with_session(
            lambda session: self._service(session).mark_consumed(source_file_id, job_id)
        )

    def mark_cleanable(self, source_file_id: str, job_id: str) -> bool:
        return self._call_with_session(
            lambda session: self._service(session).mark_cleanable(source_file_id, job_id)
        )

    def find_active_by_content_hash(self, content_hash: str, collection_id: str):
        from reality_rag_persistence.repositories.source_files import SourceFileRepository

        sf = self._call_with_session(
            lambda session: SourceFileRepository(session).find_active_by_content_hash(content_hash, collection_id)
        )
        if sf is None:
            return None
        return {
            "source_file_id": sf.source_file_id,
            "collection_id": sf.collection_id,
            "object_id": sf.object_id,
            "content_hash": sf.content_hash,
            "state": sf.state.value if hasattr(sf.state, "value") else str(sf.state),
        }

    def get_object_blob(self, object_id: str):
        from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository

        obj = self._call_with_session(lambda session: ObjectBlobRepository(session).get(object_id))
        if obj is None:
            return None
        return {
            "object_id": obj.object_id,
            "content_hash": obj.content_hash,
            "storage_key": obj.storage_key,
            "ref_count": obj.ref_count,
            "status": obj.status,
            "size_bytes": obj.size_bytes,
        }

    def get_or_create_object_blob(self, content_hash: str, storage_key: str, size_bytes: int = 0):
        obj = self._call_with_session(
            lambda session: self._service(session).get_or_create_object_blob(content_hash, storage_key, size_bytes)
        )
        return {
            "object_id": obj.object_id,
            "content_hash": obj.content_hash,
            "storage_key": obj.storage_key,
            "ref_count": obj.ref_count,
            "status": obj.status,
        }


@pytest.fixture
def inprocess_document_owner(monkeypatch):
    import ingestion_worker.job_event_flow as job_event_flow_mod
    import ingestion_worker.outbox_deliver as outbox_deliver_mod
    import ingestion_worker.pipeline as pipeline_mod

    monkeypatch.setattr(pipeline_mod, "DocumentServiceClient", InProcessDocumentOwnerClient)
    monkeypatch.setattr(job_event_flow_mod, "DocumentServiceClient", InProcessDocumentOwnerClient)
    monkeypatch.setattr(outbox_deliver_mod, "DocumentServiceClient", InProcessDocumentOwnerClient)
    return InProcessDocumentOwnerClient
