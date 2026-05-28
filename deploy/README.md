# Enterprise KnowledgeBase — Deployment Guide

**Status**: Deployment templates ready. Application container images **NOT YET BUILT**.
Services are currently verified via `scripts/run_real_runtime_smoke.py`.

## Quick Start (Dev / Smoke Test)

The verified path for running all services locally:

```bash
# Prerequisites: PostgreSQL, OpenSearch, Qdrant, Redis already running
# (e.g., via upstream RAGFlow docker-compose)

# Copy env template and fill in secrets
cp deploy/.env.example deploy/.env
# Edit deploy/.env — set Redis password, SiliconFlow API key, DB password

# Run normal smoke
py -3.14 scripts/run_real_runtime_smoke.py

# Run strict live dependency proof
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends

# Run strict Redis cache proof
REDIS_PASSWORD=<password> \
  py -3.14 scripts/run_real_runtime_smoke.py \
  --require-live-backends \
  --require-redis-cache
```

## Infrastructure Ownership

**Status: TEMPLATE READY (not yet verified as active infra entry point).**

The `deploy/docker-compose.yml` infrastructure configuration matches the current dev environment
(sourced from `upstream/ragflow/docker/docker-compose-base.yml`). However, the current strict
smoke still runs against the **upstream** containers because they occupy the host ports.

| Infra | Current Smoke Source | Target Owner | Verification |
|---|---|---|---|
| PostgreSQL | upstream `docker-postgres-1` (postgres:16, :5432) | `deploy/docker-compose.yml` | **TEMPLATE MATCH** — same image/port/env |
| OpenSearch | upstream `docker-opensearch01-1` (2.19.1, :1201→9201) | `deploy/docker-compose.yml` | **TEMPLATE MATCH** — same image/port/http.port |
| Qdrant | upstream `docker-qdrant-1` (latest, :6333-6334) | `deploy/docker-compose.yml` | **TEMPLATE MATCH** — same image/ports/healthcheck |
| Redis | upstream `docker-redis-1` (valkey:8, :6379) | `deploy/docker-compose.yml` | **TEMPLATE MATCH** — same image/command/healthcheck |

**To verify deploy as infra owner** (next step, not yet done):
1. Stop upstream infra containers
2. `cp deploy/.env.example deploy/.env` and fill in secrets
3. `docker compose -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis`
4. `py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends --require-redis-cache`
5. If 32/32 PASS → update status to VERIFIED

To start only infrastructure (when verified):

```bash
docker compose -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis
```

## Application Services (TEMPLATE — Not Yet Built)

| Service | Language | Port | Health | Dockerfile |
|---|---|---|---|---|
| admin | Python | 18084 | `GET /health` | `Dockerfile.python` |
| workbench-api | Python | 18083 | `GET /workbench/health` | `Dockerfile.python` |
| indexing | Python | 18080 | `GET /health` | `Dockerfile.python` |
| intake-pipeline | Python | 18085 | `GET /health` | `Dockerfile.python` |
| publishing-worker | Python | 18086 | `GET /health` | `Dockerfile.python` |
| retrieval | Java | 18182 | `GET /health` | `Dockerfile.java` |
| access | Java | 18181 | `GET /health` | `Dockerfile.java` |

Service blocks in `docker-compose.yml` are commented out. To build and deploy:

```bash
# Build Python service image (example: admin)
docker build -t ekb-admin -f deploy/Dockerfile.python \
  --build-arg SERVICE_DIR=services/admin .

# Build Java service image (example: retrieval)
docker build -t ekb-retrieval -f deploy/Dockerfile.java \
  --build-arg SERVICE_DIR=services/retrieval .

# Uncomment service blocks in docker-compose.yml, then:
docker compose -f deploy/docker-compose.yml up -d
```

**Known limitation**: Python Dockerfile copies ALL service source directories into each image because services cross-import via PYTHONPATH. Refactoring into proper installable packages is a future optimization.

## Environment Configuration

All configuration is via environment variables. Template: `deploy/.env.example`.

### Required for smoke test (minimum)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `ADMIN_JWT_SECRET` / `JWT_SECRET` | JWT signing key (smoke mode: `smoke-test-secret`) |
| `INDEXING_EMBEDDING_API_KEY` | SiliconFlow API key |
| `REDIS_PASSWORD` | Redis auth password (for strict Redis smoke) |

### Production JWT (when `AUTH_MODE=production`)

Additionally required:
- `ADMIN_JWT_ISSUER` + `ADMIN_JWT_AUDIENCE`
- `JWT_ISSUER` + `JWT_AUDIENCE`
- Secrets must NOT be `smoke-test-secret` or `change-me-in-production`

### Strict Mode Flags

| Flag | Effect |
|---|---|
| `REQUIRE_LIVE_BACKENDS=true` | Retrieval fails if OpenSearch/Qdrant/SiliconFlow unavailable |
| `REQUIRE_REDIS_CACHE=true` | Retrieval fails if Redis unavailable |
| `RETRIEVAL_CACHE_PROVIDER=redis` | Enables Redis cache provider |
| `INDEXING_REQUIRE_LIVE_BACKENDS=true` | Indexing fails if embedding API or hybrid backend unavailable |

## What's Not Done

- Application container images not built/tested
- OAuth/IdP SSO not implemented
- Service-to-service auth (mTLS/SPIFFE) not implemented
- Load/concurrency testing not done
- UI/workbench frontend not built
