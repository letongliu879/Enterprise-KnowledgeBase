# Enterprise KnowledgeBase

Enterprise KnowledgeBase is an enterprise knowledge platform for governed RAG and MCP services.

This project is the revised version of `Reality-RAG`. It keeps the same high-level service architecture, while changing the upstream integration strategy:

- governance, lifecycle, and retrieval boundaries remain platform-owned
- RAGFlow is used directly for document parsing and chunking runtime capability
- RAGFlow is not the governance source of truth

Architecture entry:

- [Top-level architecture](./docs/architecture.md)
- [Project overview](./docs/project-overview.md)
- [ParseSnapshot architecture](./docs/parse-snapshot-architecture.md)
- [Role of upstream/ragflow](./docs/upstream-ragflow-role.md)
- [What to keep from Reality-RAG](./docs/reality-rag-lessons.md)
- [Intake pipeline design](./services/intake-pipeline/intake-pipeline.md)
- [RAGFlow source isolation map](./docs/ragflow-source-isolation.md)

Current repository focus:

- `contracts/`: canonical service contracts
- `packages/contracts`: Python runtime contract package
- `packages/persistence`: persistence models and repositories
- `packages/documents`: shared document-domain package
- `services/intake-pipeline`: intake, governance, approval, publishing, lifecycle
- `services/indexing`: parse preview, ParseSnapshot, chunking, embedding, index materialization
- `services/retrieval`: Java retrieval mainline with RAGFlow/ContextWeaver-inspired strategies
- `services/workbench-api`: workbench-facing parse/chunk API seam
- `upstream/ragflow`: source fork for parsing/chunking/workbench runtime

## Current Implementation Status

### Completed: Document Workflow Backbone Phase

- **Intake-pipeline internal APIs**: `POST /internal/source-files`, `GET /internal/source-files/{id}`, `GET /internal/intake-jobs/{id}`, `GET /internal/published-documents/{id}`
- **Approval-service internal APIs**: `GET /internal/tickets`, `GET /internal/tickets/{id}`, `POST /internal/tickets/{id}/decide`, `GET /internal/tickets/{id}/agent-review`
- **Workbench task projection**: aggregates upload session + downstream owner states into unified task view with derived `status` and `progress_pct`
- **Cross-tenant isolation tests**: fail-closed tenant filtering on approval-service ticket list, user-level isolation on workbench task access

### Completed: Real Runtime Smoke Phase

- **Real-runtime smoke harness**: `scripts/run_real_runtime_smoke.py` starts services as real OS processes and exercises them via localhost HTTP
- **Health endpoints**: all 6 services expose `/health` (or `/actuator/health` for Java)
- **Cross-service HTTP smoke flow**: admin → workbench → intake → indexing → retrieval → access
- **Environment examples**: `.env.example` for all Python services; `application-smoke.yaml` for Java services
- **Test double documentation**: honest gap table showing which dependencies are real vs. test doubles

### Running Tests

**Unit / integration gates:**

```bash
# Python services
cd packages/contracts && py -3.14 -m pytest tests/ -v
cd services/admin && py -3.14 -m pytest tests/ -v
cd services/workbench-api && py -3.14 -m pytest tests/ -v
cd services/indexing && py -3.14 -m pytest tests/ -v

# Java services
cd services/access && mvn test
cd services/retrieval && mvn test -Dtest='!RealSqliteIndexingRegistrySmokeTest'
```

**In-process smoke (ASGI, no real servers):**

```bash
cd services/smoke_tests
py -3.14 -m pytest test_mvp_python_chain.py -v
```

**Real-runtime smoke (real OS processes, localhost HTTP):**

```bash
# Normal mode — allows stub fallback, live backends recommended
py -3.14 scripts/run_real_runtime_smoke.py

# Strict mode — requires live OpenSearch/Qdrant/SiliconFlow, no stub fallback
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends

# Connect to already-running services
py -3.14 scripts/run_real_runtime_smoke.py --use-existing-services

# Keep services running after smoke for manual exploration
py -3.14 scripts/run_real_runtime_smoke.py --keep-running
```

**Port map (default):**

| Service | Port | Health Endpoint |
|---------|------|-----------------|
| indexing (Python) | 18080 | `GET /health` |
| workbench (Python) | 18083 | `GET /workbench/health` |
| admin (Python) | 18084 | `GET /health` |
| intake (Python) | 18085 | `GET /health` |
| publishing (Python) | 18086 | `GET /health` |
| access (Java) | 18181 | `GET /health` |
| retrieval (Java) | 18182 | `GET /health` |

### Pending (next phase)

- Workbench UI integration
- Published chunk revision flow (requires indexing internal APIs)
- OAuth/IdP SSO integration (JWT issuer/audience verification implemented; SSO UI + JWKS endpoint not done)
- Concurrent/load testing

### Completed: Live Dependency Proof Phase (2026-05-28)

- **Real-runtime strict smoke**: 28/28 PASS with `--require-live-backends`
- **PostgreSQL**: shared database for all Python + Java services
- **OpenSearch**: write + BM25 recall verified live
- **Qdrant**: write + dense recall verified live
- **SiliconFlow embedding**: BAAI/bge-m3, 1024-dim verified live
- **SiliconFlow rerank**: BAAI/bge-reranker-v2-m3 verified live (trace: `source_stages: ["rerank_live"]`)
- **JWT production boundary**: issuer/audience verification implemented (`services/admin/tests/test_auth_jwt.py`, 13 tests)
- **Redis cache**: `RedisRetrievalCache.java` strict proof **PROVEN** (32/32 PASS, 2026-05-28): cache miss → hit → purge → miss
- **Strict mode flags**: `--require-live-backends` (PROVEN), `--require-redis-cache` (PROVEN), `--require-production-jwt-config` (implemented)
- **Unit/integration gates**: contracts 174, admin 78, workbench-api 57, indexing 53, retrieval 89, access 39 — all passing
