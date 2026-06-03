"""Schema validation tests: verify examples pass JSON Schema validation.

These tests ensure that contracts/examples/ payloads match their declared
schemas in contracts/schemas/.  They also enforce a schema-drift guard:
if the canonical wire field names are reverted, these tests fail.
"""

import json
from pathlib import Path
from urllib.parse import urljoin

import jsonschema
import pytest

CONTRACTS_DIR = Path(__file__).parent.parent.parent.parent / "contracts"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
EXAMPLES_DIR = CONTRACTS_DIR / "examples"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_resolver() -> jsonschema.RefResolver:
    """Build a RefResolver that preloads all local schemas.

    The schemas use ``$id`` values like
    ``https://reality-rag/contracts/schemas/common.schema.json`` which are
    not real URLs.  We map each such ``$id`` to the local file content so
    that ``$ref`` resolution works without network access.
    """
    store: dict[str, dict] = {}
    for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
        schema = _load_json(schema_file)
        # Map the $id to the schema content
        if "$id" in schema:
            store[schema["$id"]] = schema
        # Also map the file:// URI
        store[schema_file.resolve().as_uri()] = schema
    return jsonschema.RefResolver(
        base_uri=SCHEMAS_DIR.resolve().as_uri() + "/",
        store=store,
        referrer=None,
    )


def _load_schema(schema_file: str) -> dict:
    return _load_json(SCHEMAS_DIR / schema_file)


# ── RetrieveRequest example validates against schema ────────────────────


class TestRetrieveRequestSchema:
    def test_example_validates(self):
        schema = _load_schema("RetrieveRequest.schema.json")
        example = _load_json(EXAMPLES_DIR / "retrieve_request.multi_collection.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_uses_query_not_query_text(self):
        schema = _load_schema("RetrieveRequest.schema.json")
        assert "query" in schema["properties"], "Schema must define 'query' field"
        assert "query_text" not in schema["properties"], "Schema must NOT define 'query_text'"

    def test_uses_token_budget_not_max_context_tokens(self):
        schema = _load_schema("RetrieveRequest.schema.json")
        assert "token_budget" in schema["properties"], "Schema must define 'token_budget' field"
        assert "max_context_tokens" not in schema["properties"], "Schema must NOT define 'max_context_tokens'"


# ── KnowledgeContext example validates against schema ────────────────────


class TestKnowledgeContextSchema:
    def test_example_validates(self):
        schema = _load_schema("KnowledgeContext.schema.json")
        example = _load_json(EXAMPLES_DIR / "knowledge_context.min.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_uses_evidence_items_not_result_chunks(self):
        schema = _load_schema("KnowledgeContext.schema.json")
        assert "evidence_items" in schema["properties"], "Schema must define 'evidence_items'"
        assert "result_chunks" not in schema["properties"], "Schema must NOT define 'result_chunks'"

    def test_evidence_item_uses_doc_id_not_final_doc_id(self):
        schema = _load_schema("KnowledgeContext.schema.json")
        item_props = schema["properties"]["evidence_items"]["items"]["properties"]
        assert "doc_id" in item_props, "Evidence item must define 'doc_id'"
        assert "final_doc_id" not in item_props, "Evidence item must NOT define 'final_doc_id'"

    def test_evidence_item_uses_evidence_id_not_chunk_id(self):
        schema = _load_schema("KnowledgeContext.schema.json")
        item_props = schema["properties"]["evidence_items"]["items"]["properties"]
        assert "evidence_id" in item_props, "Evidence item must define 'evidence_id'"
        assert "chunk_id" not in item_props, "Evidence item must NOT define 'chunk_id'"

    def test_evidence_item_uses_content_not_display_text(self):
        schema = _load_schema("KnowledgeContext.schema.json")
        item_props = schema["properties"]["evidence_items"]["items"]["properties"]
        assert "content" in item_props, "Evidence item must define 'content'"
        assert "display_text" not in item_props, "Evidence item must NOT define 'display_text'"


# ── CollectionRetrievalPlan example validates against schema ─────────────


class TestCollectionRetrievalPlanSchema:
    def test_example_validates(self):
        schema = _load_schema("CollectionRetrievalPlan.schema.json")
        example = _load_json(EXAMPLES_DIR / "collection_retrieval_plan.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_tenant_id_is_required(self):
        schema = _load_schema("CollectionRetrievalPlan.schema.json")
        assert "tenant_id" in schema["required"], "tenant_id must be required"
        assert "tenant_id" in schema["properties"], "tenant_id must be defined in properties"


# ── Schema drift guard ──────────────────────────────────────────────────


class TestSchemaDriftGuard:
    """Ensure the old field names do NOT reappear in schemas."""

    def test_retrieve_request_has_no_old_names(self):
        schema_text = (SCHEMAS_DIR / "RetrieveRequest.schema.json").read_text(encoding="utf-8")
        assert '"query_text"' not in schema_text, "RetrieveRequest must not contain 'query_text'"
        assert '"max_context_tokens"' not in schema_text, "RetrieveRequest must not contain 'max_context_tokens'"

    def test_knowledge_context_has_no_old_names(self):
        schema_text = (SCHEMAS_DIR / "KnowledgeContext.schema.json").read_text(encoding="utf-8")
        assert '"result_chunks"' not in schema_text, "KnowledgeContext must not contain 'result_chunks'"
        assert '"display_text"' not in schema_text, "KnowledgeContext must not contain 'display_text'"

    def test_retrieve_request_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "retrieve_request.multi_collection.json").read_text(encoding="utf-8")
        assert '"query_text"' not in example_text
        assert '"max_context_tokens"' not in example_text

    def test_knowledge_context_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "knowledge_context.min.json").read_text(encoding="utf-8")
        assert '"result_chunks"' not in example_text
        assert '"display_text"' not in example_text


# ── WorkbenchUploadSession example validates against schema ──────────────


class TestWorkbenchUploadSessionSchema:
    def test_example_validates(self):
        schema = _load_schema("WorkbenchUploadSession.schema.json")
        example = _load_json(EXAMPLES_DIR / "workbench_upload_session.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_has_status_enum(self):
        schema = _load_schema("WorkbenchUploadSession.schema.json")
        enum = schema["properties"]["status"]["enum"]
        assert "uploading" in enum
        assert "failed" in enum


# ── WorkbenchChunkEdit example validates against schema ──────────────────


class TestWorkbenchChunkEditSchema:
    def test_example_validates(self):
        schema = _load_schema("WorkbenchChunkEdit.schema.json")
        example = _load_json(EXAMPLES_DIR / "workbench_chunk_edit.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_uses_content_not_display_text(self):
        schema = _load_schema("WorkbenchChunkEdit.schema.json")
        assert "content" in schema["properties"], "Schema must define 'content' field"
        assert "display_text" not in schema["properties"], "Schema must NOT define 'display_text'"

    def test_uses_base_evidence_id_not_chunk_id(self):
        schema = _load_schema("WorkbenchChunkEdit.schema.json")
        assert "base_evidence_id" in schema["properties"], "Schema must define 'base_evidence_id'"
        assert "chunk_id" not in schema["properties"], "Schema must NOT define 'chunk_id'"


# ── ChunkRevisionRequest example validates against schema ────────────────


class TestChunkRevisionRequestSchema:
    def test_example_validates(self):
        schema = _load_schema("ChunkRevisionRequest.schema.json")
        example = _load_json(EXAMPLES_DIR / "workbench_chunk_revision_request.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_payload_uses_canonical_wire(self):
        schema = _load_schema("ChunkRevisionRequest.schema.json")
        payload_props = schema["properties"]["payload"]["properties"]
        assert "evidence_id" in payload_props, "Payload must define 'evidence_id'"
        assert "doc_id" in payload_props, "Payload must define 'doc_id'"
        assert "content" in payload_props, "Payload must define 'content'"
        assert "chunk_id" not in payload_props, "Payload must NOT define 'chunk_id'"
        assert "final_doc_id" not in payload_props, "Payload must NOT define 'final_doc_id'"
        assert "display_text" not in payload_props, "Payload must NOT define 'display_text'"


# ── AgentReviewView example validates against schema ─────────────────────


class TestAgentReviewViewSchema:
    def test_example_validates(self):
        schema = _load_schema("AgentReviewView.schema.json")
        example = _load_json(EXAMPLES_DIR / "workbench_agent_review_view.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_findings_use_canonical_wire(self):
        schema = _load_schema("AgentReviewView.schema.json")
        finding_props = schema["properties"]["findings"]["items"]["properties"]
        assert "finding_id" in finding_props, "Finding must define 'finding_id'"
        assert "problem_summary" in finding_props, "Finding must define 'problem_summary'"
        assert "source_file_id" in finding_props, "Finding must define 'source_file_id'"
        assert "parse_snapshot_id" in finding_props, "Finding must define 'parse_snapshot_id'"
        assert "evidence_id" in finding_props, "Finding must define 'evidence_id'"


# ── WorkbenchTaskView example validates against schema ───────────────────


class TestWorkbenchTaskViewSchema:
    def test_example_validates(self):
        schema = _load_schema("WorkbenchTaskView.schema.json")
        example = _load_json(EXAMPLES_DIR / "workbench_task_view.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_status_derived_from_owner_states(self):
        schema = _load_schema("WorkbenchTaskView.schema.json")
        props = schema["properties"]
        assert "source_file_state" in props
        assert "intake_job_state" in props
        assert "parse_snapshot_state" in props
        assert "ticket_state" in props
        assert "published_document_state" in props


# ── Schema drift guard: workbench schemas ────────────────────────────────


class TestWorkbenchSchemaDriftGuard:
    """Ensure old field names do NOT reappear in workbench schemas."""

    def test_agent_review_view_has_no_legacy_review_fields(self):
        schema_text = (SCHEMAS_DIR / "AgentReviewView.schema.json").read_text(encoding="utf-8")
        assert '"quality_findings"' not in schema_text
        assert '"risk_flags"' not in schema_text
        assert '"suggested_fixes"' not in schema_text

    def test_workbench_chunk_edit_has_no_old_names(self):
        schema_text = (SCHEMAS_DIR / "WorkbenchChunkEdit.schema.json").read_text(encoding="utf-8")
        assert '"chunk_id"' not in schema_text, "WorkbenchChunkEdit must not contain 'chunk_id'"
        assert '"final_doc_id"' not in schema_text, "WorkbenchChunkEdit must not contain 'final_doc_id'"
        assert '"display_text"' not in schema_text, "WorkbenchChunkEdit must not contain 'display_text'"

    def test_chunk_revision_request_has_no_old_names(self):
        schema_text = (SCHEMAS_DIR / "ChunkRevisionRequest.schema.json").read_text(encoding="utf-8")
        assert '"chunk_id"' not in schema_text, "ChunkRevisionRequest must not contain 'chunk_id'"
        assert '"final_doc_id"' not in schema_text, "ChunkRevisionRequest must not contain 'final_doc_id'"
        assert '"display_text"' not in schema_text, "ChunkRevisionRequest must not contain 'display_text'"

    def test_workbench_chunk_edit_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "workbench_chunk_edit.json").read_text(encoding="utf-8")
        assert '"chunk_id"' not in example_text
        assert '"final_doc_id"' not in example_text
        assert '"display_text"' not in example_text

    def test_chunk_revision_request_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "workbench_chunk_revision_request.json").read_text(encoding="utf-8")
        assert '"chunk_id"' not in example_text
        assert '"final_doc_id"' not in example_text
        assert '"display_text"' not in example_text


# ── ApiKeyProjection schema validates ──────────────────────────────────


class TestApiKeyProjectionSchema:
    def test_example_validates(self):
        schema = _load_schema("ApiKeyProjection.schema.json")
        example = _load_json(EXAMPLES_DIR / "access_api_key_projection.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_uses_token_budget_limit_not_max_context_tokens(self):
        schema = _load_schema("ApiKeyProjection.schema.json")
        assert "token_budget_limit" in schema["properties"], "Schema must define 'token_budget_limit'"
        assert "max_context_tokens" not in schema["properties"], "Schema must NOT define 'max_context_tokens'"

    def test_uses_state_not_enabled(self):
        schema = _load_schema("ApiKeyProjection.schema.json")
        assert "state" in schema["properties"], "Schema must define 'state'"
        assert "enabled" not in schema["properties"], "Schema must NOT define 'enabled'"

    def test_has_projection_version(self):
        schema = _load_schema("ApiKeyProjection.schema.json")
        assert "projection_version" in schema["properties"]
        assert "last_updated_at" in schema["properties"]

    def test_no_key_hash(self):
        schema = _load_schema("ApiKeyProjection.schema.json")
        assert "key_hash" not in schema["properties"], "Projection must NOT contain key_hash"


class TestApiKeyProjectionSyncSchema:
    def test_example_validates(self):
        schema = _load_schema("ApiKeyProjectionSync.schema.json")
        example = _load_json(EXAMPLES_DIR / "access_api_key_projection_sync.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_has_required_command_fields(self):
        schema = _load_schema("ApiKeyProjectionSync.schema.json")
        required = schema["required"]
        assert "command_id" in required
        assert "trace_id" in required
        assert "idempotency_key" in required
        assert "actor" in required
        assert "tenant_id" in required
        assert "target_type" in required
        assert "target_id" in required
        assert "payload" in required


# ── Schema drift guard: ApiKeyProjection ───────────────────────────────


class TestApiKeyProjectionSchemaDriftGuard:
    """Ensure old field names do NOT reappear in API key projection schemas."""

    def test_api_key_projection_has_no_old_names(self):
        schema_text = (SCHEMAS_DIR / "ApiKeyProjection.schema.json").read_text(encoding="utf-8")
        assert '"max_context_tokens"' not in schema_text, "ApiKeyProjection must not contain 'max_context_tokens'"
        assert '"enabled"' not in schema_text, "ApiKeyProjection must not contain 'enabled'"
        assert '"key_hash"' not in schema_text, "ApiKeyProjection must not contain 'key_hash'"

    def test_api_key_projection_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "access_api_key_projection.json").read_text(encoding="utf-8")
        assert '"max_context_tokens"' not in example_text
        assert '"enabled"' not in example_text
        assert '"key_hash"' not in example_text

    def test_api_key_projection_sync_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "access_api_key_projection_sync.json").read_text(encoding="utf-8")
        assert '"max_context_tokens"' not in example_text
        assert '"enabled"' not in example_text
        assert '"key_hash"' not in example_text


# ── ParserProfileValidateRequest example validates against schema ────────


class TestParserProfileValidateRequestSchema:
    def test_example_validates(self):
        schema = _load_schema("ParserProfileValidateRequest.schema.json")
        example = _load_json(EXAMPLES_DIR / "parser_profile_validate_request.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_has_required_fields(self):
        schema = _load_schema("ParserProfileValidateRequest.schema.json")
        required = schema["required"]
        assert "parser_profile_id" in required
        assert "parser_id" in required
        assert "parser_config" in required
        assert "tenant_id" in required

    def test_no_old_wire_fields(self):
        schema_text = (SCHEMAS_DIR / "ParserProfileValidateRequest.schema.json").read_text(encoding="utf-8")
        assert '"query_text"' not in schema_text
        assert '"max_context_tokens"' not in schema_text
        assert '"result_chunks"' not in schema_text
        assert '"final_doc_id"' not in schema_text
        assert '"chunk_id"' not in schema_text
        assert '"display_text"' not in schema_text


class TestParserProfileValidateResponseSchema:
    def test_valid_example_validates(self):
        schema = _load_schema("ParserProfileValidateResponse.schema.json")
        example = _load_json(EXAMPLES_DIR / "parser_profile_validate_response.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_invalid_example_validates(self):
        schema = _load_schema("ParserProfileValidateResponse.schema.json")
        example = _load_json(EXAMPLES_DIR / "parser_profile_validate_response_invalid.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_runtime_owner_is_indexing(self):
        schema = _load_schema("ParserProfileValidateResponse.schema.json")
        enum = schema["properties"]["runtime_owner"]["enum"]
        assert enum == ["indexing"]

    def test_canonical_config_required_when_valid(self):
        schema = _load_schema("ParserProfileValidateResponse.schema.json")
        assert "canonical_config" in schema["properties"]
        assert "if" in schema
        assert schema["if"]["properties"]["valid"]["const"] is True
        assert "canonical_config" in schema["then"]["required"]


# ── RetrievalProfileValidateRequest example validates against schema ─────


class TestRetrievalProfileValidateRequestSchema:
    def test_example_validates(self):
        schema = _load_schema("RetrievalProfileValidateRequest.schema.json")
        example = _load_json(EXAMPLES_DIR / "retrieval_profile_validate_request.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_has_required_fields(self):
        schema = _load_schema("RetrievalProfileValidateRequest.schema.json")
        required = schema["required"]
        assert "retrieval_profile_id" in required
        assert "profile_config" in required
        assert "tenant_id" in required

    def test_no_old_wire_fields(self):
        schema_text = (SCHEMAS_DIR / "RetrievalProfileValidateRequest.schema.json").read_text(encoding="utf-8")
        assert '"query_text"' not in schema_text
        assert '"max_context_tokens"' not in schema_text
        assert '"result_chunks"' not in schema_text
        assert '"final_doc_id"' not in schema_text
        assert '"chunk_id"' not in schema_text
        assert '"display_text"' not in schema_text


class TestRetrievalProfileValidateResponseSchema:
    def test_valid_example_validates(self):
        schema = _load_schema("RetrievalProfileValidateResponse.schema.json")
        example = _load_json(EXAMPLES_DIR / "retrieval_profile_validate_response.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_invalid_example_validates(self):
        schema = _load_schema("RetrievalProfileValidateResponse.schema.json")
        example = _load_json(EXAMPLES_DIR / "retrieval_profile_validate_response_invalid.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_runtime_owner_is_retrieval(self):
        schema = _load_schema("RetrievalProfileValidateResponse.schema.json")
        enum = schema["properties"]["runtime_owner"]["enum"]
        assert enum == ["retrieval"]

    def test_canonical_config_required_when_valid(self):
        schema = _load_schema("RetrievalProfileValidateResponse.schema.json")
        assert "canonical_config" in schema["properties"]
        assert "if" in schema
        assert schema["if"]["properties"]["valid"]["const"] is True
        assert "canonical_config" in schema["then"]["required"]


# ── Schema drift guard: profile validate schemas ─────────────────────────


class TestProfileValidateSchemaDriftGuard:
    """Ensure old field names do NOT reappear in profile validate schemas or examples."""

    def test_parser_profile_validate_request_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "parser_profile_validate_request.json").read_text(encoding="utf-8")
        assert '"query_text"' not in example_text
        assert '"max_context_tokens"' not in example_text
        assert '"result_chunks"' not in example_text
        assert '"final_doc_id"' not in example_text
        assert '"chunk_id"' not in example_text
        assert '"display_text"' not in example_text

    def test_parser_profile_validate_response_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "parser_profile_validate_response.json").read_text(encoding="utf-8")
        assert '"query_text"' not in example_text
        assert '"max_context_tokens"' not in example_text
        assert '"result_chunks"' not in example_text
        assert '"final_doc_id"' not in example_text
        assert '"chunk_id"' not in example_text
        assert '"display_text"' not in example_text

    def test_retrieval_profile_validate_request_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "retrieval_profile_validate_request.json").read_text(encoding="utf-8")
        assert '"query_text"' not in example_text
        assert '"max_context_tokens"' not in example_text
        assert '"result_chunks"' not in example_text
        assert '"final_doc_id"' not in example_text
        assert '"chunk_id"' not in example_text
        assert '"display_text"' not in example_text

    def test_retrieval_profile_validate_response_example_has_no_old_names(self):
        example_text = (EXAMPLES_DIR / "retrieval_profile_validate_response.json").read_text(encoding="utf-8")
        assert '"query_text"' not in example_text
        assert '"max_context_tokens"' not in example_text
        assert '"result_chunks"' not in example_text
        assert '"final_doc_id"' not in example_text
        assert '"chunk_id"' not in example_text
        assert '"display_text"' not in example_text


# -- New schema validation tests for intake/approval contracts -----------------


class TestSourceFileRegisterRequestSchema:
    def test_example_validates(self):
        schema = _load_schema("SourceFileRegisterRequest.schema.json")
        example = _load_json(EXAMPLES_DIR / "source_file_register_request.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_has_required_command_fields(self):
        schema = _load_schema("SourceFileRegisterRequest.schema.json")
        required = schema["required"]
        assert "command_id" in required
        assert "trace_id" in required
        assert "idempotency_key" in required
        assert "actor" in required

    def test_no_old_wire_fields(self):
        schema_text = (SCHEMAS_DIR / "SourceFileRegisterRequest.schema.json").read_text(encoding="utf-8")
        assert '"query_text"' not in schema_text
        assert '"max_context_tokens"' not in schema_text
        assert '"result_chunks"' not in schema_text
        assert '"final_doc_id"' not in schema_text
        assert '"chunk_id"' not in schema_text
        assert '"display_text"' not in schema_text


class TestSourceFileViewSchema:
    def test_example_validates(self):
        schema = _load_schema("SourceFileView.schema.json")
        example = _load_json(EXAMPLES_DIR / "source_file_view.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_uses_state_not_status(self):
        schema = _load_schema("SourceFileView.schema.json")
        assert "state" in schema["properties"]


class TestIntakeJobViewSchema:
    def test_example_validates(self):
        schema = _load_schema("IntakeJobView.schema.json")
        example = _load_json(EXAMPLES_DIR / "intake_job_view.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_has_owner_reference_fields(self):
        schema = _load_schema("IntakeJobView.schema.json")
        props = schema["properties"]
        assert "parse_snapshot_id" in props
        assert "ticket_id" in props
        assert "published_document_id" in props


class TestPublishedDocumentViewSchema:
    def test_example_validates(self):
        schema = _load_schema("PublishedDocumentView.schema.json")
        example = _load_json(EXAMPLES_DIR / "published_document_view.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)


class TestApprovalTicketViewSchema:
    def test_example_validates(self):
        schema = _load_schema("ApprovalTicketView.schema.json")
        example = _load_json(EXAMPLES_DIR / "approval_ticket_view.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_has_agent_review_ref(self):
        schema = _load_schema("ApprovalTicketView.schema.json")
        assert "agent_review_ref" in schema["properties"]

    def test_no_old_wire_fields(self):
        schema_text = (SCHEMAS_DIR / "ApprovalTicketView.schema.json").read_text(encoding="utf-8")
        assert '"query_text"' not in schema_text
        assert '"max_context_tokens"' not in schema_text
        assert '"result_chunks"' not in schema_text
        assert '"chunk_id"' not in schema_text
        assert '"display_text"' not in schema_text


class TestApprovalDecisionRequestSchema:
    def test_example_validates(self):
        schema = _load_schema("ApprovalDecisionRequest.schema.json")
        example = _load_json(EXAMPLES_DIR / "approval_decision_request.json")
        resolver = _build_resolver()
        jsonschema.validate(instance=example, schema=schema, resolver=resolver)

    def test_has_required_command_fields(self):
        schema = _load_schema("ApprovalDecisionRequest.schema.json")
        required = schema["required"]
        assert "command_id" in required
        assert "trace_id" in required
        assert "idempotency_key" in required
        assert "actor" in required
        assert "payload" in required

    def test_payload_has_action_enum(self):
        schema = _load_schema("ApprovalDecisionRequest.schema.json")
        actions = schema["properties"]["payload"]["properties"]["action"]["enum"]
        assert "approve" in actions
        assert "reject" in actions
        assert "return" in actions
