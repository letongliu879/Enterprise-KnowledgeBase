"""Roundtrip tests: JSON → Pydantic → JSON for all core contract models."""

import json
from pathlib import Path

import pytest

from reality_rag_contracts import (
    AccessRetrieveRequest,
    AccessRetrieveResponse,
    ApiKeyProjection,
    ApiKeyProjectionSync,
    ApplicationProfile,
    CanonicalMetadata,
    Collection,
    CWIndexRequest,
    CWIndexResponse,
    CWSearchRequest,
    CWSearchResponse,
    DocumentDetail,
    DocumentSummary,
    EvidenceItem,
    HealthResponse,
    IngestionJob,
    IndexAssetBundle,
    IndexJobRequest,
    IndexJobResult,
    IndexSwitchRequest,
    IndexSwitchResult,
    JobInfo,
    KnowledgeContext,
    OpenSearchIndexRecord,
    ParserProfileValidateRequest,
    ParserProfileValidateResponse,
    PermissionContext,
    ProcessingRecord,
    QdrantPointRecord,
    PublishStatus,
    QualityReport,
    RetrievalMetadata,
    RetrievalProfileValidateRequest,
    RetrievalProfileValidateResponse,
    RetrievalRequest,
    RetrievalResponse,
    Tenant,
)

EXAMPLES_DIR = Path(__file__).parent.parent / "src" / "reality_rag_contracts" / "examples"


def _load_json(name: str) -> dict:
    path = EXAMPLES_DIR / name
    assert path.exists(), f"Missing example fixture: {path}"
    return json.loads(path.read_text())


def _roundtrip(cls, data: dict) -> dict:
    """JSON → model → JSON and back, returning the final dict."""
    instance = cls.model_validate(data)
    json_str = instance.model_dump_json()
    re_parsed = cls.model_validate_json(json_str)
    return json.loads(re_parsed.model_dump_json())


# ── Individual model roundtrips ───────────────────────────────────────


class TestTenant:
    def test_roundtrip(self):
        data = _load_json("tenant.json")
        result = _roundtrip(Tenant, data)
        assert result["tenant_id"] == data["tenant_id"]


class TestCollection:
    def test_roundtrip(self):
        data = _load_json("collection.json")
        result = _roundtrip(Collection, data)
        assert result["collection_id"] == data["collection_id"]
        assert result["tenant_id"] == data["tenant_id"]


class TestApplicationProfile:
    def test_roundtrip(self):
        data = _load_json("application_profile.json")
        result = _roundtrip(ApplicationProfile, data)
        assert result["application_profile_id"] == data["application_profile_id"]
        assert result["allowed_collections"] == data["allowed_collections"]


class TestCanonicalMetadata:
    def test_roundtrip(self):
        data = _load_json("canonical_metadata.json")
        result = _roundtrip(CanonicalMetadata, data)
        assert result["doc_id"] == data["doc_id"]
        assert result["publish_status"] == "published"
        assert result["index_status"] == "indexed"

    def test_asset_paths_and_processing_summary_roundtrip(self):
        data = _load_json("canonical_metadata.json")
        data["processing_summary"] = "converted via markitdown"
        data["asset_paths"] = {"canonical_md": "col-finance-policy/doc-travel-policy-v3/canonical.md"}
        result = _roundtrip(CanonicalMetadata, data)
        assert result["processing_summary"] == "converted via markitdown"
        assert result["asset_paths"]["canonical_md"] == "col-finance-policy/doc-travel-policy-v3/canonical.md"


class TestRetrievalRequest:
    def test_roundtrip(self):
        data = _load_json("retrieval_request.json")
        result = _roundtrip(RetrievalRequest, data)
        assert result["query"] == data["query"]
        assert "permission_context" in result
        assert "permission_scope_hash" in result["permission_context"]
        assert len(result["resolved_collection_ids"]) == 2

    def test_permission_context_nested(self):
        data = _load_json("retrieval_request.json")
        req = RetrievalRequest.model_validate(data)
        assert req.permission_context.permission_scope_hash == "sha256:abc123def456"


class TestKnowledgeContext:
    def test_roundtrip(self):
        data = _load_json("knowledge_context.json")
        result = _roundtrip(KnowledgeContext, data)
        assert len(result["evidence_items"]) == 2
        assert result["retrieval_metadata"]["total_evidence_count"] == 2
        assert result["retrieval_metadata"]["cache_hit"] is False

    def test_evidence_items_have_required_fields(self):
        data = _load_json("knowledge_context.json")
        kc = KnowledgeContext.model_validate(data)
        for item in kc.evidence_items:
            assert item.evidence_id
            assert item.doc_id
            assert item.collection_id
            assert item.canonical_source
            assert item.content
            assert 0.0 <= item.score <= 1.0


class TestCWSearchRequest:
    def test_roundtrip(self):
        data = _load_json("cw_search_request.json")
        result = _roundtrip(CWSearchRequest, data)
        assert result["collection_id"] == "col-finance-policy"
        assert result["index_version"] == "v1"


class TestCWIndexRequest:
    def test_roundtrip(self):
        data = _load_json("cw_index_request.json")
        result = _roundtrip(CWIndexRequest, data)
        assert result["collection_id"] == "col-finance-policy"
        assert len(result["canonical_asset_paths"]) == 2


class TestAccessRetrieveRequest:
    def test_roundtrip(self):
        data = _load_json("access_retrieve_request.json")
        result = _roundtrip(AccessRetrieveRequest, data)
        assert result["query"] == data["query"]

    def test_defaults(self):
        req = AccessRetrieveRequest(
            query="test",
            application_profile_id="ap-1",
        )
        assert req.tenant_id == "default"
        assert req.max_results == 10
        assert req.token_budget == 4096
        assert req.budget_policy == "balanced"


# ── Composite roundtrip: full retrieve chain ──────────────────────────


class TestFullRetrieveChain:
    """Simulate the complete retrieval chain contract."""

    def test_access_request_to_response_chain(self):
        # access-api receives this
        access_data = _load_json("access_retrieve_request.json")
        access_req = AccessRetrieveRequest.model_validate(access_data)

        # access-api translates to internal RetrievalRequest
        internal_req = RetrievalRequest(
            query=access_req.query,
            tenant_id=access_req.tenant_id,
            application_profile_id=access_req.application_profile_id,
            permission_context=PermissionContext(
                tenant_id=access_req.tenant_id,
                user_id=access_req.user_id,
                application_profile_id=access_req.application_profile_id,
                role_ids=[],
                group_ids=[],
                department_ids=[],
                clearance_level=0,
                attributes={},
                collection_scope=["col-finance-policy"],
                permission_scope_hash="sha256:hash123",
                policy_snapshot_version="v1",
            ),
            resolved_collection_ids=["col-finance-policy"],
            token_budget=access_req.token_budget,
            max_results=access_req.max_results,
            output_mode=access_req.output_mode,
        )

        # retrieval-service returns KnowledgeContext
        kc_data = _load_json("knowledge_context.json")
        kc = KnowledgeContext.model_validate(kc_data)

        # contextweaver-adapter returns CWSearchResponse
        cw_response = CWSearchResponse(evidence_items=kc.evidence_items)

        # access-api wraps in AccessRetrieveResponse
        response = AccessRetrieveResponse(
            knowledge_context=KnowledgeContext(
                evidence_items=cw_response.evidence_items,
                assembled_context=kc.assembled_context,
                retrieval_metadata=kc.retrieval_metadata,
            )
        )

        # Final output is valid JSON
        output = response.model_dump_json()
        parsed = json.loads(output)
        assert "knowledge_context" in parsed
        assert len(parsed["knowledge_context"]["evidence_items"]) == 2


# ── Health ────────────────────────────────────────────────────────────


class TestHealthResponse:
    def test_roundtrip(self):
        h = HealthResponse(service="access-api", version="0.1.0")
        data = _roundtrip(HealthResponse, h.model_dump())
        assert data["status"] == "ok"
        assert data["service"] == "access-api"


class TestIngestionJob:
    def test_roundtrip_with_report_asset_path(self):
        job = IngestionJob(
            job_id="ingest-1",
            job_type="ingestion",
            status="completed",
            collection_id="col-finance-policy",
            source_files=["/tmp/source.txt"],
            report_asset_path="col-finance-policy/ingest-1/conversion_report.json",
        )
        data = _roundtrip(IngestionJob, job.model_dump(mode="json"))
        assert data["report_asset_path"] == "col-finance-policy/ingest-1/conversion_report.json"


class TestProcessingRecord:
    def test_roundtrip(self):
        record = ProcessingRecord(
            doc_id="doc-travel-policy-v3",
            job_id="ingest-1",
            collection_id="col-finance-policy",
            source_file_path="/tmp/source.txt",
            source_hash="sha256:abc",
            conversion_status="success",
            tool_chain=["markitdown"],
            published_asset_paths={"canonical_md": "col-finance-policy/doc-travel-policy-v3/canonical.md"},
        )
        data = _roundtrip(ProcessingRecord, record.model_dump(mode="json"))
        assert data["job_id"] == "ingest-1"
        assert data["published_asset_paths"]["canonical_md"] == "col-finance-policy/doc-travel-policy-v3/canonical.md"


class TestIndexAssetBundle:
    def test_roundtrip(self):
        bundle = IndexAssetBundle(
            doc_id="doc-1",
            collection_id="col-1",
            index_version="v1",
            canonical_source="col-1/doc-1/canonical.md",
            chunks=[
                {
                    "chunk_id": "doc-1-chunk-0000",
                    "doc_id": "doc-1",
                    "collection_id": "col-1",
                    "chunk_index": 0,
                    "canonical_source": "col-1/doc-1/canonical.md",
                    "heading": "Purpose",
                    "content": "Travel reimbursement policy applies to employees.",
                    "token_estimate": 9,
                    "metadata": {"index_version": "v1"},
                }
            ],
            opensearch_records=[
                OpenSearchIndexRecord(
                    index_name="reality-rag-col-1-v1",
                    document_id="doc-1-chunk-0000",
                    body={"doc_id": "doc-1", "content": "Travel reimbursement policy applies to employees."},
                )
            ],
            qdrant_points=[
                QdrantPointRecord(
                    collection_name="reality-rag-col-1-v1",
                    point_id="doc-1-chunk-0000",
                    payload={"doc_id": "doc-1", "content": "Travel reimbursement policy applies to employees."},
                )
            ],
        )
        data = _roundtrip(IndexAssetBundle, bundle.model_dump(mode="json"))
        assert data["doc_id"] == "doc-1"
        assert data["chunks"][0]["chunk_id"] == "doc-1-chunk-0000"
        assert data["opensearch_records"][0]["index_name"] == "reality-rag-col-1-v1"
        assert data["qdrant_points"][0]["collection_name"] == "reality-rag-col-1-v1"


class TestIndexJobContracts:
    def test_index_job_request_roundtrip(self):
        request = IndexJobRequest(
            job_id="ingest-123",
            collection_id="col-1",
            index_version="col-1-v3",
            options={"force": True},
        )
        data = _roundtrip(IndexJobRequest, request.model_dump(mode="json"))
        assert data["job_id"] == "ingest-123"
        assert data["index_version"] == "col-1-v3"

    def test_index_job_result_roundtrip(self):
        result = IndexJobResult(
            job_id="index-ingest-123-col-1-v3",
            collection_id="col-1",
            index_version="col-1-v3",
            status="completed",
            documents_indexed=2,
            chunks_indexed=8,
            backend_mode="hybrid",
        )
        data = _roundtrip(IndexJobResult, result.model_dump(mode="json"))
        assert data["status"] == "completed"
        assert data["documents_indexed"] == 2

    def test_index_switch_contracts_roundtrip(self):
        request = IndexSwitchRequest(collection_id="col-1", index_version="col-1-v2")
        request_data = _roundtrip(IndexSwitchRequest, request.model_dump(mode="json"))
        assert request_data["collection_id"] == "col-1"
        assert request_data["index_version"] == "col-1-v2"

        result = IndexSwitchResult(
            collection_id="col-1",
            active_index_version="col-1-v2",
            previous_index_version="col-1-v1",
            target_index_version=None,
            status="indexed",
        )
        result_data = _roundtrip(IndexSwitchResult, result.model_dump(mode="json"))
        assert result_data["active_index_version"] == "col-1-v2"


# ── JobInfo ───────────────────────────────────────────────────────────


class TestJobInfo:
    def test_roundtrip(self):
        job = JobInfo(
            job_id="job-001",
            job_type="index",
            status="running",
            collection_id="col-1",
        )
        data = _roundtrip(JobInfo, job.model_dump())
        assert data["job_id"] == "job-001"
        assert data["status"] == "running"


class TestApiKeyProjection:
    def test_roundtrip(self):
        projection = ApiKeyProjection(
            api_key_id="key_agent_platform_dev",
            tenant_id="tnt_default",
            agent_type_id="kb_assistant",
            knowledge_scopes=["col_policy", "col_handbook"],
            roles=["agent", "developer"],
            debug_permission=True,
            token_budget_limit=4096,
            state="active",
            projection_version=3,
            last_updated_at="2026-05-27T12:00:00Z",
        )
        data = _roundtrip(ApiKeyProjection, projection.model_dump(mode="json"))
        assert data["api_key_id"] == "key_agent_platform_dev"
        assert data["token_budget_limit"] == 4096
        assert data["state"] == "active"
        assert data["projection_version"] == 3
        assert "key_hash" not in data

    def test_uses_token_budget_limit_not_max_context_tokens(self):
        projection = ApiKeyProjection(
            api_key_id="key-1",
            tenant_id="tnt_default",
            token_budget_limit=2048,
        )
        dumped = json.loads(projection.model_dump_json())
        assert "token_budget_limit" in dumped
        assert "max_context_tokens" not in dumped


class TestApiKeyProjectionSync:
    def test_roundtrip(self):
        sync = ApiKeyProjectionSync(
            command_id="cmd_sync_key_001",
            trace_id="trc_sync_001",
            idempotency_key="idem_key_agent_platform_dev_v3",
            actor="admin_service",
            tenant_id="tnt_default",
            target_type="api_key_projection",
            target_id="key_agent_platform_dev",
            payload=ApiKeyProjection(
                api_key_id="key_agent_platform_dev",
                tenant_id="tnt_default",
                agent_type_id="kb_assistant",
                knowledge_scopes=["col_policy"],
                roles=["agent"],
                debug_permission=False,
                token_budget_limit=4096,
                state="active",
                projection_version=1,
                last_updated_at="2026-05-27T12:00:00Z",
            ),
        )
        data = _roundtrip(ApiKeyProjectionSync, sync.model_dump(mode="json"))
        assert data["command_id"] == "cmd_sync_key_001"
        assert data["idempotency_key"] == "idem_key_agent_platform_dev_v3"
        assert data["payload"]["api_key_id"] == "key_agent_platform_dev"
        assert data["payload"]["token_budget_limit"] == 4096


# ── Profile Validate Contracts ──────────────────────────────────────────


class TestParserProfileValidateRequest:
    def test_roundtrip(self):
        req = ParserProfileValidateRequest(
            parser_profile_id="pp-naive-v2",
            parser_id="naive",
            parser_config={"chunk_token_num": 128, "delimiter": "\\n"},
            chunk_profile_id="cp-default",
            tenant_id="tnt_default",
            collection_id="col-finance-policy",
            version=3,
        )
        data = _roundtrip(ParserProfileValidateRequest, req.model_dump(mode="json"))
        assert data["parser_profile_id"] == "pp-naive-v2"
        assert data["parser_id"] == "naive"
        assert data["parser_config"]["chunk_token_num"] == 128
        assert data["tenant_id"] == "tnt_default"
        assert data["version"] == 3

    def test_optional_fields_omitted(self):
        req = ParserProfileValidateRequest(
            parser_profile_id="pp-1",
            parser_id="qa",
            parser_config={},
            tenant_id="tnt_default",
        )
        dumped = json.loads(req.model_dump_json())
        assert "chunk_profile_id" not in dumped or dumped["chunk_profile_id"] is None
        assert "collection_id" not in dumped or dumped["collection_id"] is None
        assert "version" not in dumped or dumped["version"] is None


class TestParserProfileValidateResponse:
    def test_valid_roundtrip(self):
        resp = ParserProfileValidateResponse(
            valid=True,
            canonical_config={"chunk_token_num": 128},
            profile_hash="sha256:abc123",
            warnings=[],
            errors=[],
            validator_version="indexing-v0.1.0",
        )
        data = _roundtrip(ParserProfileValidateResponse, resp.model_dump(mode="json"))
        assert data["valid"] is True
        assert data["canonical_config"]["chunk_token_num"] == 128
        assert data["profile_hash"] == "sha256:abc123"
        assert data["runtime_owner"] == "indexing"
        assert data["validator_version"] == "indexing-v0.1.0"

    def test_invalid_with_errors_roundtrip(self):
        resp = ParserProfileValidateResponse(
            valid=False,
            profile_hash="sha256:000000",
            warnings=["chunk_token_num is below recommended minimum"],
            errors=[
                {"code": "INVALID_PARSER_ID", "message": "Parser not recognized"},
            ],
            validator_version="indexing-v0.1.0",
        )
        data = _roundtrip(ParserProfileValidateResponse, resp.model_dump(mode="json"))
        assert data["valid"] is False
        assert "canonical_config" not in data or data["canonical_config"] is None
        assert len(data["errors"]) == 1
        assert data["errors"][0]["code"] == "INVALID_PARSER_ID"


class TestRetrievalProfileValidateRequest:
    def test_roundtrip(self):
        req = RetrievalProfileValidateRequest(
            retrieval_profile_id="rp-hybrid-v1",
            profile_config={"bm25_weight": 0.3, "vector_weight": 0.7},
            tenant_id="tnt_default",
            collection_id="col-finance-policy",
            version="v2",
        )
        data = _roundtrip(RetrievalProfileValidateRequest, req.model_dump(mode="json"))
        assert data["retrieval_profile_id"] == "rp-hybrid-v1"
        assert data["profile_config"]["bm25_weight"] == 0.3
        assert data["tenant_id"] == "tnt_default"
        assert data["version"] == "v2"

    def test_optional_fields_omitted(self):
        req = RetrievalProfileValidateRequest(
            retrieval_profile_id="rp-1",
            profile_config={},
            tenant_id="tnt_default",
        )
        dumped = json.loads(req.model_dump_json())
        assert "collection_id" not in dumped or dumped["collection_id"] is None
        assert "version" not in dumped or dumped["version"] is None


class TestRetrievalProfileValidateResponse:
    def test_valid_roundtrip(self):
        resp = RetrievalProfileValidateResponse(
            valid=True,
            canonical_config={"bm25_weight": 0.3},
            profile_hash="sha256:def789",
            warnings=[],
            errors=[],
            validator_version="retrieval-v0.1.0",
        )
        data = _roundtrip(RetrievalProfileValidateResponse, resp.model_dump(mode="json"))
        assert data["valid"] is True
        assert data["canonical_config"]["bm25_weight"] == 0.3
        assert data["profile_hash"] == "sha256:def789"
        assert data["runtime_owner"] == "retrieval"
        assert data["validator_version"] == "retrieval-v0.1.0"

    def test_invalid_with_errors_roundtrip(self):
        resp = RetrievalProfileValidateResponse(
            valid=False,
            profile_hash="sha256:000000",
            warnings=["similarity_threshold above 0.9 may reduce recall"],
            errors=[
                {"code": "INVALID_RERANK_MODEL", "message": "Model not available"},
            ],
            validator_version="retrieval-v0.1.0",
        )
        data = _roundtrip(RetrievalProfileValidateResponse, resp.model_dump(mode="json"))
        assert data["valid"] is False
        assert "canonical_config" not in data or data["canonical_config"] is None
        assert len(data["errors"]) == 1
        assert data["errors"][0]["code"] == "INVALID_RERANK_MODEL"
