# Contracts

`contracts/` is the canonical cross-service contract source for the final Reality-RAG architecture.

- `openapi/` defines HTTP ingress contracts.
- `schemas/` defines core DTO and state schemas.
- `events/` defines event envelope and event payload schemas.
- `examples/` provides example payloads used by contract tests.
- `compatibility/` records compatibility rules and evolution notes.

These files are authoritative for cross-service names and payload shape. Service-local models may wrap them, but they must not redefine them incompatibly.

## Canonical Wire Format

The following field names are the canonical wire format for cross-service communication. All services MUST use these exact names on the wire.

| Concept | Canonical Wire Name | Old Name (deprecated) |
|---|---|---|
| Query text (RetrieveRequest) | `query` | `query_text` |
| Token budget (RetrieveRequest) | `token_budget` | `max_context_tokens` |
| Token budget (API Key) | `token_budget_limit` | `max_context_tokens` |
| API Key state | `state` | `enabled` |
| Evidence list (KnowledgeContext) | `evidence_items` | `result_chunks` |
| Document ID (in evidence item) | `doc_id` | `final_doc_id` |
| Evidence/Chunk ID | `evidence_id` | `chunk_id` |
| Display content | `content` | `display_text` |

### Snake-case convention

All JSON wire fields use `snake_case` naming. Java local mirrors use `camelCase` field names with explicit `@JsonProperty` annotations or `@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)` to produce the correct wire format.

## Local Mirrors are Transitional

Some services still keep local mirrored DTO/model definitions because code generation is not fully wired yet.

- These local mirrors are **transitional only**; they are not independent contract owners and must not evolve field shape on their own.
- Any contract change must land in `contracts/` first, then be propagated into local mirrors.
- Until generation is fully wired, every local mirror must be treated as `contracts/`-validated compatibility scaffolding, not as a parallel schema source.
- Java local mirrors must use explicit `@JsonProperty("canonical_name")` on every field whose camelCase/SnakeCase mapping would not produce the canonical wire name.

## Contract Change Process

1. **Update schemas first**: Modify the relevant `.schema.json` file(s) in `contracts/schemas/`.
2. **Update examples**: Modify the corresponding example file(s) in `contracts/examples/`.
3. **Update OpenAPI**: If the schema is exposed via HTTP, update the relevant `contracts/openapi/*.yaml` file.
4. **Update Python contracts**: Sync `packages/contracts/src/reality_rag_contracts/models.py` and add/update tests in `packages/contracts/tests/`.
5. **Update Java mirrors**: Sync the relevant Java record/DTO in each service, ensuring `@JsonProperty` and `@JsonNaming` are correct.
6. **Add/update wire tests**: Verify real JSON serialization/deserialization works across service boundaries.
7. **Update documentation**: Update this README and any service-specific docs.
8. **Run the gate**: See Gate Commands below.

## Gate Commands

Run these commands locally before considering a contract change complete:

```bash
# Python contracts: schema validation + roundtrip + drift guard
cd packages/contracts
py -3.14 -m pytest tests/ -v

# Access service: wire tests + integration tests
cd services/access
mvn test

# Retrieval service: wire tests + controller tests (exclude smoke test)
cd services/retrieval
mvn test -Dtest='!RealSqliteIndexingRegistrySmokeTest'
```

The Python `test_schema_validation.py` enforces a schema-drift guard: if `query_text`, `max_context_tokens`, or `result_chunks` reappear in the schemas, the test fails.

## Current Status

- [x] `RetrieveRequest.schema.json` uses `query` and `token_budget`
- [x] `KnowledgeContext.schema.json` uses `evidence_items` with `doc_id`/`evidence_id`/`content`
- [x] `CollectionRetrievalPlan.schema.json` has `tenant_id` as required
- [x] `common.schema.json` defines `tenant_id`
- [x] Python contracts aligned with canonical wire
- [x] Java access-service contracts aligned with canonical wire
- [x] Java retrieval-service contracts aligned with canonical wire
- [x] Examples validate against schemas
- [x] Real wire tests pass (access <-> retrieval serialization roundtrip)
- [x] `WorkbenchUploadSession.schema.json` uses canonical wire
- [x] `WorkbenchChunkEdit.schema.json` uses `base_evidence_id` and `content`
- [x] `ChunkRevisionRequest.schema.json` uses canonical wire in payload
- [x] `AgentReviewView.schema.json` defines read-only artifact view
- [x] `ApiKeyProjection.schema.json` uses `token_budget_limit` and `state`
- [x] `ApiKeyProjectionSync.schema.json` defines command envelope with idempotency
- [x] `ParserProfileValidateRequest.schema.json` / `ParserProfileValidateResponse.schema.json` — indexing profile validate/canonicalize
- [x] `RetrievalProfileValidateRequest.schema.json` / `RetrievalProfileValidateResponse.schema.json` — retrieval profile validate/canonicalize
- [x] Admin publish flow integrates downstream validate with ops_audit logging and fail-closed semantics
- [x] `SourceFileRegisterRequest.schema.json` / `SourceFileView.schema.json` — intake source file register/read
- [x] `IntakeJobView.schema.json` — intake job read-only owner state
- [x] `PublishedDocumentView.schema.json` — published document read-only owner state
- [x] `ApprovalTicketView.schema.json` — approval ticket read-only owner state
- [x] `ApprovalDecisionRequest.schema.json` — approval decision command envelope
- [x] `intake-internal.yaml` — intake-pipeline owner internal API contract
- [x] `approval-internal.yaml` — approval-service owner internal API contract
- [x] `workbench-api` task projection queries real intake-pipeline and approval-service owner APIs
- [x] `workbench-api` downstream client uses canonical wire fields
- [x] `workbench-api` chunk edit/revision flow: **IMPLEMENTED**
  - `POST /internal/chunks/{evidence_id}/revisions` — indexing creates ChunkRevision
  - `GET /internal/chunk-revisions/{revision_id}` — read revision status
  - `POST /internal/chunk-revisions/{revision_id}/materialize` — materialize revision, supersede old chunk, write OpenSearch+Qdrant
  - `POST /internal/cache/purge` — retrieval cache purge by scope
  - `POST /workbench/chunk-edits/{id}/submit` — pre-publish edit submit to indexing
- [x] `admin` document lifecycle ops: archive/retract/reindex endpoints with ops_audit logging and downstream fail-closed semantics
- [x] `indexing` pre-publish chunk edit overlay: `_apply_pre_publish_edits()` merges draft chunk revisions before materialization
- [x] `indexing` cache purge on activation: `IndexJobRunner` calls retrieval `POST /internal/cache/purge` after successful index version activation
- [x] `workbench-api` task projection enhanced with `index_build_state` and `active_index_version` from indexing service
- [x] `workbench-api` task status derivation: archived → retracted → published (active_index_version) → indexing (BUILDING) → approved → rejected → reviewing → failed → parsing → uploading
- [x] `admin/workbench` core backbone: **COMPLETE** — all owner APIs wired, cross-service smoke tests pass
- [x] Cross-service Python smoke test: `services/smoke_tests/test_mvp_python_chain.py` — 20 tests covering full chain from collection creation through archive/retract
- [ ] `admin/workbench` UI integration: pending

## Owner API vs Workbench Projection Relationship

The workbench-api is a **consumer and projection store**, not an owner.

| Entity | Owner | Workbench Role |
|--------|-------|----------------|
| source_file | intake-pipeline | Read-only display; register via `POST /internal/source-files` |
| intake_job | intake-pipeline | Read-only status query; derive task progress |
| published_document | publishing domain | Read-only display; never mutate |
| approval_ticket | approval-service | Read-only list/detail; decide via `POST /internal/tickets/{id}/decide` |
| agent_review | agent-review-worker / approval pipeline | Read-only display via `GET /internal/tickets/{id}/agent-review` |
| parse_snapshot | indexing-service | Read-only display; trigger preview via indexing |
| workbench_upload_session | workbench-api | Local projection; status derived from owner states |
| workbench_chunk_edit | workbench-api | Local edit intent; revision command sent to indexing |

Rules:
- Workbench **never** directly writes to owner tables (`source_files`, `intake_jobs`, `approval_tickets`, `published_documents`).
- Workbench **never** makes its local `status` a source of truth; it must be reconstructible from owner states.
- All cross-service writes use command envelopes with `command_id`, `trace_id`, `idempotency_key`, `actor`.
- On downstream failure, workbench projection must NOT be marked success; return `DOWNSTREAM_NOT_IMPLEMENTED` or `DOWNSTREAM_UNAVAILABLE`.
