"""Tests for trash endpoints."""

from fastapi.testclient import TestClient


class TestTrash:
    """Trash endpoints: list, restore, hard-delete."""

    def test_list_trash_empty(self, client: TestClient, uploader_token: str):
        """No archived/retracted docs returns empty list."""
        resp = client.get(
            "/workbench/trash",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_trash_with_items(self, client: TestClient, uploader_token: str, db_session):
        """Archived and retracted documents show up in trash."""
        from reality_rag_persistence.models import WorkbenchDocumentProjectionModel

        tenant = "tenant_acme"

        # Active doc — should NOT appear
        active = WorkbenchDocumentProjectionModel(
            doc_id="doc_active",
            tenant_id=tenant,
            collection_id="col_default",
            document_state="ACTIVE",
            filename="active.pdf",
            mime_type="application/pdf",
        )
        db_session.add(active)

        # Archived doc
        archived = WorkbenchDocumentProjectionModel(
            doc_id="doc_archived",
            tenant_id=tenant,
            collection_id="col_default",
            document_state="ARCHIVED",
            filename="archived.pdf",
            mime_type="application/pdf",
        )
        db_session.add(archived)

        # Retracted doc
        retracted = WorkbenchDocumentProjectionModel(
            doc_id="doc_retracted",
            tenant_id=tenant,
            collection_id="col_default",
            document_state="RETRACTED",
            filename="retracted.pdf",
            mime_type="application/pdf",
        )
        db_session.add(retracted)

        db_session.commit()

        resp = client.get(
            "/workbench/trash",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        doc_ids = {item["doc_id"] for item in data["items"]}
        assert "doc_archived" in doc_ids
        assert "doc_retracted" in doc_ids
        assert "doc_active" not in doc_ids

    def test_restore_document(self, client: TestClient, uploader_token: str, db_session):
        """Restore sets document_state back to ACTIVE."""
        from reality_rag_persistence.models import WorkbenchDocumentProjectionModel

        tenant = "tenant_acme"
        doc = WorkbenchDocumentProjectionModel(
            doc_id="doc_trashed",
            tenant_id=tenant,
            collection_id="col_default",
            document_state="ARCHIVED",
            filename="trashed.pdf",
            mime_type="application/pdf",
        )
        db_session.add(doc)
        db_session.commit()

        resp = client.post(
            "/workbench/trash/doc_trashed/restore",
            headers={"Authorization": f"{uploader_token}"},
        )

        # Should fail — wrong prefix. Use Bearer
        assert resp.status_code == 401

    def test_restore_document_correct_auth(self, client: TestClient, uploader_token: str, db_session):
        """Restore sets document_state back to ACTIVE with correct auth."""
        from reality_rag_persistence.models import WorkbenchDocumentProjectionModel

        tenant = "tenant_acme"
        doc = WorkbenchDocumentProjectionModel(
            doc_id="doc_trashed2",
            tenant_id=tenant,
            collection_id="col_default",
            document_state="ARCHIVED",
            filename="trashed.pdf",
            mime_type="application/pdf",
        )
        db_session.add(doc)
        db_session.commit()

        resp = client.post(
            "/workbench/trash/doc_trashed2/restore",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_id"] == "doc_trashed2"
        assert data["document_state"] == "ACTIVE"

    def test_hard_delete_document(self, client: TestClient, uploader_token: str, db_session):
        """Hard delete removes the projection from DB."""
        from reality_rag_persistence.models import WorkbenchDocumentProjectionModel
        from workbench_api.projections.repository import DocumentProjectionRepository

        tenant = "tenant_acme"
        doc = WorkbenchDocumentProjectionModel(
            doc_id="doc_delete_me",
            tenant_id=tenant,
            collection_id="col_default",
            document_state="ARCHIVED",
            filename="gone.pdf",
            mime_type="application/pdf",
        )
        db_session.add(doc)
        db_session.commit()

        resp = client.delete(
            "/workbench/trash/doc_delete_me",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 204

        # Verify gone from DB
        repo = DocumentProjectionRepository(db_session)
        assert repo.get("doc_delete_me") is None
