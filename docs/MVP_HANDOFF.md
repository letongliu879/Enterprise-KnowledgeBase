# MVP Handoff Document

**Freeze date:** 2026-05-28
**Branch:** master
**Scope:** Backend MVP — contracts, persistence, services, real-runtime smoke

---

## 1. MVP Completed Capabilities

### Contracts & Canonical Wire

| Concept | Canonical Wire | Deprecated (do not use) |
|---|---|---|
| Query text | `query` | `query_text` |
| Token budget | `token_budget` / `token_budget_limit` | `max_context_tokens` |
| Evidence list | `evidence_items` | `result_chunks` |
| Document ID | `doc_id` | `final_doc_id` |
| Evidence ID | `evidence_id` | `chunk_id` |
| Content | `content` | `display_text` |

Wire drift guards: `packages/contracts/tests/test_wire_drift_guard.py` (5 tests) — **76 schema/drift tests pass**.

### Services (7 services, all operational)

| Service | Language | Auth | Status |
|---|---|---|---|
| admin | Python | Bearer JWT (HS256, issuer/audience supported) | MVP complete |
| workbench-api | Python | Bearer JWT (HS256, issuer/audience supported) | MVP complete |
| intake-pipeline | Python | Internal-only / caller-gated | MVP complete |
| publishing-worker | Python | Internal-only / caller-gated | MVP complete |
| indexing | Python | Internal-only / caller-gated (`IndexingSecurity` app-level) | MVP complete |
| access | Java | API Key (`X-API-Key` header → `api_key_projection`) | MVP complete |
| retrieval | Java | Internal-only / caller-gated | MVP complete |

**Internal-only services caveat**: intake-pipeline, publishing-worker, indexing, and retrieval do not perform end-user JWT verification or service-to-service auth themselves. They rely on the caller (admin, workbench-api, access, or smoke test harness) having already authenticated. In production deployment, access to these services must be restricted via network policy, API gateway, service mesh, or internal service auth. OAuth/IdP integration and service-to-service auth remain pending.

### Core Chains Verified

1. **Document intake → governance → approval → publish → indexing** — closed loop
2. **Contract projection sync** — closed loop:
   - admin → retrieval (`/internal/retrieval-profile-projections/sync`)
   - indexing → retrieval (`/internal/index-projections/sync`)
   - admin → access (`/internal/api-key-projections/sync`)
3. **Retrieval** — hybrid recall (OpenSearch BM25 + Qdrant dense) → rerank → expansion → context pack → `KnowledgeContext`
4. **Access** — REST + MCP dual entry → API key auth → retrieval delegation

### Strict Live Dependency Proof (28/28 PASS)

Verified via `py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends`:

| Dependency | Evidence |
|---|---|
| PostgreSQL | All 7 services `PgConnection` confirmed |
| OpenSearch write + recall | Direct `_search` hits=1 (`doc_smoke_test`); log: `OpenSearch live recall returned 1 hits` |
| Qdrant write + recall | Direct `scroll` points=1 (`doc_smoke_test`); log: `Qdrant live recall returned 1 hits` |
| SiliconFlow embedding | Log: `SiliconFlow embedding succeeded, model=BAAI/bge-m3, dimension=1024` |
| SiliconFlow rerank | Log: `SiliconFlow rerank succeeded, returned 1 results`; trace: `source_stages: ["rerank_live"]` |
| Redis cache (strict) | 32/32 PASS: cache miss → cache hit → purge (deleted=3) → cache miss after purge; log: `Redis cache purge: pattern=reality-rag:retrieval:*, deleted=3` |
| Contract projection sync | All 3 projection sync endpoints return 200 |
| JWT issuer/audience verification | 13 tests pass (`services/admin/tests/test_auth_jwt.py`) |

### Strict Mode Features

- `--require-live-backends`: no silent stub/heuristic fallback → `IllegalStateException` on failure (PROVEN, 28/28)
- `--require-redis-cache`: Redis cache miss/hit/purge proof (PROVEN, 32/32, 2026-05-28)
- `--require-production-jwt-config`: JWT issuer/audience enforced, no default secret (implemented, not yet run as strict smoke)

### Verified Unit/Integration Gates (2026-05-28)

| Gate | Count |
|---|---|
| `packages/contracts` pytest | 174 passed |
| `services/admin` pytest | 78 passed |
| `services/workbench-api` pytest | 57 passed |
| `services/indexing` pytest | 53 passed |
| `services/access` mvn test | 39 passed, 1 skipped |
| `services/retrieval` mvn test | 89 passed |

---

## 2. Exact Verification Commands

```bash
# Unit/integration gates
cd packages/contracts && py -3.14 -m pytest tests/ -v
cd services/admin && py -3.14 -m pytest tests/ -v
cd services/workbench-api && py -3.14 -m pytest tests/ -v
cd services/indexing && py -3.14 -m pytest tests/ -v
cd services/access && mvn test
cd services/retrieval && mvn test -Dtest='!RealSqliteIndexingRegistrySmokeTest'

# Normal smoke (stub fallback allowed)
py -3.14 scripts/run_real_runtime_smoke.py

# Strict live dependency proof (requires OpenSearch, Qdrant, SiliconFlow)
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends

# Strict Redis cache proof (requires Redis with credentials)
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends --require-redis-cache

# Full production readiness (requires Redis + production JWT config)
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends --require-redis-cache --require-production-jwt-config
```

---

## 3. Remaining Pending Items (do NOT claim as complete)

| Item | Status | Next Step |
|---|---|---|
| Redis strict smoke | **PROVEN** — 32/32 PASS (2026-05-28): cache miss → hit → purge (deleted=3) → miss | Done |
| Infrastructure ownership | **VERIFIED (Status A)** — 32/32 PASS against project deploy containers (2026-05-28); `deploy/` is primary infra owner; `upstream/ragflow/docker` is legacy/reference | Done |
| OAuth/IdP SSO | **NOT IMPLEMENTED** — JWT issuer/audience verification exists, but no SSO login page, no JWKS endpoint, no external IdP integration | Integrate OAuth2/OIDC provider (Keycloak, Auth0, etc.) |
| Production deployment | **TEMPLATES READY** — `deploy/docker-compose.yml`, `Dockerfile.python`, `Dockerfile.java`, `.env.example` created; container images NOT YET BUILT | Build images, test compose, deploy |
| Concurrent/load testing | **NOT DONE** | Run load tests against retrieval and access endpoints |
| UI/workbench frontend | **NOT DONE** | Build workbench UI and admin console frontend |
| Retrieval cache purge granularity | Partial — `POST /internal/cache/purge` flushes ALL keys regardless of request parameters | Implement collection/doc-level purge |
| MinIO / Object Storage | **TEMPLATE** — deploy compose has commented-out minio service; not in current MVP path; zero service connections confirmed | Uncomment and start when document binary storage is enabled |

---

## 4. "Do Not Regress" Constraints

### Must Preserve

1. **Canonical wire fields** — never reintroduce `query_text`, `max_context_tokens`, `result_chunks`, `final_doc_id`, `chunk_id`, `display_text` as wire fields
2. **Contract projection sync** — data flows via HTTP sync, not shared DB or direct import across languages
3. **Strict live dependency checks** — `OpenSearchRecaller`, `QdrantRecaller`, `RerankService`, `OpenAiCompatibleQueryEmbeddingClient` strict mode must throw on fallback
4. **Strict smoke entry points** — `--require-live-backends` must continue to fail (not WARN) when live backends unavailable
5. **Auth boundary** — access service uses API keys (not JWT); retrieval has no auth (caller-gated); admin/workbench use JWT
6. **`spring.sql.init.mode=never`** in smoke profile — no fixture data in retrieval; all data must come from projection sync
7. **Wire drift guards** — `test_wire_drift_guard.py` and schema validation tests must pass

### Must Update Together

Any future change to one of these requires updating ALL:
- Code (service implementation)
- Contracts (`contracts/schemas/`, `contracts/openapi/`)
- Tests (unit + integration + smoke)
- Docs (architecture.md + service-level docs)

### Source Stage Formats

- Recall: `hybrid_fusion:opensearch_bm25+qdrant_dense` (live) or `hybrid_fusion:opensearch_bm25_stub+qdrant_dense_stub` (stub)
- Rerank: `rerank_live` (SiliconFlow) or `rerank_heuristic` (local fallback)
- Embedding: logged as `SiliconFlow embedding succeeded, model=..., dimension=...`

---

## 5. Configuration Summary

### JWT Auth

| Service | Env Var for Secret | Production Requirements |
|---|---|---|
| admin | `ADMIN_JWT_SECRET` | `AUTH_MODE=production` + explicit `ADMIN_JWT_ISSUER` + `ADMIN_JWT_AUDIENCE` + non-default secret (not `smoke-test-secret` or `change-me-in-production`) |
| workbench-api | `JWT_SECRET` | `AUTH_MODE=production` + explicit `JWT_ISSUER` + `JWT_AUDIENCE` + non-default secret (not `smoke-test-secret` or `dev-secret-change-me`) |
| access | N/A (API key, not JWT) | API key projection sync from admin must be operational |
| retrieval | N/A (internal-only) | Network-level access restriction required |

**Note**: JWKS/OIDC discovery endpoint and OAuth2/OpenID Connect integration are not yet implemented. Current production JWT config supports HS256 shared-secret with issuer/audience verification only.

### Cache

| Profile | Provider | Config |
|---|---|---|
| Default (`application.yaml`) | `noop` | `fail-open: true` |
| Smoke (`application-smoke.yaml`) | `${RETRIEVAL_CACHE_PROVIDER:noop}` | `require-redis: ${REQUIRE_REDIS_CACHE:false}` |
| Strict Redis | `redis` | `REQUIRE_REDIS_CACHE=true`, `RETRIEVAL_CACHE_FAIL_OPEN=false` |

### Infrastructure Ownership

**Status A VERIFIED (2026-05-28) — `deploy/` is primary infra owner. `upstream/ragflow/docker` is legacy/reference.**

| Dependency | Container | Image | Port | Verification |
|---|---|---|---|---|
| PostgreSQL | `deploy-postgres-1` | postgres:16 | :5432 | VERIFIED — smoke 32/32 |
| OpenSearch | `deploy-opensearch-1` | opensearchproject/opensearch:2.19.1 | :1201→9201 | VERIFIED — `_search` hits=1 |
| Qdrant | `deploy-qdrant-1` | qdrant/qdrant:latest | :6333-6334 | VERIFIED — `scroll` points=1 |
| Redis | `deploy-redis-1` | valkey/valkey:8 | :6379 | VERIFIED — purge deleted=3 |
| MinIO / S3 | `deploy/docker-compose.yml` (commented out) | `deploy/docker-compose.yml` | **TEMPLATE** — not in current MVP path; no service uses MinIO; smoke 32/32 confirmed zero impact when stopped |

### Live Backends

| Service | Env Var | Strict Mode |
|---|---|---|
| indexing | `INDEXING_BACKEND_MODE=hybrid` | `INDEXING_REQUIRE_LIVE_BACKENDS=true` |
| retrieval | `live-recall-enabled`, `live-embedding-enabled`, `live-rerank-enabled` | `REQUIRE_LIVE_BACKENDS=true` |

---

## 6. Recommended Next Phases (in order)

1. **OAuth/IdP integration** — add OAuth2/OIDC provider, JWKS endpoint, replace smoke-test-secret with real identity provider
3. **Deployment hardening** — containerize services, production profiles, secrets management, monitoring
4. **Load/concurrency testing** — verify retrieval throughput, cache hit rates, failover behavior
5. **UI/workbench frontend** — if needed by stakeholders

---

## 7. Files Modified This Session (final)

| File | Change Type |
|---|---|
| `.gitignore` | Added `.run-logs/`, `.verify/runtime/`, `.verify/logs/` |
| `docs/architecture.md` | Auth boundary table, Redis/JWT status corrections, strict proof evidence update |
| `docs/MVP_HANDOFF.md` | **NEW** — this file |
| `README.md` | Strict smoke commands, Redis/JWT status, completed capabilities |
| `services/admin/admin.md` | Auth description: bcrypt→pbkdf2_sha256, issuer/audience config |
| `services/workbench-api/workbench-api.md` | Removed non-existent `/workbench/auth/login`; JWT issuer/audience added |
| `services/access/access.md` | Clarified API key auth (no JWT) |
| `services/retrieval/retrieval.md` | Strict mode proof evidence, Redis status NOT PROVEN |
| `services/smoke_tests/README.md` | Three smoke modes, test doubles table, strict proof evidence |
| `services/admin/tests/test_auth_jwt.py` | **NEW** — 13 JWT issuer/audience tests |
| `services/admin/src/admin_service/config.py` | Added `jwt_issuer`, `jwt_audience`, `auth_mode` |
| `services/admin/src/admin_service/deps.py` | JWT issuer/audience enforcement |
| `services/admin/src/admin_service/identity/service.py` | Token iss/aud claims |
| `services/workbench-api/src/workbench_api/config.py` | Added `jwt_issuer`, `jwt_audience`, `auth_mode` |
| `services/workbench-api/src/workbench_api/deps.py` | JWT issuer/audience enforcement |
| `services/retrieval/src/main/java/.../RetrievalBackendProperties.java` | Added `requireLiveBackends` |
| `services/retrieval/src/main/java/.../RetrievalCacheProperties.java` | Added `requireRedis` |
| `services/retrieval/src/main/java/.../OpenSearchRecaller.java` | Logger + strict mode enforcement |
| `services/retrieval/src/main/java/.../QdrantRecaller.java` | Logger + strict mode enforcement |
| `services/retrieval/src/main/java/.../RerankService.java` | Logger + strict mode enforcement |
| `services/retrieval/src/main/java/.../OpenAiCompatibleQueryEmbeddingClient.java` | Logger + strict mode enforcement |
| `services/retrieval/src/main/java/.../RedisRetrievalCache.java` | `requireRedis` strict check in `isAvailable()` |
| `services/retrieval/src/main/java/.../RecallOrchestrator.java` | Source stage granularity |
| `services/retrieval/src/main/resources/application.yaml` | `require-live-backends: false` |
| `services/retrieval/src/main/resources/application-smoke.yaml` | Live backends config + Redis config with env vars |
| `services/retrieval/src/test/.../OpenSearchRecallerTest.java` | **NEW** — 6 tests |
| `services/retrieval/src/test/.../QdrantRecallerTest.java` | **NEW** — 6 tests |
| `services/retrieval/src/test/.../RerankServiceTest.java` | **NEW** — 6 tests |
| `services/retrieval/src/test/.../OpenAiCompatibleQueryEmbeddingClientTest.java` | **NEW** — 5 tests |
| `services/retrieval/src/test/.../RerankDisabledRetrieveControllerTest.java` | Updated source stage assertion |
| `services/indexing/src/indexing_service/config.py` | Added `require_live_backends` |
| `services/indexing/src/indexing_service/backends.py` | `require_live` param for `embed_texts()`, `QdrantPointWriter`, `get_index_backend()` |
| `scripts/run_real_runtime_smoke.py` | `--require-live-backends`, `--require-redis-cache`, `--require-production-jwt-config`; OpenSearch/Qdrant direct verification; Redis cache proof; WARN status for non-strict |

---

## 8. Unresolved Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `services/indexing/.env` contains real SiliconFlow API key | HIGH — gitignored (`*.env`), confirmed not tracked | Key rotation recommended before production deployment |
| Internal-only services (intake, publishing, indexing, retrieval) rely on deployment boundary, not in-service auth | HIGH — any network exposure of these services bypasses all authentication | Add service-to-service auth (mTLS, SPIFFE, internal JWT) or enforce network policy (API gateway, service mesh, firewall rules) in deployment hardening phase |
| Redis requires authentication credentials not configured | ~~MEDIUM~~ RESOLVED — strict Redis smoke 32/32 PASS (2026-05-28) | Credentials configured via `REDIS_PASSWORD` env var (never tracked in repo) |
| `smoke-test-secret` used for all smoke auth | LOW — explicitly marked as smoke/test mode only | Production mode requires `AUTH_MODE=production` + explicit issuer/audience + non-default secret |
