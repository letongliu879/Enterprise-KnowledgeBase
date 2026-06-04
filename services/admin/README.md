# Reality-RAG Admin Service

Admin control panel for the Enterprise KnowledgeBase platform.

## Overview

The admin service (`services/admin`) is a FastAPI-based monolith that provides the sole backend entry for the `admin-console` frontend. It manages:

- **Identity**: JWT-based authentication with pbkdf2_sha256 password hashing and session tracking
- **Collection Catalog**: CRUD for collections, lifecycle transitions, versioned profile bindings
- **Profile Registry**: Parser profiles and retrieval profiles with draft/published/retired states and immutable published versions
- **API Key Registry**: Key creation, rotation, disable/revoke with SHA-256 hashing (no plaintext storage)
- **Ops Audit**: Append-only audit log for all control actions
- **Document Lifecycle Ops**: Archive, retract, and reindex published documents via downstream services
- **Downstream Client Gates**: Explicit failure semantics when calling indexing/retrieval/access/publishing-worker services

## Architecture

```
services/admin/src/admin_service/
  main.py                 # FastAPI app, mounts all routers
  config.py               # Settings (JWT secret, downstream URLs, auth mode)
  deps.py                 # FastAPI dependencies (DB session, current_user, role checks)
  database.py             # Admin DB init (calls persistence create_all)
  errors.py               # Unified error codes
  identity/               # Login, logout, me
  collection_catalog/     # Collection CRUD, lifecycle, bindings
  profile_registry/       # Parser + retrieval profile CRUD, publish, transition
  api_key_registry/       # API key CRUD, rotate, disable, revoke
  ops_audit/              # Audit log write/query
  document_ops/           # Published document archive/retract/reindex
  downstream_clients/     # Indexing, retrieval, access, publishing-worker clients
```

## Setup

### Install dependencies

项目使用 uv workspace，根目录执行 `uv sync` 即可自动安装所有依赖（包括 workspace 内本地包）。

如需单独安装：

```bash
uv pip install -e packages/contracts -e packages/persistence -e services/admin
```

### Run tests

```bash
cd services/admin && uv run pytest tests/ -v
```

### Run the service

```bash
cd services/admin
ADMIN_JWT_SECRET=your-secret-here uv run python -m uvicorn admin_service.main:app --reload --port 18084
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_JWT_SECRET` | `change-me-in-production` | JWT signing secret |
| `ADMIN_JWT_EXPIRATION_HOURS` | `24` | JWT token lifetime |
| `ADMIN_SESSION_EXPIRATION_HOURS` | `168` | Session invalidation window |
| `ADMIN_JWT_ISSUER` | `""` | JWT issuer claim (production mode) |
| `ADMIN_JWT_AUDIENCE` | `""` | JWT audience claim (production mode) |
| `AUTH_MODE` | `smoke` | Authentication mode (`smoke` or `production`) |
| `DATABASE_URL` | `sqlite:///admin.db` | Database connection string |
| `INDEXING_BASE_URL` | `http://localhost:18082` | Indexing service URL |
| `RETRIEVAL_BASE_URL` | `http://localhost:18083` | Retrieval service URL |
| `ACCESS_BASE_URL` | `http://localhost:18081` | Access service URL |
| `PUBLISHING_WORKER_BASE_URL` | `http://localhost:18085` | Publishing worker URL |

## API Endpoints

### Health
- `GET /health` — Service health check

### Auth
- `POST /admin/auth/login` — Authenticate and receive JWT
- `POST /admin/auth/logout` — Invalidate session (TODO: full session invalidation)
- `GET /admin/auth/me` — Get current user

### Collections
- `GET /admin/collections?tenant_id=` — List collections
- `POST /admin/collections` — Create collection
- `GET /admin/collections/{collection_id}` — Get collection
- `PATCH /admin/collections/{collection_id}` — Update collection
- `POST /admin/collections/{collection_id}/lifecycle` — Transition lifecycle state
- `GET /admin/collections/{collection_id}/bindings` — List bindings
- `GET /admin/collections/{collection_id}/bindings/current` — Get current binding
- `POST /admin/collections/{collection_id}/bindings` — Create new binding version

### Parser Profiles
- `GET /admin/parser-profiles?state=` — List profiles
- `POST /admin/parser-profiles` — Create profile
- `GET /admin/parser-profiles/{parser_profile_id}` — Get profile
- `PATCH /admin/parser-profiles/{parser_profile_id}` — Update draft profile (409 if published)
- `POST /admin/parser-profiles/{parser_profile_id}/publish` — Publish profile (calls indexing validate first; 409 on validation failure)
- `POST /admin/parser-profiles/{parser_profile_id}/transition` — Transition state

### Retrieval Profiles
- `GET /admin/retrieval-profiles?state=` — List profiles
- `POST /admin/retrieval-profiles` — Create profile
- `GET /admin/retrieval-profiles/{retrieval_profile_id}` — Get profile
- `PATCH /admin/retrieval-profiles/{retrieval_profile_id}` — Update draft profile (409 if published)
- `POST /admin/retrieval-profiles/{retrieval_profile_id}/publish` — Publish profile (calls retrieval validate first; 409 on validation failure; syncs projection to retrieval runtime)
- `POST /admin/retrieval-profiles/{retrieval_profile_id}/transition` — Transition state

### API Keys
- `GET /admin/api-keys?tenant_id=&state=` — List keys
- `POST /admin/api-keys` — Create key (returns plaintext once)
- `GET /admin/api-keys/{api_key_id}` — Get key
- `PATCH /admin/api-keys/{api_key_id}` — Update key
- `POST /admin/api-keys/{api_key_id}/rotate` — Rotate key
- `POST /admin/api-keys/{api_key_id}/disable` — Disable key
- `POST /admin/api-keys/{api_key_id}/revoke` — Revoke key

### Ops Audit
- `GET /admin/ops/audit-log?actor_id=&target_type=&target_id=&tenant_id=&collection_id=&limit=&offset=` — Query audit log
- `POST /admin/ops/audit-log` — Query audit log (POST variant with request body)

### Document Lifecycle Ops
- `POST /admin/documents/{final_doc_id}/archive` — Archive published document
- `POST /admin/documents/{final_doc_id}/retract` — Retract published document
- `POST /admin/documents/{final_doc_id}/reindex` — Trigger reindex of published document

## Design Decisions

- **Shared database**: Admin tables live in the same PostgreSQL/SQLite database as other services, avoiding cross-service transaction complexity
- **Backward compatibility**: `ApiKeyRegistryModel` keeps both `max_context_tokens` (for existing Java services) and `token_budget_limit` (admin canonical wire)
- **Immutable published profiles**: Modifying a published profile creates a new version; the old version is retired
- **Validate-before-publish**: Publishing a profile calls the runtime owner (indexing/retrieval) validate endpoint first. Validation failure or downstream unavailability returns 409 and writes an ops_audit_log entry with `after_state=rejected`.
- **No mock/stub pretending success**: Downstream client gates return explicit error codes (`DOWNSTREAM_NOT_IMPLEMENTED`, `DOWNSTREAM_UNAVAILABLE`) when runtime owners are unreachable
- **Role-based access control**: `knowledge_admin` or `platform_admin` role required for all mutating operations
- **Document ops proxy**: Archive/retract/reindex operations proxy to publishing-worker and indexing services; admin never directly modifies downstream tables
