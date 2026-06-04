# Reality-RAG Workbench API

Document processing workbench for the Enterprise KnowledgeBase platform.

## Positioning

Workbench is a **Human Workflow BFF + Projection Store**. It does not own document processing truth; it orchestrates downstream services (intake, indexing, approval, access) and maintains local projections for UI state.

## Setup

项目使用 uv workspace，根目录执行 `uv sync` 即可自动安装所有依赖。

如需单独安装：

```bash
uv pip install -e services/workbench-api
```

## Run

```bash
uv run python -m uvicorn workbench_api.main:app --reload --port 8005
```

## Test

```bash
cd services/workbench-api && uv run pytest tests/ -v
```

## Architecture

- `auth/` - JWT validation (shared secret with admin)
- `upload_sessions/` - Upload tracking with document-service integration
- `parser_selection/` - Read-only parser profile listing (admin + indexing)
- `parse_preview/` - Sandbox preview via indexing
- `parse_snapshot/` - Snapshot/chunk proxy to indexing
- `chunks/` - Chunk detail and revision requests
- `tickets/` - Approval ticket proxy + projection reads
- `chunk_edits/` - Local edit intent storage
- `task_projection/` - Aggregated task views (SQL projection)
- `workspace/` - Ticket workspace detail aggregation
- `source_files/` - Source file content/preview proxy
- `commands/retrieval/` - Retrieval verification proxy to access service
- `events/` - Downstream service callback ingestion (intake/approval/indexing)
- `projections/` - SQL projection store + read routes (documents, tickets, tasks, agent-review, chunks, query-runs)
- `downstream_clients/` - HTTP clients for intake/indexing/approval/admin/access/document-service

## API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/workbench/health` | Health check | None |
| GET | `/workbench/auth/me` | Current user info | JWT |
| POST | `/workbench/uploads` | Create upload session | `uploader` |
| GET | `/workbench/uploads` | List upload sessions | JWT |
| GET | `/workbench/uploads/{id}` | Get upload session | JWT |
| DELETE | `/workbench/uploads/{id}` | Delete upload session | JWT |
| POST | `/workbench/uploads/{id}/content` | Upload file content | JWT |
| GET | `/workbench/parser-profiles` | List parser profiles | JWT |
| POST | `/workbench/parse-previews` | Create parse preview | `uploader` |
| GET | `/workbench/parse-previews/{id}` | Get parse preview | JWT |
| GET | `/workbench/parse-snapshots/{id}` | Get parse snapshot | JWT |
| GET | `/workbench/parse-snapshots/{id}/chunks` | Get snapshot chunks | JWT |
| GET | `/workbench/chunks/{evidence_id}` | Get chunk detail | JWT |
| PATCH | `/workbench/chunks/{evidence_id}` | Post-publish chunk edit | `chunk_editor` |
| POST | `/workbench/parse-snapshots/{id}/chunk-edits` | Create pre-publish edit | `chunk_editor` |
| GET | `/workbench/parse-snapshots/{id}/chunk-edits` | List pre-publish edits | JWT |
| PUT | `/workbench/chunk-edits/{id}` | Update pre-publish edit | `chunk_editor` |
| DELETE | `/workbench/chunk-edits/{id}` | Delete pre-publish edit | `chunk_editor` |
| POST | `/workbench/chunk-edits/{id}/submit` | Submit edit to indexing | `chunk_editor` |
| GET | `/workbench/tickets` | List tickets (projection) | JWT |
| GET | `/workbench/tickets/{id}` | Get ticket detail | JWT |
| POST | `/workbench/tickets/{id}/decide` | Approve/Reject/Return | `reviewer` |
| GET | `/workbench/tickets/{id}/agent-review` | AgentReview findings | JWT |
| GET | `/workbench/tickets/{ticket_id}/workspace` | Workspace aggregation | JWT |
| GET | `/workbench/tasks` | List task projections | JWT |
| GET | `/workbench/tasks/{upload_id}` | Get task projection | JWT |
| GET | `/workbench/documents` | List document projections | JWT |
| GET | `/workbench/source-files/{id}/content` | Source file content proxy | JWT |
| GET | `/workbench/source-files/{id}/preview` | Source file preview | JWT |
| POST | `/workbench/retrieve` | Retrieval verification | JWT |
| GET | `/workbench/query-runs` | List query runs | JWT |
| GET | `/workbench/query-runs/{id}` | Get query run detail | JWT |
| POST | `/internal/events/{service}` | Ingest downstream events | Service key |

## Downstream Dependencies

| Service | Client | Used For |
|---------|--------|----------|
| `document-service` | `DocumentServiceClient` | File upload (binary storage) |
| `intake-pipeline` | `IntakeClient` | Source files, intake jobs, published docs |
| `services/indexing` | `IndexingClient` | Parse snapshots, previews, chunks, revisions |
| `approval-service` | `ApprovalClient` | Tickets, decisions, agent review |
| `services/admin` | `AdminClient` | Collections, parser profiles |
| `services/access` | `AccessClient` | Retrieval verification |

## Pending Downstream APIs

The following downstream APIs may return `DOWNSTREAM_NOT_IMPLEMENTED` (HTTP 501) if not yet available on the target service:

| Service | API | Workbench Feature |
|---------|-----|-------------------|
| intake-pipeline | POST /internal/source-files | Upload registration |
| intake-pipeline | GET /internal/intake-jobs/{id} | Job status |
| intake-pipeline | GET /internal/source-files/{id} | Source file detail |
| approval-service | GET /internal/tickets | Ticket list fallback |
| approval-service | GET /internal/tickets/{id} | Ticket detail fallback |
| approval-service | POST /internal/tickets/{id}/decide | Decision submission |
| approval-service | GET /internal/tickets/{id}/agent-review | AgentReview fallback |
| services/indexing | GET /internal/parse-snapshots/{id}/chunks | Snapshot chunk preview |
| services/indexing | POST /internal/chunks/{id}/revisions | Chunk revision creation |
| services/admin | GET /admin/collections/{id} | Collection config |
| services/admin | GET /admin/parser-profiles | Parser profile list |
| services/access | POST /v1/retrieve | Retrieval verification |
| document-service | POST /upload | Binary file upload |

## Projection Store

Workbench maintains SQL projections for read performance:

- `workbench_task_projection` - Upload lifecycle aggregation
- `workbench_ticket_projection` - Ticket list/cache
- `workbench_document_projection` - Document catalog
- `workbench_agent_review_projection` - AgentReview findings
- `workbench_chunk_projection` - Chunk cache
- `workbench_query_runs` - Retrieval query history
- `workbench_projection_events` - Event log (append-only)

Projections are updated via `/internal/events/{service}` callbacks from downstream services and a background reconciliation loop.
