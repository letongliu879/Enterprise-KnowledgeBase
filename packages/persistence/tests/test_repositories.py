"""Test all persistence repositories with SQLite in-memory backend."""

from datetime import datetime, timezone

from reality_rag_contracts import (
    ApiKeyRegistryEntry,
    ApplicationProfile,
    CanonicalMetadata,
    Collection,
    ConversionReport,
    ConversionResult,
    ConversionStatus,
    IndexRegistryStatus,
    IndexStatus,
    IngestionJob,
    JobInfo,
    JobStatus,
    DocumentPolicy,
    PolicyCondition,
    PolicySubject,
    PrincipalProfile,
    PublishStatus,
    Tenant,
)

from reality_rag_persistence.repositories.tenants import TenantRepository
from reality_rag_persistence.repositories.api_key_registry import ApiKeyRegistryRepository
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.jobs import JobRepository
from reality_rag_persistence.repositories.application_profiles import ApplicationProfileRepository
from reality_rag_persistence.repositories.document_policies import DocumentPolicyRepository
from reality_rag_persistence.repositories.ingestion import IngestionRepository
from reality_rag_persistence.repositories.index_registry import (
    IndexRegistryRepository,
    IndexVersionEntry,
)
from reality_rag_persistence.repositories.principal_profiles import PrincipalProfileRepository
from reality_rag_persistence.repositories.run_audit import (
    RunStepRepository,
    RunTraceRepository,
    TraceArtifactRepository,
)


class TestTenantRepository:
    def test_get_nonexistent_returns_none(self, session):
        repo = TenantRepository(session)
        assert repo.get("no-such-tenant") is None

    def test_save_and_get(self, session):
        repo = TenantRepository(session)
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        repo.save(tenant)
        session.commit()

        result = repo.get("t1")
        assert result is not None
        assert result.tenant_id == "t1"
        assert result.name == "Test Tenant"

    def test_list_all(self, session):
        repo = TenantRepository(session)
        repo.save(Tenant(tenant_id="t1", name="One"))
        repo.save(Tenant(tenant_id="t2", name="Two"))
        session.commit()

        tenants = repo.list_all()
        assert len(tenants) == 2


class TestRunAuditRepositories:
    def test_run_trace_upsert_and_lookup(self, session):
        repo = RunTraceRepository(session)
        first = repo.upsert(
            trace_id="trc-1",
            run_kind="intake",
            tenant_id="t1",
            collection_id="col-1",
            principal_id="system",
            query_id="job-1",
            index_version_id="pending",
            profile_id="intake",
            root_status="RUNNING",
            debug_ref="dbg://intake/trc-1",
            result_count=0,
            source_file_id="src-1",
            intake_job_id="job-1",
        )
        second = repo.upsert(
            trace_id="trc-1",
            run_kind="intake",
            tenant_id="t1",
            collection_id="col-1",
            principal_id="system",
            query_id="job-1",
            index_version_id="pending",
            profile_id="intake",
            root_status="SUCCEEDED",
            debug_ref="dbg://intake/trc-1",
            result_count=1,
            source_file_id="src-1",
            intake_job_id="job-1",
            final_doc_id="doc-1",
        )
        session.commit()

        assert first.run_trace_id == second.run_trace_id
        rows = repo.list_by_source_file_id("src-1")
        assert len(rows) == 1
        assert rows[0].root_status == "SUCCEEDED"
        assert rows[0].final_doc_id == "doc-1"

    def test_run_steps_and_artifacts_append(self, session):
        step_repo = RunStepRepository(session)
        artifact_repo = TraceArtifactRepository(session)
        step_repo.append(
            trace_id="trc-2",
            step_name="parse_preview_requested",
            status="STARTED",
            summary="source_file_id=src-2",
        )
        step_repo.append(
            trace_id="trc-2",
            step_name="parse_snapshot_persisted",
            status="SUCCEEDED",
            summary="parse_snapshot_id=pss-src-2",
        )
        artifact_repo.append(
            trace_id="trc-2",
            artifact_ref="parse_snapshot:pss-src-2",
            artifact_kind="parse_snapshot",
            summary="parser_id=naive",
        )
        session.commit()

        steps = step_repo.list_by_trace_id("trc-2")
        artifacts = artifact_repo.list_by_trace_id("trc-2")
        assert [step.step_name for step in steps] == [
            "parse_preview_requested",
            "parse_snapshot_persisted",
        ]
        assert len(artifacts) == 1
        assert artifacts[0].artifact_kind == "parse_snapshot"


class TestCollectionRepository:
    def test_save_and_get(self, session):
        TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
        repo = CollectionRepository(session)

        col = Collection(
            collection_id="col-a", tenant_id="default",
            name="Col A", description="Test", authority_level=5,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        repo.save(col)
        session.commit()

        result = repo.get("col-a")
        assert result is not None
        assert result.name == "Col A"
        assert result.authority_level == 5

    def test_list_by_tenant(self, session):
        TenantRepository(session).save(Tenant(tenant_id="t1", name="T1"))
        TenantRepository(session).save(Tenant(tenant_id="t2", name="T2"))
        repo = CollectionRepository(session)
        repo.save(Collection(collection_id="c1", tenant_id="t1", name="C1"))
        repo.save(Collection(collection_id="c2", tenant_id="t1", name="C2"))
        repo.save(Collection(collection_id="c3", tenant_id="t2", name="C3"))
        session.commit()

        assert len(repo.list_by_tenant("t1")) == 2
        assert len(repo.list_by_tenant("t2")) == 1

    def test_count(self, session):
        TenantRepository(session).save(Tenant(tenant_id="t", name="T"))
        repo = CollectionRepository(session)
        assert repo.count() == 0
        repo.save(Collection(collection_id="c1", tenant_id="t", name="C1"))
        repo.save(Collection(collection_id="c2", tenant_id="t", name="C2"))
        session.commit()
        assert repo.count() == 2


class TestDocumentRepository:
    def _seed_tenant_and_collection(self, session):
        TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
        CollectionRepository(session).save(Collection(
            collection_id="col-1", tenant_id="default", name="Col 1",
        ))

    def test_save_and_get(self, session):
        self._seed_tenant_and_collection(session)
        repo = DocumentRepository(session)

        doc = CanonicalMetadata(
            doc_id="doc-1", logical_document_id="ldoc-1",
            tenant_id="default", collection_id="col-1",
            source_hash="abc123", version=1,
            publish_status=PublishStatus.PUBLISHED,
            index_status=IndexStatus.INDEXED,
            domain_tags=["finance"],
            processing_summary="converted via markitdown",
            asset_paths={"canonical_md": "/sidecar/col-1/doc-1/canonical.md"},
        )
        repo.save(doc)
        session.commit()

        result = repo.get("doc-1")
        assert result is not None
        assert result.publish_status == PublishStatus.PUBLISHED
        assert result.index_status == IndexStatus.INDEXED
        assert result.domain_tags == ["finance"]
        assert result.processing_summary == "converted via markitdown"
        assert result.asset_paths == {"canonical_md": "/sidecar/col-1/doc-1/canonical.md"}

    def test_list_by_collection(self, session):
        self._seed_tenant_and_collection(session)
        TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
        CollectionRepository(session).save(Collection(
            collection_id="col-2", tenant_id="default", name="Col 2",
        ))
        repo = DocumentRepository(session)
        repo.save(CanonicalMetadata(
            doc_id="d1", logical_document_id="l1",
            tenant_id="default", collection_id="col-1",
            source_hash="h1", version=1,
        ))
        repo.save(CanonicalMetadata(
            doc_id="d2", logical_document_id="l2",
            tenant_id="default", collection_id="col-1",
            source_hash="h2", version=1,
        ))
        repo.save(CanonicalMetadata(
            doc_id="d3", logical_document_id="l3",
            tenant_id="default", collection_id="col-2",
            source_hash="h3", version=1,
        ))
        session.commit()

        assert len(repo.list_by_collection("col-1")) == 2
        assert len(repo.list_by_collection("col-2")) == 1

    def test_get_by_source_hash_returns_active_doc(self, session):
        self._seed_tenant_and_collection(session)
        repo = DocumentRepository(session)
        repo.save(CanonicalMetadata(
            doc_id="d-hash", logical_document_id="l-hash",
            tenant_id="default", collection_id="col-1",
            source_hash="hash-abc", version=1, archived=False,
        ))
        session.commit()
        found = repo.get_by_source_hash("hash-abc", "col-1")
        assert found is not None
        assert found.doc_id == "d-hash"
        assert repo.get_by_source_hash("hash-abc", "col-2") is None

    def test_get_by_source_hash_returns_none_for_archived(self, session):
        self._seed_tenant_and_collection(session)
        repo = DocumentRepository(session)
        repo.save(CanonicalMetadata(
            doc_id="d-arch", logical_document_id="l-arch",
            tenant_id="default", collection_id="col-1",
            source_hash="hash-arch", version=1, archived=True,
        ))
        session.commit()
        assert repo.get_by_source_hash("hash-arch", "col-1") is None

    def test_archive_document_sets_archived_true(self, session):
        self._seed_tenant_and_collection(session)
        repo = DocumentRepository(session)
        repo.save(CanonicalMetadata(
            doc_id="d-arch", logical_document_id="l-arch",
            tenant_id="default", collection_id="col-1",
            source_hash="hash-arch", version=1, archived=False,
        ))
        session.commit()
        repo.archive_document("d-arch")
        session.commit()
        found = repo.get("d-arch")
        assert found is not None
        assert found.archived is True

    def test_get_latest_by_logical_id_returns_highest_version(self, session):
        self._seed_tenant_and_collection(session)
        repo = DocumentRepository(session)
        repo.save(CanonicalMetadata(
            doc_id="d-v1", logical_document_id="l-latest",
            tenant_id="default", collection_id="col-1",
            source_hash="hash-v1", version=1, archived=False,
        ))
        repo.save(CanonicalMetadata(
            doc_id="d-v2", logical_document_id="l-latest",
            tenant_id="default", collection_id="col-1",
            source_hash="hash-v2", version=2, archived=False,
        ))
        session.commit()
        latest = repo.get_latest_by_logical_id("l-latest")
        assert latest is not None
        assert latest.version == 2

    def test_list_active_excludes_archived(self, session):
        self._seed_tenant_and_collection(session)
        repo = DocumentRepository(session)
        repo.save(CanonicalMetadata(
            doc_id="d-active", logical_document_id="l-active",
            tenant_id="default", collection_id="col-1",
            source_hash="hash-a", version=1, archived=False,
        ))
        repo.save(CanonicalMetadata(
            doc_id="d-archived", logical_document_id="l-archived",
            tenant_id="default", collection_id="col-1",
            source_hash="hash-b", version=1, archived=True,
        ))
        session.commit()
        all_docs = repo.list_all()
        active_docs = repo.list_active()
        assert len(all_docs) == 2
        assert len(active_docs) == 1
        assert active_docs[0].doc_id == "d-active"


class TestJobRepository:
    def test_save_and_get(self, session):
        repo = JobRepository(session)
        job = JobInfo(
            job_id="j1", job_type="index",
            status=JobStatus.COMPLETED,
            collection_id="col-1", doc_id="doc-1",
            created_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
            updated_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
        )
        repo.save(job)
        session.commit()

        result = repo.get("j1")
        assert result is not None
        assert result.status == JobStatus.COMPLETED
        assert result.job_type == "index"

    def test_failed_job_error_message_roundtrip(self, session):
        repo = JobRepository(session)
        job = JobInfo(
            job_id="j-err", job_type="index",
            status=JobStatus.FAILED,
            collection_id="col-1", doc_id="doc-x",
            error_message="OCR failed on page 3",
        )
        repo.save(job)
        session.commit()

        result = repo.get("j-err")
        assert result.error_message == "OCR failed on page 3"


class TestApplicationProfileRepository:
    def _seed_tenant(self, session):
        TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))

    def test_save_and_get(self, session):
        self._seed_tenant(session)
        repo = ApplicationProfileRepository(session)

        profile = ApplicationProfile(
            application_profile_id="ap-1", tenant_id="default",
            name="Test Profile",
            allowed_collections=["col-1"],
            default_collections=["col-1"],
        )
        repo.save(profile)
        session.commit()

        result = repo.get("ap-1")
        assert result is not None
        assert result.name == "Test Profile"
        assert result.allowed_collections == ["col-1"]
        assert result.default_budget_policy == "balanced"

    def test_get_nonexistent_returns_none(self, session):
        repo = ApplicationProfileRepository(session)
        assert repo.get("no-such") is None

    def test_json_list_fields_roundtrip(self, session):
        self._seed_tenant(session)
        repo = ApplicationProfileRepository(session)

        profile = ApplicationProfile(
            application_profile_id="ap-json", tenant_id="default",
            name="JSON Test",
            allowed_collections=["col-1", "col-2", "col-3"],
            default_collections=["col-1"],
        )
        repo.save(profile)
        session.commit()

        result = repo.get("ap-json")
        assert result.allowed_collections == ["col-1", "col-2", "col-3"]


class TestApiKeyRegistryRepository:
    def test_save_and_get(self, session):
        repo = ApiKeyRegistryRepository(session)
        repo.save(ApiKeyRegistryEntry(
            api_key_id="rr-agent-platform-dev",
            display_name="Agent Platform Dev",
            agent_type_id="kb_assistant",
            knowledge_scopes=["col_policy", "col_handbook"],
            roles=["agent"],
            debug_permission=False,
            max_context_tokens=4096,
            enabled=True,
        ))
        session.commit()

        result = repo.get("rr-agent-platform-dev")
        assert result is not None
        assert result.agent_type_id == "kb_assistant"
        assert result.knowledge_scopes == ["col_policy", "col_handbook"]
        assert result.roles == ["agent"]
        assert result.enabled is True

    def test_list_enabled_filters_disabled_rows(self, session):
        repo = ApiKeyRegistryRepository(session)
        repo.save(ApiKeyRegistryEntry(
            api_key_id="enabled-key",
            display_name="Enabled",
            agent_type_id="kb_assistant",
            knowledge_scopes=["col_policy"],
            roles=["agent"],
            enabled=True,
        ))
        repo.save(ApiKeyRegistryEntry(
            api_key_id="disabled-key",
            display_name="Disabled",
            agent_type_id="kb_assistant",
            knowledge_scopes=["col_policy"],
            roles=["agent"],
            enabled=False,
        ))
        session.commit()

        enabled = repo.list_enabled()
        assert [entry.api_key_id for entry in enabled] == ["enabled-key"]


class TestPrincipalProfileRepository:
    def test_save_and_get(self, session):
        TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
        repo = PrincipalProfileRepository(session)
        repo.save(PrincipalProfile(
            tenant_id="default",
            user_id="user-1",
            role_ids=["finance_reader"],
            group_ids=["g1"],
            department_ids=["finance"],
            clearance_level=3,
            attributes={"business_domains": ["finance"]},
        ))
        session.commit()

        result = repo.get("user-1")
        assert result is not None
        assert result.role_ids == ["finance_reader"]
        assert result.clearance_level == 3


class TestDocumentPolicyRepository:
    def test_save_and_list_by_collection(self, session):
        TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
        CollectionRepository(session).save(Collection(collection_id="col-1", tenant_id="default", name="Col 1"))
        DocumentRepository(session).save(CanonicalMetadata(
            tenant_id="default",
            collection_id="col-1",
            doc_id="doc-1",
            logical_document_id="ldoc-1",
            source_hash="abc",
            version=1,
        ))
        repo = DocumentPolicyRepository(session)
        repo.save(DocumentPolicy(
            policy_id="p-1",
            tenant_id="default",
            collection_id="col-1",
            doc_id="doc-1",
            effect="allow",
            subjects=[PolicySubject(subject_type="role", subject_id="finance_reader")],
            conditions=[PolicyCondition(field="clearance_level", operator="gte", value=3)],
            priority=100,
            policy_version="v1",
        ))
        session.commit()

        result = repo.list_by_collection("col-1")
        assert len(result) == 1
        assert result[0].subjects[0].subject_type == "role"
        assert result[0].conditions[0].field == "clearance_level"


class TestIngestionRepository:
    def test_save_and_get_with_report(self, session):
        repo = IngestionRepository(session)

        now = datetime(2026, 5, 14, tzinfo=timezone.utc)
        report = ConversionReport(
            report_id="rpt-1", job_id="ingest-x",
            source_file_path="batch:2_files",
            conversion_status=ConversionStatus.SUCCESS,
            total_files=2, successful=2, failed=0, unsupported=0,
            details=[
                ConversionResult(
                    source_file_path="/tmp/f1.txt",
                    conversion_status=ConversionStatus.SUCCESS,
                    doc_id="doc-f1-v1",
                    canonical_asset_path="/sidecar/col-1/doc-f1-v1/canonical.md",
                    canonical_md="# File 1\n\nContent.",
                ),
                ConversionResult(
                    source_file_path="/tmp/f2.txt",
                    conversion_status=ConversionStatus.SUCCESS,
                    doc_id="doc-f2-v1",
                    canonical_asset_path="/sidecar/col-1/doc-f2-v1/canonical.md",
                    canonical_md="# File 2\n\nMore.",
                ),
            ],
            created_at=now,
        )
        job = IngestionJob(
            job_id="ingest-x", job_type="ingestion",
            status=JobStatus.COMPLETED, collection_id="col-1",
            source_files=["/tmp/f1.txt", "/tmp/f2.txt"],
            conversion_report=report,
            report_asset_path="/sidecar/col-1/ingest-x/conversion_report.json",
            created_at=now, updated_at=now,
        )
        repo.save(job)
        session.commit()

        result = repo.get("ingest-x")
        assert result is not None
        assert result.status == JobStatus.COMPLETED
        assert result.report_asset_path == "/sidecar/col-1/ingest-x/conversion_report.json"
        assert result.conversion_report is not None
        assert result.conversion_report.total_files == 2
        assert result.conversion_report.successful == 2
        assert len(result.conversion_report.details) == 2
        assert result.conversion_report.details[0].canonical_md == ""
        assert result.conversion_report.details[0].canonical_asset_path == "/sidecar/col-1/doc-f1-v1/canonical.md"

    def test_save_and_get_without_report(self, session):
        repo = IngestionRepository(session)
        now = datetime(2026, 5, 14, tzinfo=timezone.utc)
        job = IngestionJob(
            job_id="ingest-nr", job_type="ingestion",
            status=JobStatus.PENDING, collection_id="col-1",
            source_files=["/tmp/f.txt"],
            created_at=now, updated_at=now,
        )
        repo.save(job)
        session.commit()

        result = repo.get("ingest-nr")
        assert result is not None
        assert result.status == JobStatus.PENDING
        assert result.conversion_report is None

    def test_list_all(self, session):
        repo = IngestionRepository(session)
        now = datetime(2026, 5, 14, tzinfo=timezone.utc)
        repo.save(IngestionJob(
            job_id="i1", job_type="ingestion",
            status=JobStatus.COMPLETED, collection_id="col-1",
            source_files=[], created_at=now, updated_at=now,
        ))
        repo.save(IngestionJob(
            job_id="i2", job_type="ingestion",
            status=JobStatus.FAILED, collection_id="col-2",
            source_files=[], created_at=now, updated_at=now,
        ))
        session.commit()
        assert len(repo.list_all()) == 2


class TestIndexRegistryRepository:
    def test_save_and_get(self, session):
        repo = IndexRegistryRepository(session)
        entry = IndexVersionEntry(
            collection_id="col-1",
            index_version="col-1-v2",
            status=IndexRegistryStatus.INDEXED,
            created_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
            previous_index_version="col-1-v1",
        )
        repo.save(entry)
        session.commit()

        result = repo.get("col-1")
        assert result is not None
        assert result.index_version == "col-1-v2"
        assert result.status == IndexRegistryStatus.INDEXED
        assert result.previous_index_version == "col-1-v1"

    def test_get_index_versions_only_returns_indexed(self, session):
        repo = IndexRegistryRepository(session)
        repo.save(IndexVersionEntry("col-1", "col-1-v2", IndexRegistryStatus.INDEXED))
        repo.save(IndexVersionEntry("col-2", "col-2-v1", IndexRegistryStatus.INDEXED))
        repo.save(IndexVersionEntry("col-3", "col-3-v1", IndexStatus.NOT_INDEXED))
        session.commit()

        versions = repo.get_index_versions(["col-1", "col-2", "col-3"])
        assert len(versions) == 2
        assert versions["col-1"] == "col-1-v2"
        assert versions["col-2"] == "col-2-v1"
        assert "col-3" not in versions

    def test_indexing_keeps_active_version_until_activation(self, session):
        repo = IndexRegistryRepository(session)
        repo.save(IndexVersionEntry("col-1", "col-1-v1", IndexRegistryStatus.INDEXED))
        session.commit()

        repo.mark_indexing("col-1", "col-1-v2")
        session.commit()

        versions = repo.get_index_versions(["col-1"])
        entry = repo.get("col-1")
        assert versions["col-1"] == "col-1-v1"
        assert entry.target_index_version == "col-1-v2"
        assert entry.status == IndexRegistryStatus.INDEXING

        repo.activate("col-1")
        session.commit()

        activated = repo.get("col-1")
        assert activated.index_version == "col-1-v2"
        assert activated.previous_index_version == "col-1-v1"
        assert activated.target_index_version is None
        assert activated.status == IndexRegistryStatus.INDEXED

    def test_rollback_restores_previous_version(self, session):
        repo = IndexRegistryRepository(session)
        repo.save(
            IndexVersionEntry(
                collection_id="col-1",
                index_version="col-1-v2",
                previous_index_version="col-1-v1",
                status=IndexRegistryStatus.INDEXED,
            )
        )
        session.commit()

        repo.rollback("col-1")
        session.commit()

        rolled_back = repo.get("col-1")
        assert rolled_back.index_version == "col-1-v1"
        assert rolled_back.previous_index_version == "col-1-v2"
        assert rolled_back.status == IndexRegistryStatus.INDEXED

    def test_get_nonexistent_returns_none(self, session):
        repo = IndexRegistryRepository(session)
        assert repo.get("no-such") is None


class TestSeed:
    def test_seed_runs_without_error(self, session):
        from reality_rag_persistence.seed import seed
        seed(session=session)

        # After seeding, all repos should return data
        assert len(TenantRepository(session).list_all()) >= 1
        assert len(CollectionRepository(session).list_all()) >= 2
        assert len(DocumentRepository(session).list_all()) >= 3
        assert len(JobRepository(session).list_all()) >= 2
        assert len(ApplicationProfileRepository(session).list_all()) >= 3
        assert len(ApiKeyRegistryRepository(session).list_enabled()) >= 2
        assert len(PrincipalProfileRepository(session).list_by_tenant("default")) >= 3
        assert len(IngestionRepository(session).list_all()) >= 3
        assert len(IndexRegistryRepository(session).list_all()) >= 2
        assert len(DocumentPolicyRepository(session).list_by_collection("col-1")) >= 1

    def test_seed_is_repeatable(self, session):
        from reality_rag_persistence.seed import seed

        seed(session=session)
        seed(session=session)

        assert len(IngestionRepository(session).list_all()) >= 3
