# Backend API Contract — 企业知识库工作台

> RESTful HTTP JSON · Base: `/api/workbench` · Auth: Bearer JWT

---

## 目录

1. [全局规范](#1-全局规范)
2. [认证与元数据](#2-认证与元数据)
3. [知识库集合](#3-知识库集合)
4. [上传与任务](#4-上传与任务)
5. [工单与复核](#5-工单与复核)
6. [工单评论](#6-工单评论)
7. [Chunk 操作](#7-chunk-操作)
8. [文档库与生命周期](#8-文档库与生命周期)
9. [源文件预览](#9-源文件预览)
10. [检索验证](#10-检索验证)
11. [通知](#11-通知)
12. [系统管理](#12-系统管理)
13. [状态流转](#13-状态流转)
14. [错误码总表](#14-错误码总表)

---

## 1. 全局规范

### 1.1 通用请求头

| Header | 必填 | 值 |
|--------|------|----|
| `Authorization` | 是 | `Bearer <JWT>` |
| `Content-Type` | 否 | `application/json`（上传文件时 `multipart/form-data`） |
| `X-API-Key` | 条件 | 访问服务专用 |

### 1.2 通用成功响应
```json
{ "<resource>": { ... }, "items": [...], "total": 42 }
```

### 1.3 通用错误响应
```json
{ "code": "ERROR_CODE", "message": "Human-readable description", "detail": "..." }
```

### 1.4 通用错误码

| HTTP | Code | 含义 |
|------|------|------|
| 400 | `INVALID_INPUT` | 参数校验失败 |
| 401 | `UNAUTHORIZED` | Token 缺失或过期 |
| 403 | `FORBIDDEN` | 无权限 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 409 | `CONFLICT` | 资源冲突 |
| 501 | `NOT_IMPLEMENTED` | 功能未实现（前端展示 BackendGap） |
| 503 | `SERVICE_UNAVAILABLE` | 服务不可用 |

### 1.5 分页规范
```
?page=1&page_size=20  →  { items: [...], total: N, page: 1, page_size: 20 }
```

### 1.6 角色权限
| 角色 | 标识 | 权限范围 |
|------|------|---------|
| 操作员 | `operator` | 上传、查看工单、检索、查看文档 |
| 复核员 | `reviewer` | 审批、编辑 chunks |
| 管理员 | `knowledge_admin` | 以上 + 批量操作、API密钥、审计 |
| 超级管理员 | `platform_admin` | 以上 + 租户级配置 |

---

## 2. 认证与元数据

### `GET /workbench/auth/me`
**Response 200:**
```json
{ "user_id": "u_abc", "email": "...", "display_name": "张三", "roles": ["operator"], "tenant_id": "tnt_c", "allowed_collections": ["col_1"] }
```
**Errors:** 401 UNAUTHORIZED, 501 NOT_IMPLEMENTED

### `GET /workbench/health`
**Response 200:** `{ "service": "workbench-api", "status": "ok" }`

### `GET /workbench/health/all`
**Response 200:**
```json
{
  "workbench": { "status": "ok", "service": "workbench-api" },
  "services": { "admin": {"status":"ok"}, "access": {"status":"ok"}, "retrieval": {"status":"degraded"}, "ingestion": {"status":"ok"} },
  "all_healthy": false
}
```

---

## 3. 知识库集合

### `GET /workbench/collections?tenant_id=`
**Response 200:** `{ items: AdminCollection[], total: N }`

**AdminCollection 字段：**
`collection_id`, `tenant_id`, `name`, `description?`, `lifecycle_state`("active"|"archived"|"disabled"), `authority_level?`, `access_policy?`, `default_parser_profile_id?`, `default_retrieval_profile_id?`, `created_by`, `created_at`, `updated_by`, `updated_at`

### `POST /workbench/collections`
**Request:** `{ collection_id, tenant_id, name, description?, lifecycle_state, authority_level?, access_policy? }`
**Response 201:** `{ collection_id: "col_new" }`
**Errors:** 409 CONFLICT（ID重复）, 403 FORBIDDEN

### `PATCH /workbench/collections/:id`
**Request:** `{ name?, description?, lifecycle_state? }`
**Response 200:** `{ collection_id, updated_at }`

### `DELETE /workbench/collections/:id`
**Response 200:** `{ status: "deleted", collection_id }`
**Errors:** 409 HAS_ACTIVE_DOCUMENTS（有文档时）, 404 NOT_FOUND, 403 FORBIDDEN

### `GET /workbench/collections/:id`
**Response 200（含统计）:**
```json
{ "collection_id": "...", "name": "...", "lifecycle_state": "active", "stats": { "doc_count": 42, "total_chunks": 1538, "total_pages": 210, "last_upload_at": "...", "avg_chunks_per_doc": 36.6 } }
```

### `GET /workbench/collections/:id/documents?q=`
**Response 200:** 同文档库列表格式，过滤到该集合。

---

## 4. 上传与任务

### `POST /workbench/uploads`（timeout 120s）
**Request:**
```json
{ "collection_id", "filename", "mime_type", "size_bytes", "selected_parser_profile_id?", "parser_override_json?", "access_scope_json?" }
```
**Response 200:** `{ upload_id, status: "uploading" }`
**Errors:** 400 INVALID_INPUT（不支持格式）, 400 FILE_TOO_LARGE（>500MB）

### `POST /workbench/uploads/:id/content`
**Request:** `multipart/form-data`, field: `file`
**Response 200:** `{ upload_id, source_file_id?, status, progress_pct }`
**Errors:** 404 NOT_FOUND, 409 UPLOAD_ALREADY_HAS_CONTENT

### `POST /workbench/tasks/:id/cancel`
**Response 200:** `{ status: "cancelled", task_id }`
**Errors:** 409 TASK_ALREADY_FINAL（已终态）, 404 NOT_FOUND

### `GET /workbench/uploads[?collection_id=&status=]`
**Response 200:** `{ items: WorkbenchUploadSession[], total: N }`

### `GET /workbench/tasks[?collection_id=&status=&offset=&limit=&sort_by=&sort_order=]`
**Response 200:**
```json
{ "items": [{ "upload_id", "status", "progress_pct", "source_file_state?", "intake_job_state?", "parse_snapshot_state?", "ticket_state?", "published_document_state?", "filename", "collection_id", "created_at", "updated_at" }], "total": N }
```

**支持状态过滤值：** `uploading`, `parsing`, `reviewing`, `failed`, `cancelled`, `completed`

---

## 5. 工单与复核

### `GET /workbench/tickets[?collection_id=&status=&page=&page_size=]`
**Response 200:**
```json
{ "items": [{ "ticket_id", "collection_id", "status", "title?", "filename?", "priority?", "assignee_user_id?", "doc_id?", "source_file_id?", "created_at", "updated_at?" }], "total": N }
```

### `GET /workbench/tickets/:id`
**Response 200:** `TicketDetail`（含 `failure_code?`, `failure_stage?`, `next_action?`, `decision?`, `decision_reason?`, `decided_by?`）

### `POST /workbench/tickets/:id/decide`
**Request:**
```json
{ "decision_request_id": "dec_1718000000", "action": "APPROVE"|"REJECT"|"RETURN", "reason?": "...", "tenant_id", "collection_id" }
```
**Response 200:** `{ ticket_id, status: "approved"|"rejected"|"returned", decision: "approve"|"reject"|"return" }`
**Errors:** 409 ALREADY_DECIDED, 409 DECISION_REQUEST_ID_CONFLICT, 403 FORBIDDEN

### `POST /workbench/tickets/:id/transfer`
**Request:** `{ assignee_user_id, reason? }`
**Response 200:** `TicketDetail`
**Errors:** 400 SELF_TRANSFER, 404 ASSIGNEE_NOT_FOUND

### `GET /workbench/tickets/:id/workspace`
**Response 200（聚合视图）:**
```json
{
  "ticket_id",
  "ticket": WorkspaceTicketView|null,
  "document": WorkspaceDocumentView,
  "task": WorkspaceTaskView|null,
  "source_file": WorkspaceSourceFileView|null,
  "parse_snapshot": WorkspaceParseSnapshotView|null,
  "chunks": { items: ChunkView[], total: N },
  "chunk_edits": { items: WorkspaceChunkEditView[], total: N },
  "agent_review": WorkspaceAgentReviewView,
  "capabilities": WorkspaceCapabilitiesView,
  "projection_freshness": { ticket_projection_updated_at?, ticket_is_stale, document_projection_updated_at?, document_is_stale },
  "degraded_parts": string[],
  "trace_id": string
}
```

### `GET /workbench/documents/:id/workspace`
同 `WorkspaceDetailView` 结构，以 doc_id 为入口。

---

## 6. 工单评论

| Method | Endpoint | Request | Response |
|--------|----------|---------|----------|
| `GET` | `/workbench/tickets/:id/comments` | - | `{ items: TicketComment[], total: N }` |
| `POST` | `/workbench/tickets/:id/comments` | `{ content }` | `TicketComment` (201) |
| `PATCH` | `/workbench/comments/:id` | `{ content }` | `TicketComment` |
| `DELETE` | `/workbench/comments/:id` | - | 204 |

**TicketComment:** `{ comment_id, ticket_id, author_id, author_name?, author_email?, content, mentions?, created_at, updated_at? }`

---

## 7. Chunk 操作

### `GET /workbench/parse-snapshots/:id/chunks[?page=&page_size=]`
**Response 200:** `{ items: ChunkView[], total: N }`

**ChunkView:** `{ evidence_id, doc_id, content, vector_text?, section_path?[], page_spans?[{page_from, page_to}], chunk_type?, metadata? }`

### `PATCH /workbench/chunks/:evidence_id`
**Request:** `{ content?, vector_text?, section_path?[], edit_reason? }`

### `GET /workbench/chunk-edits?parse_snapshot_id=`
**Response 200:** `{ items: WorkspaceChunkEditView[], total: N }`

---

## 8. 文档库与生命周期

### `GET /workbench/documents[?collection_id=&document_state=&status=&offset=&limit=&order_by=&order_dir=]`
**Response 200:** `{ items: DocumentProjectionItem[], total: N }`

### `GET /workbench/documents/:id`
**Response 200:** `DocumentProjectionItem`

### `POST /workbench/documents/:id/archive`
**Request:** `{ reason }`
**Response 200:** `{ success, final_doc_id, new_state: "archived" }`

### `POST /workbench/documents/:id/retract`
**Request:** `{ reason }`
**Response 200:** `{ success, final_doc_id, new_state: "retracted" }`

### `POST /workbench/documents/:id/reindex`
**Request:** `{ reason, index_profile_id? }`
**Response 200:** `{ success, final_doc_id, new_state: "indexing", job_id? }`

### `POST /workbench/documents/batch/{archive|retract|reindex}`
**Request:** `{ doc_ids, reason, index_profile_id? }`
**Response 200:**
```json
{ "total": 2, "succeeded": 2, "failed": 0, "items": [{ "doc_id", "success", "new_state?", "error_code?", "error_message?" }] }
```

### `GET /workbench/dashboard`
**Response 200:** `{ stats: { today_uploads, pending_review_count, total_documents, stale_ratio }, recent_tickets: TicketItem[] }`

### `POST /workbench/documents/:id/share`
**Request:** `{ expires_in_hours?, password? }`
**Response 200:** `{ share_url, expires_at }`

---

## 9. 源文件预览

### `GET /workbench/source-files/:id/preview`
**Response 200:** `SourceFilePreviewView`（mime_type, page_count, preview_kind, preview_available）

### `GET /workbench/source-files/:id/preview/content`
**Response:** Binary blob（Content-Type 按实际文件类型）

### `GET /workbench/parse-snapshots/:id/source`
**Response:** Binary blob

---

## 10. 检索验证

### `POST /workbench/retrieve`
**Request:**
```json
{ "query", "collection_id", "retrieval_profile_id", "token_budget": 2000, "debug": "none"|"basic"|"full" }
```
**Response 200:**
```json
{
  "query_run_id", "knowledge_context": {}, "latency_ms": 342, "trace_id",
  "evidence_items": [{
    "collection_id", "doc_id", "evidence_id", "document_index_revision_id",
    "content", "section_path": [], "page_spans": [{"page_from", "page_to"}],
    "score": 0.92, "source_stage": "rerank", "why_selected": "..."
  }],
  "token_budget_used": 450
}
```
**Errors:** 400 MISSING_COLLECTION, 400 MISSING_RETRIEVAL_PROFILE, 400 EMPTY_QUERY, 503 RETRIEVAL_SERVICE_UNAVAILABLE

### `GET /workbench/query-runs[?limit=&offset=]`
**Response 200:** `{ items: [{ query_run_id, query, collection_id, retrieval_profile_id, created_at, latency_ms? }], total: N }`

---

## 11. 通知

| Method | Endpoint | Response |
|--------|----------|----------|
| `GET` | `/workbench/notifications` | `{ items: NotificationItem[], total: N, unread_count: N }` |
| `PATCH` | `/workbench/notifications/:id/read` | `{ notification_id, is_read }` |
| `POST` | `/workbench/notifications/read-all` | `{ count: N }` |
| `GET` | `/workbench/notifications/unread-count` | `{ count: N }` |

---

## 12. 系统管理

| 资源 | 端点 | 操作 |
|------|------|------|
| 检索配置 | `/workbench/retrieval-profiles` | CRUD + POST publish + POST clone |
| 解析策略 | `/workbench/parser-profiles` | CRUD + POST publish + POST clone |
| API 密钥 | `/workbench/api-keys` | CRUD + GET usage |
| 审计日志 | `/workbench/audit-logs` | GET（筛选分页）+ POST export（CSV/Excel） |

---

## 13. 状态流转

### 上传/任务
```
queued → uploading → uploaded → parsing → reviewing → approved → indexing → published
  ↓                    ↓           ↓           ↓
cancelled             failed      failed      failed
                      duplicate ───┘
```

### 工单
```
pending ──→ approved ──→ (自动发布)
    │──→ rejected ──→ (不入库)
    └──→ returned ──→ pending (重新编辑后)
```

### 文档生命周期
```
published ──→ archive ──→ archived (不可检索)
    │                        └→ restore ──→ published
    └──→ retract ──→ retracted
              └→ reindex ──→ indexing ──→ published
```

---

## 14. 错误码总表

| HTTP | code | 触发场景 |
|------|------|---------|
| 400 | `INVALID_INPUT` | 必填字段缺失 |
| 400 | `MISSING_COLLECTION` | 未选集合 |
| 400 | `EMPTY_QUERY` | 空查询 |
| 400 | `SELF_TRANSFER` | 转让给自己 |
| 400 | `FILE_TOO_LARGE` | 文件超限 |
| 401 | `UNAUTHORIZED` | Token 无效 |
| 403 | `FORBIDDEN` | 权限不足 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 404 | `ASSIGNEE_NOT_FOUND` | 受让人不存在 |
| 409 | `CONFLICT` | 创建冲突 |
| 409 | `ALREADY_DECIDED` | 重复审批 |
| 409 | `DECISION_REQUEST_ID_CONFLICT` | 决策幂等冲突 |
| 409 | `TASK_ALREADY_FINAL` | 取消已终态任务 |
| 409 | `HAS_ACTIVE_DOCUMENTS` | 删除非空集合 |
| 409 | `UPLOAD_ALREADY_HAS_CONTENT` | 重复上传文件 |
| 409 | `ALREADY_ARCHIVED` | 重复归档 |
| 501 | `NOT_IMPLEMENTED` | 功能未实现 |
| 503 | `SERVICE_UNAVAILABLE` | 服务离线 |
| 503 | `RETRIEVAL_SERVICE_UNAVAILABLE` | 检索服务离线 |
| 429 | `RATE_LIMITED` | 频率限制 |
