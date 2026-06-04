# Reality-RAG Admin Service

Admin control panel for the Enterprise KnowledgeBase platform.

## Overview

The admin service (`services/admin`) is a FastAPI-based monolith that provides the sole backend entry for the `admin-console` frontend. It manages:

- **Identity**: JWT-based authentication with bcrypt password hashing and session invalidation
- **Collection Catalog**: CRUD for collections, lifecycle transitions, versioned profile bindings
- **Profile Registry**: Parser profiles and retrieval profiles with draft/published/retired states and immutable published versions
- **API Key Registry**: Key creation, rotation, disable/revoke with SHA-256 hashing (no plaintext storage)
- **Ops Audit**: Append-only audit log for all control actions
- **Downstream Client Gates**: Explicit failure semantics when calling indexing/retrieval/access services

## Architecture

```
services/admin/src/admin_service/
  main.py                 # FastAPI app, mounts all routers
  config.py               # Settings (JWT secret, downstream URLs)
  deps.py                 # FastAPI dependencies (DB session, current_user)
  database.py             # Admin DB init (calls persistence create_all)
  errors.py               # Unified error codes
  identity/               # Login, logout, me
  collection_catalog/     # Collection CRUD, lifecycle, bindings
  profile_registry/       # Parser + retrieval profile CRUD
  api_key_registry/       # API key CRUD, rotate
  ops_audit/              # Audit log write/query
  downstream_clients/     # Indexing, retrieval, access clients
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
| `DATABASE_URL` | `sqlite:///admin.db` | Database connection string |
| `INDEXING_BASE_URL` | `http://localhost:18082` | Indexing service URL |
| `RETRIEVAL_BASE_URL` | `http://localhost:18083` | Retrieval service URL |
| `ACCESS_BASE_URL` | `http://localhost:18081` | Access service URL |

## API Endpoints

### Auth
- `POST /admin/auth/login` — Authenticate and receive JWT
- `POST /admin/auth/logout` — Invalidate session
- `GET /admin/auth/me` — Get current user

### Collections
- `GET /admin/collections` — List collections
- `POST /admin/collections` — Create collection
- `GET /admin/collections/{id}` — Get collection
- `PATCH /admin/collections/{id}` — Update collection
- `POST /admin/collections/{id}/lifecycle` — Transition lifecycle state
- `GET /admin/collections/{id}/bindings` — List bindings
- `GET /admin/collections/{id}/bindings/current` — Get current binding
- `POST /admin/collections/{id}/bindings` — Create new binding version

### Parser Profiles
- `GET /admin/parser-profiles` — List profiles
- `POST /admin/parser-profiles` — Create profile
- `GET /admin/parser-profiles/{id}` — Get profile
- `PATCH /admin/parser-profiles/{id}` — Update draft profile
- `POST /admin/parser-profiles/{id}/publish` — Publish profile (calls indexing validate first; 409 on validation failure)
- `POST /admin/parser-profiles/{id}/transition` — Transition state

### Retrieval Profiles
- Same pattern as parser profiles under `/admin/retrieval-profiles`
- `POST /admin/retrieval-profiles/{id}/publish` — Publish profile (calls retrieval validate first; 409 on validation failure)

### API Keys
- `GET /admin/api-keys` — List keys
- `POST /admin/api-keys` — Create key (returns plaintext once)
- `GET /admin/api-keys/{id}` — Get key
- `PATCH /admin/api-keys/{id}` — Update key
- `POST /admin/api-keys/{id}/rotate` — Rotate key
- `POST /admin/api-keys/{id}/disable` — Disable key
- `POST /admin/api-keys/{id}/revoke` — Revoke key

### Ops Audit
- `GET /admin/ops/audit-log` — Query audit log
- `POST /admin/ops/audit-log` — Query audit log (POST variant)

## Design Decisions

- **Shared database**: Admin tables live in the same PostgreSQL/SQLite database as other services, avoiding cross-service transaction complexity
- **Backward compatibility**: `ApiKeyRegistryModel` keeps both `max_context_tokens` (for existing Java services) and `token_budget_limit` (admin canonical wire)
- **Immutable published profiles**: Modifying a published profile creates a new version; the old version is retired
- **Validate-before-publish**: Publishing a profile calls the runtime owner (indexing/retrieval) validate endpoint first. Validation failure or downstream unavailability returns 409 and writes an ops_audit_log entry with `after_state=rejected`.
- **No mock/stub pretending success**: Downstream client gates return explicit error codes (`DOWNSTREAM_NOT_IMPLEMENTED`, `DOWNSTREAM_UNAVAILABLE`) when runtime owners are unreachable
