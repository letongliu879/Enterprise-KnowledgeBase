# Enterprise KnowledgeBase — Deployment Guide

**Status**: Docker Compose is the recommended way to run the full EKB stack (infrastructure + application services).

## Quick Start (Compose)

```bash
# 1. Prepare environment
cp deploy/.env.example deploy/.env
# Edit deploy/.env — set DATABASE_PASSWORD, REDIS_PASSWORD, SiliconFlow API keys, JWT secrets

# 2. Start infrastructure + application services
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d

# 3. Wait for all services to be healthy, then run smoke test
uv run python scripts/run_real_runtime_smoke.py --use-existing-services
```

## Fallback: Local Host Process Mode

For fast local iteration without building images:

```bash
# Start only infrastructure
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis

# Start application services directly on the host
uv run python scripts/ekb-svc.py start
```

## Infrastructure Ownership

**Status: VERIFIED — project deploy is primary infra owner.**

| Infra | Container | Image | Port | Verification |
|---|---|---|---|---|
| PostgreSQL | `deploy-postgres-1` | postgres:16 | :5432 | VERIFIED |
| OpenSearch | `deploy-opensearch-1` | opensearchproject/opensearch:2.19.1 | :19201→9201 | VERIFIED |
| Qdrant | `deploy-qdrant-1` | qdrant/qdrant:latest | :6333-6334 | VERIFIED |
| Redis | `deploy-redis-1` | valkey/valkey:8 | :6379 | VERIFIED |
| MinIO / S3 | `minio/minio:latest` | :9000-9001 | TEMPLATE — not in MVP path |

To start infrastructure only:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis
```

## Application Services

| Service | Language | Port | Compose Service | Health | Status |
|---|---|---|---|---|---|
| admin | Python | 18084 | `admin` | `GET /health` | ENABLED |
| workbench-api | Python | 18083 | `workbench` | `GET /workbench/health` | ENABLED |
| indexing | Python | 18080 | `indexing` | `GET /health` | ENABLED |
| document-service | Python | 8006 | `document-service` | `GET /health` | ENABLED |
| publishing-worker | Python | 18086 | `publishing-worker` | `GET /health` | ENABLED |
| approval-service | Python | 18087 | `approval-service` | `GET /health` | ENABLED |
| agent-review-worker | Python | 18090 | `agent-review-worker` | `GET /health` | ENABLED |
| conversion-worker | Python | 18089 | `conversion-worker` | `GET /health` | ENABLED |
| ingestion-worker | Python | 18088 | `ingestion-worker` | `GET /health` | ENABLED |
| retrieval | Java | 18082 | `retrieval` | `GET /health` | ENABLED |
| access | Java | 18081 | `access` | `GET /health` | ENABLED |
| web (frontend) | Next.js | 3000 | `web` | `GET /` | TEMPLATE — build blocked by pre-existing TS error |

To build and start all services:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

To start without the frontend (backend only):

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis admin workbench indexing document-service publishing-worker approval-service agent-review-worker conversion-worker ingestion-worker retrieval access
```

## Building Individual Images

```bash
# Shared Python image (used by all Python services)
docker build -t ekb-python:latest -f deploy/Dockerfile.python .

# Java services
docker build -t ekb-retrieval:latest -f deploy/Dockerfile.java --build-arg SERVICE_DIR=services/retrieval .
docker build -t ekb-access:latest -f deploy/Dockerfile.java --build-arg SERVICE_DIR=services/access .

# Frontend (requires fixing pre-existing TypeScript error first)
docker build -t ekb-web:latest --build-arg NEXT_PUBLIC_ADMIN_API_URL=http://localhost:18084 --build-arg NEXT_PUBLIC_WORKBENCH_API_URL=http://localhost:18083 -f apps/web/Dockerfile apps/web
```

## Environment Configuration

All configuration is via environment variables. Template: `deploy/.env.example`.

### Required for smoke test (minimum)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (SQLAlchemy format) |
| `DATABASE_JDBC_URL` | PostgreSQL connection string (JDBC format for Java services) |
| `ADMIN_JWT_SECRET` / `JWT_SECRET` | JWT signing key (smoke mode: `smoke-test-secret`) |
| `INDEXING_EMBEDDING_API_KEY` | SiliconFlow API key |
| `REDIS_PASSWORD` | Redis auth password |

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

- Kubernetes / Helm charts not implemented
- OAuth/IdP SSO not implemented
- Service-to-service auth (mTLS/SPIFFE) not implemented
- Load/concurrency testing not done
- Frontend production build currently fails due to a pre-existing TypeScript error in `apps/web/src/app/trash/page.tsx`
