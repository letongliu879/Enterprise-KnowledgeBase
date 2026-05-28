# Reality-RAG Workbench API

Document processing workbench for the Enterprise KnowledgeBase platform.

## Positioning

Workbench is a **Human Workflow BFF + Projection Store**. It does not own document processing truth; it orchestrates downstream services (intake, indexing, approval) and maintains local projections for UI state.

## Setup

```bash
cd services/workbench-api
py -3.14 -m pip install -e ".[dev]"
```

## Run

```bash
py -3.14 -m uvicorn workbench_api.main:app --reload --port 8005
```

## Test

```bash
py -3.14 -m pytest tests/ -v
```

## Architecture

- `auth/` - JWT validation (shared secret with admin)
- `upload_sessions/` - Upload tracking with intake integration
- `parser_selection/` - Read-only parser profile listing
- `parse_preview/` - Sandbox preview via indexing
- `parse_snapshot/` - Snapshot/chunk proxy to indexing
- `chunks/` - Chunk detail and revision requests
- `tickets/` - Approval ticket proxy
- `chunk_edits/` - Local edit intent storage
- `task_projection/` - Aggregated task views
- `downstream_clients/` - HTTP clients for intake/indexing/approval/admin

## Pending Downstream APIs

The following downstream APIs are not yet implemented. Workbench returns `DOWNSTREAM_NOT_IMPLEMENTED`:

| Service | API |
|---------|-----|
| intake-pipeline | POST /internal/source-files |
| intake-pipeline | GET /internal/intake-jobs/{id} |
| intake-pipeline | GET /internal/source-files/{id} |
| approval-service | GET /internal/tickets |
| approval-service | GET /internal/tickets/{id} |
| approval-service | POST /internal/tickets/{id}/decide |
| approval-service | GET /internal/tickets/{id}/agent-review |
| services/admin | GET /internal/collections/{id} (internal) |
| services/indexing | GET /internal/parse-snapshots/{id}/chunks |
| services/indexing | POST /internal/chunks/{id}/revisions |
