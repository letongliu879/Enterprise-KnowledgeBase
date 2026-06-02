"""Seed development database with sample data matching existing in-memory repos.

Usage:
    python -m reality_rag_persistence.seed
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from reality_rag_contracts import (
    ApiKeyRegistryEntry,
    ApplicationProfile,
    CanonicalMetadata,
    Collection,
    ConversionReport,
    ConversionResult,
    ConversionStatus,
    IndexStatus,
    IngestionJob,
    JobInfo,
    JobStatus,
    DocumentPolicy,
    PolicyCondition,
    PolicySubject,
    PrincipalProfile,
    PublishStatus,
    RetrievalProfile,
    Tenant,
)

from .database import create_all, get_session
from .repositories.application_profiles import ApplicationProfileRepository
from .repositories.api_key_registry import ApiKeyRegistryRepository
from .repositories.collections import CollectionRepository
from .repositories.documents import DocumentRepository
from reality_rag_contracts import IndexRegistryStatus

from .repositories.index_registry import IndexRegistryRepository, IndexVersionEntry
from .repositories.ingestion import IngestionRepository
from .repositories.jobs import JobRepository
from .repositories.document_policies import DocumentPolicyRepository
from .repositories.principal_profiles import PrincipalProfileRepository
from .repositories.retrieval_profiles import RetrievalProfileRepository
from .repositories.tenants import TenantRepository

COL_POLICY = "col_policy"
COL_HANDBOOK = "col_handbook"


def _write_text_asset(asset_path: str, content: str) -> None:
    path = Path(asset_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json_asset(asset_path: str, payload: dict) -> None:
    path = Path(asset_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def seed(session=None) -> None:
    """Seed all tables with sample dev data."""
    own_session = session is None
    if own_session:
        create_all()
        session = get_session()

    try:
        _seed_tenants(session)
        _seed_collections(session)
        _seed_documents(session)
        _seed_jobs(session)
        _seed_application_profiles(session)
        _seed_api_key_registry(session)
        _seed_retrieval_profiles(session)
        _seed_principal_profiles(session)
        _seed_ingestion(session)
        _seed_index_registry(session)
        _seed_document_policies(session)
        session.commit()
    finally:
        if own_session:
            session.close()


def _seed_tenants(session):
    repo = TenantRepository(session)
    if repo.get("default") is None:
        repo.save(Tenant(tenant_id="default", name="Default Tenant"))


def _seed_collections(session):
    repo = CollectionRepository(session)
    if repo.get(COL_POLICY) is None:
        repo.save(Collection(
            collection_id=COL_POLICY, tenant_id="default",
            name="Financial Compliance",
            description="Primary collection of financial regulatory compliance documents.",
            authority_level=8,
            created_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
            updated_at=datetime(2025, 3, 10, tzinfo=timezone.utc),
        ))
    if repo.get(COL_HANDBOOK) is None:
        repo.save(Collection(
            collection_id=COL_HANDBOOK, tenant_id="default",
            name="Legal Contracts",
            description="Legal contracts and agreements requiring compliance review.",
            authority_level=7,
            created_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
        ))


def _seed_documents(session):
    repo = DocumentRepository(session)
    doc_001_asset_paths = {
        "canonical_md": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-001/canonical.md",
        "canonical_meta": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-001/canonical.meta.json",
        "quality_report": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-001/quality_report.json",
        "agent_review": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-001/agent_review.json",
        "processing_record": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-001/processing_record.json",
    }
    doc_002_asset_paths = {
        "canonical_md": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-002/canonical.md",
        "canonical_meta": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-002/canonical.meta.json",
        "quality_report": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-002/quality_report.json",
        "processing_record": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-002/processing_record.json",
    }
    doc_003_asset_paths = {
        "canonical_md": "E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/doc-003/canonical.md",
        "canonical_meta": "E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/doc-003/canonical.meta.json",
        "quality_report": "E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/doc-003/quality_report.json",
        "agent_review": "E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/doc-003/agent_review.json",
        "processing_record": "E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/doc-003/processing_record.json",
    }
    doc_004_asset_paths = {
        "canonical_md": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/canonical.md",
        "canonical_meta": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/canonical.meta.json",
        "quality_report": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/quality_report.json",
        "agent_review": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/agent_review.json",
        "review_context": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/review_context.json",
        "human_review": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/human_review.json",
        "processing_record": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/processing_record.json",
        "chunk_manifest": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/chunk_manifest.json",
        "opensearch_records": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/opensearch_records.json",
        "qdrant_points": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/qdrant_points.json",
    }

    if repo.get("doc-001") is None:
        repo.save(CanonicalMetadata(
            doc_id="doc-001", logical_document_id="ld-001",
            tenant_id="default", collection_id=COL_POLICY,
            source_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            version=3,
            archived=False,
            publish_status=PublishStatus.PUBLISHED,
            index_status=IndexStatus.INDEXED,
            effective_date=datetime(2025, 3, 15, tzinfo=timezone.utc),
            authority_level=8,
            governance_level="high",
            domain_tags=["compliance", "financial-reporting"],
            risk_tags=["regulatory"],
            quality_summary="High-quality PDF conversion with embedded tables preserved.",
            asset_paths=doc_001_asset_paths,
        ))
    if repo.get("doc-002") is None:
        repo.save(CanonicalMetadata(
            doc_id="doc-002", logical_document_id="ld-002",
            tenant_id="default", collection_id=COL_POLICY,
            source_hash="b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
            version=1,
            archived=False,
            publish_status=PublishStatus.DRAFT,
            index_status=IndexStatus.NOT_INDEXED,
            authority_level=5,
            governance_level="standard",
            domain_tags=["policy", "internal-procedures"],
            risk_tags=[],
            quality_summary="Draft document awaiting final review before publishing.",
            asset_paths=doc_002_asset_paths,
        ))
    if repo.get("doc-003") is None:
        repo.save(CanonicalMetadata(
            doc_id="doc-003", logical_document_id="ld-003",
            tenant_id="default", collection_id=COL_HANDBOOK,
            source_hash="c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            version=2,
            archived=False,
            publish_status=PublishStatus.PUBLISHED,
            index_status=IndexStatus.FAILED,
            effective_date=datetime(2025, 2, 28, tzinfo=timezone.utc),
            authority_level=7,
            governance_level="standard",
            domain_tags=["legal", "contracts"],
            risk_tags=["indexing-failure"],
            quality_summary="Published but indexing failed due to embedded image OCR issues.",
            asset_paths=doc_003_asset_paths,
        ))
    if repo.get("doc-004") is None:
        repo.save(CanonicalMetadata(
            doc_id="doc-004", logical_document_id="ld-004",
            tenant_id="default", collection_id=COL_POLICY,
            source_hash="d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
            version=1,
            archived=False,
            publish_status=PublishStatus.PENDING_REVIEW,
            index_status=IndexStatus.NOT_INDEXED,
            authority_level=6,
            governance_level="standard",
            domain_tags=["policy", "travel"],
            risk_tags=["needs-human-review"],
            quality_summary="Converted markdown is usable but the agent requested human confirmation before publication.",
            asset_paths=doc_004_asset_paths,
        ))

    _write_text_asset(
        doc_001_asset_paths["canonical_md"],
        "## Q1 2025 Financial Report\n\nRevenue: $12.4M (up 8% YoY)\n\n### Highlights\n- Net income grew 12%\n- Operating margin expanded to 24%\n",
    )
    _write_json_asset(
        doc_001_asset_paths["canonical_meta"],
        CanonicalMetadata(
            doc_id="doc-001", logical_document_id="ld-001",
            tenant_id="default", collection_id=COL_POLICY,
            source_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            version=3,
            publish_status=PublishStatus.PUBLISHED,
            index_status=IndexStatus.INDEXED,
            effective_date=datetime(2025, 3, 15, tzinfo=timezone.utc),
            authority_level=8,
            governance_level="high",
            domain_tags=["compliance", "financial-reporting"],
            risk_tags=["regulatory"],
            quality_summary="High-quality PDF conversion with embedded tables preserved.",
            asset_paths=doc_001_asset_paths,
        ).model_dump(mode="json"),
    )
    _write_json_asset(
        doc_001_asset_paths["quality_report"],
        {
            "doc_id": "doc-001",
            "support_tier": "A",
            "conversion_score": 0.97,
            "ocr_used": False,
            "ocr_confidence_summary": {},
            "garbled_text_rate": 0.0,
            "blank_ratio": 0.01,
            "table_extraction_quality": 0.95,
            "image_density": 0.0,
            "source_canonical_length_mismatch": 0.0,
            "truncation_suspicion": False,
            "recommended_review_status": "published",
            "blocking_reasons": [],
        },
    )
    _write_json_asset(
        doc_001_asset_paths["agent_review"],
        {
            "doc_id": "doc-001",
            "decision": "approve",
            "confidence": 0.92,
            "reasons": ["All sections match source", "Tables correctly extracted"],
            "risk_tags": ["low-risk"],
            "suggested_actions": [],
            "publish_recommendation": "published",
            "sections_requiring_review": [],
        },
    )
    _write_json_asset(
        doc_001_asset_paths["processing_record"],
        {
            "doc_id": "doc-001",
            "job_id": "ingest-001",
            "collection_id": COL_POLICY,
            "source_file_path": "datasets/raw/finance/2025-q1-report.docx",
            "source_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "conversion_status": "success",
            "tool_chain": ["ragflow-naive"],
            "tool_versions": {},
            "parameters": {},
            "warnings": [],
            "error_message": "",
            "published_asset_paths": doc_001_asset_paths,
            "created_at": datetime(2025, 5, 10, 9, 30, tzinfo=timezone.utc).isoformat(),
        },
    )

    _write_text_asset(
        doc_002_asset_paths["canonical_md"],
        "## Independent Auditor's Letter\n\nWe have audited the financial statements of Example Corp for Q1 2025.\n\nOpinion: Unqualified.\n",
    )
    _write_json_asset(
        doc_002_asset_paths["canonical_meta"],
        CanonicalMetadata(
            doc_id="doc-002", logical_document_id="ld-002",
            tenant_id="default", collection_id=COL_POLICY,
            source_hash="b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
            version=1,
            publish_status=PublishStatus.DRAFT,
            index_status=IndexStatus.NOT_INDEXED,
            authority_level=5,
            governance_level="standard",
            domain_tags=["policy", "internal-procedures"],
            risk_tags=[],
            quality_summary="Draft document awaiting final review before publishing.",
            asset_paths=doc_002_asset_paths,
        ).model_dump(mode="json"),
    )
    _write_json_asset(
        doc_002_asset_paths["quality_report"],
        {
            "doc_id": "doc-002",
            "support_tier": "B",
            "conversion_score": 0.88,
            "ocr_used": False,
            "ocr_confidence_summary": {},
            "garbled_text_rate": 0.01,
            "blank_ratio": 0.02,
            "table_extraction_quality": 0.80,
            "image_density": 0.0,
            "source_canonical_length_mismatch": 0.0,
            "truncation_suspicion": False,
            "recommended_review_status": "pending_review",
            "blocking_reasons": [],
        },
    )
    _write_json_asset(
        doc_002_asset_paths["processing_record"],
        {
            "doc_id": "doc-002",
            "job_id": "ingest-001",
            "collection_id": COL_POLICY,
            "source_file_path": "datasets/raw/finance/2025-q1-audit-letter.docx",
            "source_hash": "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
            "conversion_status": "success",
            "tool_chain": ["ragflow-naive"],
            "tool_versions": {},
            "parameters": {},
            "warnings": [],
            "error_message": "",
            "published_asset_paths": doc_002_asset_paths,
            "created_at": datetime(2025, 5, 10, 9, 31, tzinfo=timezone.utc).isoformat(),
        },
    )

    _write_text_asset(
        doc_003_asset_paths["canonical_md"],
        "## Contract OCR Recovery\n\nScanned contract requires manual table correction.\n",
    )
    _write_json_asset(
        doc_003_asset_paths["canonical_meta"],
        CanonicalMetadata(
            doc_id="doc-003", logical_document_id="ld-003",
            tenant_id="default", collection_id=COL_HANDBOOK,
            source_hash="c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            version=2,
            publish_status=PublishStatus.PUBLISHED,
            index_status=IndexStatus.FAILED,
            effective_date=datetime(2025, 2, 28, tzinfo=timezone.utc),
            authority_level=7,
            governance_level="standard",
            domain_tags=["legal", "contracts"],
            risk_tags=["indexing-failure"],
            quality_summary="Published but indexing failed due to embedded image OCR issues.",
            asset_paths=doc_003_asset_paths,
        ).model_dump(mode="json"),
    )
    _write_json_asset(
        doc_003_asset_paths["quality_report"],
        {
            "doc_id": "doc-003",
            "support_tier": "C",
            "conversion_score": 0.65,
            "ocr_used": True,
            "ocr_confidence_summary": {"page_1": 0.72, "page_2": 0.58},
            "garbled_text_rate": 0.05,
            "blank_ratio": 0.03,
            "table_extraction_quality": 0.45,
            "image_density": 3.2,
            "source_canonical_length_mismatch": 0.0,
            "truncation_suspicion": False,
            "recommended_review_status": "quarantined",
            "blocking_reasons": ["Low OCR confidence on page 2", "Table extraction below threshold"],
        },
    )
    _write_json_asset(
        doc_003_asset_paths["agent_review"],
        {
            "doc_id": "doc-003",
            "decision": "quarantine",
            "confidence": 0.78,
            "reasons": ["OCR quality below threshold on page 2"],
            "risk_tags": ["ocr-risk", "quality-concern"],
            "suggested_actions": ["Re-scan source document", "Manual table correction"],
            "publish_recommendation": "quarantined",
            "sections_requiring_review": ["Appendix A — Financial Tables"],
        },
    )
    _write_json_asset(
        doc_003_asset_paths["processing_record"],
        {
            "doc_id": "doc-003",
            "job_id": "ingest-002",
            "collection_id": COL_HANDBOOK,
            "source_file_path": "datasets/raw/legal/contract-v3-scanned.pdf",
            "source_hash": "c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "conversion_status": "failed",
            "tool_chain": ["ragflow-naive"],
            "tool_versions": {},
            "parameters": {},
            "warnings": [],
            "error_message": "OCR threshold not met on page 2",
            "published_asset_paths": doc_003_asset_paths,
            "created_at": datetime(2025, 5, 11, 14, 0, tzinfo=timezone.utc).isoformat(),
        },
    )

    source_doc_004 = Path("E:/AI/My-Project/Reality-RAG/datasets/raw/finance/manual-review-policy.md")
    source_doc_004.parent.mkdir(parents=True, exist_ok=True)
    source_doc_004.write_text(
        "# Travel Exception Policy\n\n"
        "Expenses over 500 USD require director approval and a written exception explanation.\n\n"
        "Draft note: the exception explanation must reference the travel request number.\n",
        encoding="utf-8",
    )
    _write_text_asset(
        doc_004_asset_paths["canonical_md"],
        "## Travel Exception Policy\n\n"
        "Expenses over 500 USD require director approval.\n\n"
        "A written exception explanation is required before reimbursement.\n",
    )
    _write_json_asset(
        doc_004_asset_paths["canonical_meta"],
        CanonicalMetadata(
            doc_id="doc-004", logical_document_id="ld-004",
            tenant_id="default", collection_id=COL_POLICY,
            source_hash="d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
            version=1,
            publish_status=PublishStatus.PENDING_REVIEW,
            index_status=IndexStatus.NOT_INDEXED,
            authority_level=6,
            governance_level="standard",
            domain_tags=["policy", "travel"],
            risk_tags=["needs-human-review"],
            quality_summary="Converted markdown is usable but the agent requested human confirmation before publication.",
            asset_paths=doc_004_asset_paths,
        ).model_dump(mode="json"),
    )
    _write_json_asset(
        doc_004_asset_paths["quality_report"],
        {
            "doc_id": "doc-004",
            "support_tier": "B",
            "conversion_score": 0.84,
            "ocr_used": False,
            "ocr_confidence_summary": {},
            "garbled_text_rate": 0.0,
            "blank_ratio": 0.01,
            "table_extraction_quality": 0.9,
            "image_density": 0.0,
            "source_canonical_length_mismatch": 0.12,
            "truncation_suspicion": False,
            "recommended_review_status": "pending_review",
            "blocking_reasons": ["Manual confirmation required for missing exception-reference detail"],
        },
    )
    _write_json_asset(
        doc_004_asset_paths["agent_review"],
        {
            "doc_id": "doc-004",
            "decision": "request_changes",
            "confidence": 0.73,
            "reasons": ["Converted markdown omitted the travel request reference requirement"],
            "risk_tags": ["content-gap"],
            "suggested_actions": ["Confirm whether the reference requirement should remain in canonical markdown"],
            "publish_recommendation": "pending_review",
            "sections_requiring_review": ["Exception explanation clause"],
        },
    )
    _write_json_asset(
        doc_004_asset_paths["review_context"],
        {
            "doc_id": "doc-004",
            "request": {
                "model": "deepseek-chat",
                "prompt_excerpt": "You are reviewing a converted enterprise document for publication in a governed RAG system...",
                "canonical_excerpt": "## Travel Exception Policy\\n\\nExpenses over 500 USD require director approval...",
            },
            "response": {
                "decision": "request_changes",
                "confidence": 0.73,
                "reasons": ["Converted markdown omitted the travel request reference requirement"],
            },
            "created_at": datetime(2025, 5, 12, 11, 0, tzinfo=timezone.utc).isoformat(),
        },
    )
    _write_json_asset(
        doc_004_asset_paths["human_review"],
        {
            "doc_id": "doc-004",
            "status": "pending",
            "note": "",
            "history": [],
            "updated_at": datetime(2025, 5, 12, 11, 1, tzinfo=timezone.utc).isoformat(),
        },
    )
    _write_json_asset(
        doc_004_asset_paths["processing_record"],
        {
            "doc_id": "doc-004",
            "job_id": "ingest-004",
            "collection_id": COL_POLICY,
            "source_file_path": str(source_doc_004),
            "source_hash": "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
            "conversion_status": "success",
            "tool_chain": ["ragflow-naive"],
            "tool_versions": {},
            "parameters": {},
            "warnings": ["Human confirmation required before publication"],
            "error_message": "",
            "published_asset_paths": doc_004_asset_paths,
            "created_at": datetime(2025, 5, 12, 11, 0, tzinfo=timezone.utc).isoformat(),
        },
    )


def _seed_jobs(session):
    repo = JobRepository(session)
    if repo.get("job-001") is None:
        repo.save(JobInfo(
            job_id="job-001", job_type="index", status=JobStatus.COMPLETED,
            collection_id=COL_POLICY, doc_id="doc-001",
            created_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
            updated_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
        ))
    if repo.get("job-002") is None:
        repo.save(JobInfo(
            job_id="job-002", job_type="index", status=JobStatus.FAILED,
            collection_id=COL_HANDBOOK, doc_id="doc-003",
            created_at=datetime(2025, 2, 28, tzinfo=timezone.utc),
            updated_at=datetime(2025, 2, 28, tzinfo=timezone.utc),
            error_message="Indexing failed: OCR text extraction threshold not met on page 2",
        ))


def _seed_application_profiles(session):
    repo = ApplicationProfileRepository(session)
    if repo.get("ap-finance") is None:
        repo.save(ApplicationProfile(
            application_profile_id="ap-finance", tenant_id="default",
            name="Finance Profile",
            allowed_collections=[COL_POLICY],
            default_collections=[COL_POLICY],
        ))
    if repo.get("ap-privacy") is None:
        repo.save(ApplicationProfile(
            application_profile_id="ap-privacy", tenant_id="default",
            name="Privacy Profile",
            allowed_collections=[COL_HANDBOOK],
            default_collections=[COL_HANDBOOK],
        ))
    if repo.get("ap-cross") is None:
        repo.save(ApplicationProfile(
            application_profile_id="ap-cross", tenant_id="default",
            name="Cross-Domain Profile",
            allowed_collections=[COL_POLICY, COL_HANDBOOK],
            default_collections=[COL_POLICY],
            allow_cross_collection=True,
        ))
    if repo.get("default") is None:
        repo.save(ApplicationProfile(
            application_profile_id="default", tenant_id="default",
            name="Default Profile",
            allowed_collections=[COL_POLICY],
            default_collections=[COL_POLICY],
            default_token_budget=4096,
            metadata_policy="minimal",
        ))
    if repo.get("research") is None:
        repo.save(ApplicationProfile(
            application_profile_id="research", tenant_id="default",
            name="Research Profile",
            allowed_collections=[COL_POLICY, COL_HANDBOOK],
            default_collections=[COL_POLICY],
            allow_cross_collection=True,
            default_token_budget=8192,
            default_budget_policy="comprehensive",
            metadata_policy="full",
        ))
    if repo.get("ap-internal-assistant") is None:
        repo.save(ApplicationProfile(
            application_profile_id="ap-internal-assistant", tenant_id="default",
            name="Internal Assistant",
            allowed_collections=[COL_POLICY, COL_HANDBOOK],
            default_collections=[COL_POLICY],
            allow_cross_collection=True,
            default_token_budget=4096,
            metadata_policy="minimal",
        ))


def _seed_api_key_registry(session):
    repo = ApiKeyRegistryRepository(session)
    if repo.get("rr-agent-platform-dev") is None:
        repo.save(ApiKeyRegistryEntry(
            api_key_id="rr-agent-platform-dev",
            display_name="Agent Platform Dev",
            agent_type_id="kb_assistant",
            knowledge_scopes=[COL_POLICY, COL_HANDBOOK],
            roles=["agent"],
            debug_permission=False,
            max_context_tokens=4096,
            enabled=True,
        ))
    if repo.get("rr-agent-platform-ops") is None:
        repo.save(ApiKeyRegistryEntry(
            api_key_id="rr-agent-platform-ops",
            display_name="Agent Platform Ops",
            agent_type_id="ops_assistant",
            knowledge_scopes=[COL_POLICY, COL_HANDBOOK],
            roles=["agent", "ops"],
            debug_permission=True,
            max_context_tokens=8192,
            enabled=True,
        ))


def _seed_retrieval_profiles(session):
    repo = RetrievalProfileRepository(session)
    for collection_id in (COL_POLICY, COL_HANDBOOK):
        if repo.get("ret_default", collection_id) is None:
            repo.save(RetrievalProfile(
                profile_id="ret_default",
                collection_id=collection_id,
                profile_version=1,
                profile_hash="sha256:ret-default-seed",
                bm25_weight=0.55,
                vector_weight=0.45,
                candidate_top_k=20,
                similarity_threshold=0.2,
                rerank_enabled=True,
                rerank_model="siliconflow-rerank",
                fail_policy="fail_closed",
                expansion_policy={"adjacent_window": 1},
                pack_budget=1200,
                enabled=True,
                updated_at=datetime.now(timezone.utc),
                updated_by="seed",
            ))


def _seed_principal_profiles(session):
    repo = PrincipalProfileRepository(session)
    if repo.get("user-42") is None:
        repo.save(PrincipalProfile(
            tenant_id="default",
            user_id="user-42",
            role_ids=["researcher"],
            group_ids=["cross-functional"],
            department_ids=["finance"],
            clearance_level=4,
            attributes={"business_domains": ["finance", "legal"]},
        ))
    if repo.get("finance-analyst") is None:
        repo.save(PrincipalProfile(
            tenant_id="default",
            user_id="finance-analyst",
            role_ids=["finance_reader"],
            group_ids=[],
            department_ids=["finance"],
            clearance_level=3,
            attributes={"business_domains": ["finance"]},
        ))
    if repo.get("legal-reviewer") is None:
        repo.save(PrincipalProfile(
            tenant_id="default",
            user_id="legal-reviewer",
            role_ids=["legal_reviewer"],
            group_ids=[],
            department_ids=["legal"],
            clearance_level=5,
            attributes={"business_domains": ["legal"]},
        ))


def _seed_document_policies(session):
    repo = DocumentPolicyRepository(session)
    if repo.get("policy-doc-001-allow-finance") is None:
        repo.save(DocumentPolicy(
            policy_id="policy-doc-001-allow-finance",
            tenant_id="default",
            collection_id=COL_POLICY,
            doc_id="doc-001",
            effect="allow",
            subjects=[PolicySubject(subject_type="tenant", subject_id="default")],
            conditions=[],
            priority=100,
            policy_version="v1",
        ))
    if repo.get("policy-doc-002-deny-all") is None:
        repo.save(DocumentPolicy(
            policy_id="policy-doc-002-deny-all",
            tenant_id="default",
            collection_id=COL_POLICY,
            doc_id="doc-002",
            effect="deny",
            subjects=[PolicySubject(subject_type="tenant", subject_id="default")],
            conditions=[],
            priority=10,
            policy_version="v1",
        ))
    if repo.get("policy-doc-003-allow-legal") is None:
        repo.save(DocumentPolicy(
            policy_id="policy-doc-003-allow-legal",
            tenant_id="default",
            collection_id=COL_HANDBOOK,
            doc_id="doc-003",
            effect="allow",
            subjects=[PolicySubject(subject_type="role", subject_id="legal_reviewer")],
            conditions=[
                PolicyCondition(field="clearance_level", operator="gte", value=5),
            ],
            priority=100,
            policy_version="v1",
        ))
    if repo.get("policy-doc-004-allow-research") is None:
        repo.save(DocumentPolicy(
            policy_id="policy-doc-004-allow-research",
            tenant_id="default",
            collection_id=COL_POLICY,
            doc_id="doc-004",
            effect="allow",
            subjects=[PolicySubject(subject_type="role", subject_id="researcher")],
            conditions=[
                PolicyCondition(field="clearance_level", operator="gte", value=4),
            ],
            priority=120,
            policy_version="v1",
        ))


def _seed_ingestion(session):
    repo = IngestionRepository(session)
    if repo.get("ingest-001") is None:
        now = datetime(2025, 5, 10, 9, 30, tzinfo=timezone.utc)
        report = ConversionReport(
            report_id="rpt-001", job_id="ingest-001",
            source_file_path="datasets/raw/finance/",
            conversion_status=ConversionStatus.SUCCESS,
            total_files=3, successful=2, failed=1, unsupported=0,
            warnings=["PDF image extraction skipped on page 4 of appendix"],
            details=[
                ConversionResult(
                    source_file_path="datasets/raw/finance/2025-q1-report.docx",
                    conversion_status=ConversionStatus.SUCCESS,
                    doc_id="doc-001",
                    canonical_asset_path="E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-001/canonical.md",
                    canonical_md="## Q1 2025 Financial Report\n\nRevenue: $12.4M (up 8% YoY)\n\n### Highlights\n- Net income grew 12%\n- Operating margin expanded to 24%\n\nFull report follows...",
                    metadata={"pages": 14, "format": "docx"},
                ),
                ConversionResult(
                    source_file_path="datasets/raw/finance/2025-q1-appendix.pdf",
                    conversion_status=ConversionStatus.FAILED,
                    canonical_md="",
                    error_message="PDF text extraction failed: encrypted or scanned image-only pages",
                    warnings=["Image extraction skipped on page 4"],
                    metadata={"pages": 22, "format": "pdf"},
                ),
                ConversionResult(
                    source_file_path="datasets/raw/finance/2025-q1-audit-letter.docx",
                    conversion_status=ConversionStatus.SUCCESS,
                    doc_id="doc-002",
                    canonical_asset_path="E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-002/canonical.md",
                    canonical_md="## Independent Auditor's Letter\n\nWe have audited the financial statements of Example Corp for Q1 2025.\n\nOpinion: Unqualified.",
                    metadata={"pages": 3, "format": "docx"},
                ),
            ],
            created_at=now,
        )
        repo.save(IngestionJob(
            job_id="ingest-001", job_type="ingestion",
            status=JobStatus.COMPLETED, collection_id=COL_POLICY,
            source_files=[
                "datasets/raw/finance/2025-q1-report.docx",
                "datasets/raw/finance/2025-q1-appendix.pdf",
                "datasets/raw/finance/2025-q1-audit-letter.docx",
            ],
            conversion_report=report,
            report_asset_path="E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/ingest-001/conversion_report.json",
            created_at=now, updated_at=datetime(2025, 5, 10, 9, 35, tzinfo=timezone.utc),
        ))
    if repo.get("ingest-002") is None:
        now = datetime(2025, 5, 11, 14, 0, tzinfo=timezone.utc)
        report = ConversionReport(
            report_id="rpt-002", job_id="ingest-002",
            source_file_path="datasets/raw/legal/contract-v3-scanned.pdf",
            conversion_status=ConversionStatus.FAILED,
            total_files=1, successful=0, failed=1, unsupported=0,
            error_message="All files failed conversion",
            details=[
                ConversionResult(
                    source_file_path="datasets/raw/legal/contract-v3-scanned.pdf",
                    conversion_status=ConversionStatus.FAILED,
                    doc_id="doc-003",
                    canonical_asset_path="E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/doc-003/canonical.md",
                    canonical_md="",
                    error_message="Scanned image PDF with no OCR layer — requires manual OCR preprocessing",
                    metadata={"pages": 45, "format": "pdf"},
                ),
            ],
            created_at=now,
        )
        repo.save(IngestionJob(
            job_id="ingest-002", job_type="ingestion",
            status=JobStatus.FAILED, collection_id=COL_HANDBOOK,
            source_files=["datasets/raw/legal/contract-v3-scanned.pdf"],
            conversion_report=report,
            report_asset_path="E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/ingest-002/conversion_report.json",
            created_at=now, updated_at=datetime(2025, 5, 11, 14, 2, tzinfo=timezone.utc),
            error_message="Ingestion failed: no convertible files in batch",
        ))
    if repo.get("ingest-003") is None:
        now = datetime(2025, 5, 15, 8, 0, tzinfo=timezone.utc)
        repo.save(IngestionJob(
            job_id="ingest-003", job_type="ingestion",
            status=JobStatus.PENDING, collection_id=COL_POLICY,
            source_files=[
                "datasets/raw/finance/2025-q2-forecast.xlsx",
                "datasets/raw/finance/2025-q2-notes.md",
            ],
            created_at=now, updated_at=now,
        ))
    if repo.get("ingest-004") is None:
        now = datetime(2025, 5, 12, 11, 0, tzinfo=timezone.utc)
        report = ConversionReport(
            report_id="rpt-004", job_id="ingest-004",
            source_file_path="datasets/raw/finance/manual-review-policy.md",
            conversion_status=ConversionStatus.SUCCESS,
            total_files=1, successful=1, failed=0, unsupported=0,
            warnings=["Human confirmation required before publication"],
            details=[
                ConversionResult(
                    source_file_path="E:/AI/My-Project/Reality-RAG/datasets/raw/finance/manual-review-policy.md",
                    conversion_status=ConversionStatus.SUCCESS,
                    doc_id="doc-004",
                    canonical_asset_path="E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/canonical.md",
                    canonical_md="## Travel Exception Policy\n\nExpenses over 500 USD require director approval.\n\nA written exception explanation is required before reimbursement.\n",
                    metadata={"pages": 1, "format": "md"},
                ),
            ],
            created_at=now,
        )
        repo.save(IngestionJob(
            job_id="ingest-004", job_type="ingestion",
            status=JobStatus.COMPLETED, collection_id=COL_POLICY,
            source_files=["E:/AI/My-Project/Reality-RAG/datasets/raw/finance/manual-review-policy.md"],
            conversion_report=report,
            report_asset_path="E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/ingest-004/conversion_report.json",
            created_at=now, updated_at=now,
        ))

    ingest_001_created_at = datetime(2025, 5, 10, 9, 30, tzinfo=timezone.utc)
    ingest_001_report_asset_path = "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/ingest-001/conversion_report.json"
    _write_json_asset(
        ingest_001_report_asset_path,
        {
            "report_id": "rpt-001",
            "job_id": "ingest-001",
            "source_file_path": "datasets/raw/finance/",
            "conversion_status": "success",
            "total_files": 3,
            "successful": 2,
            "failed": 1,
            "unsupported": 0,
            "error_message": "",
            "warnings": ["PDF image extraction skipped on page 4 of appendix"],
            "details": [
                {
                    "source_file_path": "datasets/raw/finance/2025-q1-report.docx",
                    "conversion_status": "success",
                    "doc_id": "doc-001",
                    "canonical_asset_path": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-001/canonical.md",
                    "canonical_md": "## Q1 2025 Financial Report\n\nRevenue: $12.4M (up 8% YoY)\n\n### Highlights\n- Net income grew 12%\n- Operating margin expanded to 24%\n\nFull report follows...",
                    "error_message": "",
                    "warnings": [],
                    "metadata": {"pages": 14, "format": "docx"},
                },
                {
                    "source_file_path": "datasets/raw/finance/2025-q1-appendix.pdf",
                    "conversion_status": "failed",
                    "doc_id": "",
                    "canonical_asset_path": "",
                    "canonical_md": "",
                    "error_message": "PDF text extraction failed: encrypted or scanned image-only pages",
                    "warnings": ["Image extraction skipped on page 4"],
                    "metadata": {"pages": 22, "format": "pdf"},
                },
                {
                    "source_file_path": "datasets/raw/finance/2025-q1-audit-letter.docx",
                    "conversion_status": "success",
                    "doc_id": "doc-002",
                    "canonical_asset_path": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-002/canonical.md",
                    "canonical_md": "## Independent Auditor's Letter\n\nWe have audited the financial statements of Example Corp for Q1 2025.\n\nOpinion: Unqualified.",
                    "error_message": "",
                    "warnings": [],
                    "metadata": {"pages": 3, "format": "docx"},
                },
            ],
            "created_at": ingest_001_created_at.isoformat(),
        },
    )

    ingest_002_created_at = datetime(2025, 5, 11, 14, 0, tzinfo=timezone.utc)
    ingest_002_report_asset_path = "E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/ingest-002/conversion_report.json"
    _write_json_asset(
        ingest_002_report_asset_path,
        {
            "report_id": "rpt-002",
            "job_id": "ingest-002",
            "source_file_path": "datasets/raw/legal/contract-v3-scanned.pdf",
            "conversion_status": "failed",
            "total_files": 1,
            "successful": 0,
            "failed": 1,
            "unsupported": 0,
            "error_message": "All files failed conversion",
            "warnings": [],
            "details": [
                {
                    "source_file_path": "datasets/raw/legal/contract-v3-scanned.pdf",
                    "conversion_status": "failed",
                    "doc_id": "doc-003",
                    "canonical_asset_path": "E:/AI/My-Project/Reality-RAG/.sidecar/col_handbook/doc-003/canonical.md",
                    "canonical_md": "",
                    "error_message": "Scanned image PDF with no OCR layer — requires manual OCR preprocessing",
                    "warnings": [],
                    "metadata": {"pages": 45, "format": "pdf"},
                }
            ],
            "created_at": ingest_002_created_at.isoformat(),
        },
    )

    ingest_004_created_at = datetime(2025, 5, 12, 11, 0, tzinfo=timezone.utc)
    ingest_004_report_asset_path = "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/ingest-004/conversion_report.json"
    _write_json_asset(
        ingest_004_report_asset_path,
        {
            "report_id": "rpt-004",
            "job_id": "ingest-004",
            "source_file_path": "datasets/raw/finance/manual-review-policy.md",
            "conversion_status": "success",
            "total_files": 1,
            "successful": 1,
            "failed": 0,
            "unsupported": 0,
            "error_message": "",
            "warnings": ["Human confirmation required before publication"],
            "details": [
                {
                    "source_file_path": "E:/AI/My-Project/Reality-RAG/datasets/raw/finance/manual-review-policy.md",
                    "conversion_status": "success",
                    "doc_id": "doc-004",
                    "canonical_asset_path": "E:/AI/My-Project/Reality-RAG/.sidecar/col_policy/doc-004/canonical.md",
                    "canonical_md": "## Travel Exception Policy\n\nExpenses over 500 USD require director approval.\n\nA written exception explanation is required before reimbursement.\n",
                    "error_message": "",
                    "warnings": ["Human confirmation required before publication"],
                    "metadata": {"pages": 1, "format": "md"},
                }
            ],
            "created_at": ingest_004_created_at.isoformat(),
        },
    )


def _seed_index_registry(session):
    repo = IndexRegistryRepository(session)
    if repo.get(COL_POLICY) is None:
        repo.save(IndexVersionEntry(
            collection_id=COL_POLICY, index_version="idxv_col_policy_seed_v2",
            status=IndexRegistryStatus.INDEXED,
            created_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
        ))
    if repo.get(COL_HANDBOOK) is None:
        repo.save(IndexVersionEntry(
            collection_id=COL_HANDBOOK, index_version="idxv_col_handbook_seed_v1",
            status=IndexRegistryStatus.INDEXED,
            created_at=datetime(2025, 2, 28, tzinfo=timezone.utc),
        ))


if __name__ == "__main__":
    seed()
    print("Seed complete.")
