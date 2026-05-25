from reality_rag_contracts import (
    Collection,
    ConversionStatus,
    PublishStatus,
    SourceFileState,
    Tenant,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.models import IntakeJobModel, StageResultModel, StageTaskModel
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from reality_rag_persistence.repositories.tenants import TenantRepository

from ingestion_worker.orchestrator import OrchestratorService
from ingestion_worker.stage_runtime import run_publishing


def _seed_dependencies(session) -> None:
    if TenantRepository(session).get("default") is None:
        TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
    if CollectionRepository(session).get("col-1") is None:
        CollectionRepository(session).save(
            Collection(
                collection_id="col-1",
                tenant_id="default",
                name="Test Collection",
                authority_level=5,
            )
        )
    session.commit()


def test_run_publishing_uses_final_doc_id_and_approved_publish_status():
    session = get_session()
    try:
        _seed_dependencies(session)
        ObjectBlobRepository(session).create(
            object_id="obj-stage-runtime-1",
            content_hash="sha256:stage-runtime-1",
            storage_key=__file__,
            size_bytes=1,
        )
        SourceFileRepository(session).create(
            source_file_id="src-stage-runtime-1",
            collection_id="col-1",
            object_id="obj-stage-runtime-1",
            content_hash="sha256:stage-runtime-1",
            state=SourceFileState.CONSUMED,
        )
        job = OrchestratorService(session).create_intake_job(
            "src-stage-runtime-1",
            "obj-stage-runtime-1",
            "col-1",
        )

        row = session.get(IntakeJobModel, job.intake_job_id)
        assert row is not None
        row.preliminary_doc_id = "pre-doc-1"
        row.final_doc_id = "doc-final-1"

        session.add(
            StageResultModel(
                stage_result_id="res-stage-runtime-conv",
                stage_task_id="task-stage-runtime-conv",
                stage_attempt_id="att-stage-runtime-conv",
                intake_job_id=job.intake_job_id,
                stage_name="conversion",
                idempotency_key="conv:key",
                result_hash="hash:conv",
                summary_json={
                    "preliminary_doc_id": "pre-doc-1",
                    "logical_document_id": "logical-1",
                    "version": 1,
                    "conversion_result": {
                        "source_file_path": __file__,
                        "conversion_status": ConversionStatus.SUCCESS.value,
                        "doc_id": "pre-doc-1",
                        "canonical_asset_path": "",
                        "canonical_md": "# Title\n\nBody text",
                        "error_message": "",
                        "warnings": [],
                        "metadata": {"converter": "test", "extension": ".py"},
                    },
                    "quality_report": {
                        "doc_id": "pre-doc-1",
                        "recommended_review_status": PublishStatus.QUARANTINED.value,
                        "blocking_reasons": ["High garbled text rate: 77.5%"],
                    },
                },
            )
        )
        session.add(
            StageResultModel(
                stage_result_id="res-stage-runtime-review",
                stage_task_id="task-stage-runtime-review",
                stage_attempt_id="att-stage-runtime-review",
                intake_job_id=job.intake_job_id,
                stage_name="agent_review",
                idempotency_key="review:key",
                result_hash="hash:review",
                summary_json={
                    "agent_review": {
                        "doc_id": "pre-doc-1",
                        "decision": "quarantine",
                        "publish_recommendation": PublishStatus.QUARANTINED.value,
                        "risk_tags": ["garbled_text"],
                    },
                    "review_context": {},
                },
            )
        )
        session.commit()

        run_publishing(session, job.intake_job_id)
        session.commit()

        saved_doc = DocumentRepository(session).get("doc-final-1")
        assert saved_doc is not None
        assert saved_doc.doc_id == "doc-final-1"
        assert saved_doc.publish_status == PublishStatus.PUBLISHED
        assert "doc-final-1" in saved_doc.asset_paths["canonical_md"]

        task = (
            session.query(StageTaskModel)
            .filter(StageTaskModel.intake_job_id == job.intake_job_id)
            .filter(StageTaskModel.stage_name == "publishing")
            .first()
        )
        assert task is not None
        assert task.idempotency_key.endswith("doc-final-1")
    finally:
        session.close()
