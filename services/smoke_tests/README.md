# Cross-Service MVP Smoke Tests

This directory contains end-to-end smoke tests that exercise the full service chain.

There are **two** smoke test modes:

1. **In-process ASGI smoke** (`test_mvp_python_chain.py`) — fast, no real servers
2. **Real-runtime smoke** (`../../scripts/run_real_runtime_smoke.py`) — real OS processes, localhost HTTP

---

## 1. In-Process ASGI Smoke (Fast)

All Python FastAPI services are mounted under a single combined ASGI app (`combined_app` in `conftest.py`). Cross-service HTTP calls route in-process via `httpx.ASGITransport`.

```
TestClient(combined_app)
  ├── /workbench  → workbench_api.main:app  (prefix re-added after mount strip)
  ├── /indexing   → indexing_service.main:app
  ├── /intake     → intake_pipeline.main:app
  ├── /approval   → approval_service.main:app
  ├── /publishing → publishing_worker.main:app
  └── /           → admin_service.main:app      (admin routes embed /admin)
```

### Running

```bash
cd services/smoke_tests
py -3.14 -m pytest test_mvp_python_chain.py -v
```

### Key Design Decisions

1. **Module-scoped fixtures**: All fixtures use `scope="module"` because services maintain in-memory state (intake's `_documents`, indexing repository caches) that persists across function-scoped tests. The DB is reset once per module via `_reset_smoke_db`.

2. **httpx patch strategy**:
   - `httpx.AsyncClient.__init__` is patched globally to inject `ASGITransport(combined_app)` when no explicit transport is provided.
   - `intake_pipeline.main.httpx.Client` is patched locally (via a proxy module) to `_AsyncClientWrapper`, which delegates to `httpx.AsyncClient` internally. This avoids mutating the global `httpx.Client`.

3. **Sync-async bridge**: `_AsyncClientWrapper` handles nested event loops by offloading coroutine execution to a fresh thread with an explicitly created event loop.

4. **Shared SQLite DB**: A single SQLite file at `.verify/runtime/smoke-test.db` is used so Java services can also read the state.

### Known Limitations

- **Retrieval/access visibility**: Not directly tested in Python smoke tests. Verified by existing Java tests (`DbBackedRuntimeRetrieveControllerTest`, `RetrieveControllerTest`) and manual `RealSqliteIndexingRegistrySmokeTest`.
- **Workbench parse-preview**: Bypassed in smoke test; uses `intake enter_document` directly for parse preview.
- **Reindex version creation**: Current implementation rebuilds the same index version rather than creating a new one.

---

## 2. Real Runtime Smoke (Honest)

`scripts/run_real_runtime_smoke.py` starts each service as a **real OS process** and calls them via **localhost HTTP**. No ASGI in-process transport, no TestClient, no direct imports of service internals for business logic.

### What it does

1. Starts Python services (admin, workbench, indexing, intake) as `uvicorn` subprocesses
2. Starts Java services (access, retrieval) as `mvn spring-boot:run` subprocesses with `smoke` profile
3. Waits for health endpoints to respond
4. Runs the full MVP chain through real HTTP:
   - admin: create collection, parser profile, retrieval profile, API key, sync to access
   - workbench: create upload, list tasks
   - intake: enter_document, approve-and-publish
   - indexing: query chunks, list indexed documents
   - retrieval: direct query (returns evidence_items from projection-synced PostgreSQL data)
   - access: query with API key (returns evidence_items via retrieval)
   - visibility: archive/retract document

### Running

```bash
# Normal mode — stub fallback allowed, no Redis, smoke JWT secret (28/28, PROVEN)
py -3.14 scripts/run_real_runtime_smoke.py

# Strict live backends — require OpenSearch/Qdrant/SiliconFlow (28/28, PROVEN)
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends

# Strict live + Redis — also require Redis cache miss/hit/purge proof (NOT RUN)
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends --require-redis-cache

# Full production — live + Redis + production JWT config (NOT RUN)
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends --require-redis-cache --require-production-jwt-config

# Connect to already-running services
py -3.14 scripts/run_real_runtime_smoke.py --use-existing-services

# Keep services running after smoke
py -3.14 scripts/run_real_runtime_smoke.py --keep-running
```

### Port Map

| Service | Port | Health Endpoint |
|---------|------|-----------------|
| indexing (Python) | 18080 | `GET /health` |
| workbench (Python) | 18083 | `GET /workbench/health` |
| admin (Python) | 18084 | `GET /health` |
| intake (Python) | 18085 | `GET /health` |
| publishing (Python) | 18086 | `GET /health` |
| access (Java) | 18181 | `GET /health` |
| retrieval (Java) | 18182 | `GET /health` |

### Test Doubles vs Real Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Python services DB | **Real PostgreSQL** | All services share `DATABASE_URL=postgresql://rag_flow:infini_rag_flow@127.0.0.1:5432/rag_flow` |
| Java services DB | **Real PostgreSQL** | Access and retrieval use `smoke` profile with `jdbc:postgresql://...` |
| Redis/cache | **Test double (noop)** | `retrieval.cache.provider=noop` in smoke profile; Redis not required |
| OpenSearch | **Real (strict mode verified)** | `INDEXING_BACKEND_MODE=hybrid`; strict smoke confirms OpenSearch `_search` returns `doc_smoke_test` and retrieval logs `OpenSearch live recall returned 1 hits`. Normal mode falls back to stub with WARN log. |
| Qdrant | **Real (strict mode verified)** | `INDEXING_BACKEND_MODE=hybrid`; strict smoke confirms Qdrant `scroll` returns `doc_smoke_test` and retrieval logs `Qdrant live recall returned 1 hits`. Normal mode falls back to stub with WARN log. |
| Embedding (indexing) | **Real SiliconFlow** | Real API key/URL in `.env`; `embed_texts()` calls `https://api.siliconflow.cn/v1/embeddings`. Falls back to 16-dim hash vector only when API key/URL missing (non-strict). |
| Embedding (retrieval) | **Real (strict mode verified)** | Strict smoke logs `SiliconFlow embedding succeeded, model=BAAI/bge-m3, dimension=1024`. Normal mode falls back to empty/stub with WARN log. |
| Rerank | **Real (strict mode verified)** | Strict smoke logs `SiliconFlow rerank succeeded, model=BAAI/bge-reranker-v2-m3, returned 1 results`; trace records `source_stages: ["rerank_live"]`. Normal mode falls back to heuristic with WARN log. |
| Retrieval data | **Projection sync** | data-smoke.sql and schema-smoke.sql exist but `spring.sql.init.mode=never`; all data comes from real HTTP projection sync (admin → retrieval, indexing → retrieval) |
| Auth / JWT | **Test double** | Uses `smoke-test-secret` HS256 tokens; no real IdP/OAuth flow |

### Known Gaps

- **Silent fallback in recall/rerank/embedding (resolved in strict mode)**: Strict mode (`--require-live-backends`) now throws `IllegalStateException` if any live backend is unavailable, empty, or unconfigured. Normal mode still allows fallback for local dev.
- **JWT auth uses smoke secret**: All auth tokens are generated with `smoke-test-secret` HS256. No real IdP or OAuth flow is exercised.
- **Cache is noop**: Retrieval cache uses `provider: noop`; Redis is not exercised.
- **Strict smoke verified live (2026-05-28)**: 28/28 PASS with `--require-live-backends`. OpenSearch doc verification (hits=1), Qdrant point verification (points=1), retrieval logs confirm `SiliconFlow embedding succeeded`, `live recall returned 1 hits`, `SiliconFlow rerank succeeded`, trace records `source_stages: ["rerank_live"]`.

---

## Integration Gaps Discovered & Fixed

1. **Intake `approve_and_publish` did not persist `PublishedDocument`**: The endpoint set in-memory state but never wrote to the `published_documents` table. Fixed by adding `PublishedDocumentRepository.create()` call in `_publish_from_ticket()`.

2. **Workbench → intake client envelope mismatch**: Workbench's `IntakeClient.create_source_file()` sent a command envelope, but intake expected flat `RegisterSourceFileRequest`. Fixed by unwrapping the envelope in the client.

3. **Admin mount prefix stripping**: Mounting `admin_app` at `/admin` stripped the `/admin` prefix, but admin routes embed `/admin`. Fixed by mounting admin at `/`.

4. **Global httpx.Client mutation**: Patching `_intake_main.httpx.Client = _AsyncClientWrapper` mutated the global `httpx.Client`, breaking TestClient inheritance. Fixed by using a proxy module.
