# workbench-api 对外接口契约

## Inbound（workbench 接收的请求 — 给前端 + 下游回调）

### 认证
所有 `/workbench/*` 路由需要 JWT（Authorization: Bearer），`/internal/events/*` 需要 X-Service-Key。

### Auth
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/workbench/auth/me` | 当前用户信息（从 JWT 解析） | JWT |
| GET | `/workbench/health` | 健康检查 | 无 |
| GET | `/workbench/health/all` | 聚合下游健康状态 | 无 |

### Upload Sessions
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| POST | `/workbench/uploads` | 创建 upload session（201） | `uploader` |
| GET | `/workbench/uploads` | 列当前用户 uploads | JWT |
| GET | `/workbench/uploads/{id}` | 单 session 详情 | JWT |
| DELETE | `/workbench/uploads/{id}` | 删除 session（204） | JWT |
| POST | `/workbench/uploads/{id}/content` | 上传二进制内容 | JWT |

`POST /workbench/uploads` body:
```
collection_id, filename, mime_type, size_bytes,
selected_parser_profile_id(opt), parser_override_json(opt), access_scope_json(opt)
```

`POST /workbench/uploads/{id}/content` multipart:
```
file (binary), access_scope_json(opt form)
```

### Parser Profiles & Parse Preview
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/workbench/parser-profiles?collection_id=` | 列出可用 profiles | JWT |
| POST | `/workbench/parse-previews` | 触发沙盒预览（202） | `uploader` |
| GET | `/workbench/parse-previews/{id}` | 查询预览结果 | JWT |
| GET | `/workbench/parse-snapshots/{id}` | 查看 ParseSnapshot | JWT |
| GET | `/workbench/parse-snapshots/{id}/chunks?page=&page_size=` | 查看 snapshot chunks | JWT |

`POST /workbench/parse-previews` body:
```
upload_id, source_file_id, collection_id, tenant_id,
parser_profile_id, parser_override_json(opt), actor
```

### Chunks
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/workbench/chunks/{evidence_id}` | 单条 chunk 详情 | JWT |
| PATCH | `/workbench/chunks/{evidence_id}` | 发布后 chunk 编辑（202） | `chunk_editor` |

`PATCH` body: 任意 dict，传给 indexing 创建 ChunkRevision。

### Pre-publish Chunk Edits
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| POST | `/workbench/parse-snapshots/{id}/chunk-edits` | 创建 draft edit（201） | `chunk_editor` |
| GET | `/workbench/parse-snapshots/{id}/chunk-edits` | 列 snapshot 的 edits | JWT |
| PUT | `/workbench/chunk-edits/{id}` | 更新 edit | `chunk_editor` |
| DELETE | `/workbench/chunk-edits/{id}` | 删除 edit（204） | `chunk_editor` |
| POST | `/workbench/chunk-edits/{id}/submit` | 提交到 indexing | `chunk_editor` |

### Tickets & Agent Review
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/workbench/tickets` | 列表（projection 优先） | JWT |
| GET | `/workbench/tickets/{id}` | 单票详情（projection→approval fallback） | JWT |
| POST | `/workbench/tickets/{id}/decide` | Approve/Reject/Return | `reviewer` |
| GET | `/workbench/tickets/{id}/agent-review` | AgentReview 发现 | JWT |
| GET | `/workbench/tickets/{ticket_id}/workspace` | 聚合工作区 | JWT |

`POST /workbench/tickets/{id}/decide` body:
```
decision_request_id, action(approve/reject/return),
reason(opt), tenant_id, collection_id
```

### Task Projection
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/workbench/tasks` | 任务列表（projection） | JWT |
| GET | `/workbench/tasks/{upload_id}` | 单任务 | JWT |
| POST | `/workbench/tasks/{upload_id}/recover` | 手动恢复 stuck projection | JWT |

### Documents
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/workbench/documents` | 文档列表（projection） | JWT |

### Source Files
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/workbench/source-files/{id}/content` | 元数据+下载URL | JWT |
| GET | `/workbench/source-files/{id}/preview` | 预览信息 | JWT |

### Retrieval 验证
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| POST | `/workbench/retrieve` | 代理检索到 access | JWT |
| GET | `/workbench/query-runs` | 检索历史 | JWT |
| GET | `/workbench/query-runs/{id}` | 单条检索详情 | JWT |

`POST /workbench/retrieve` body:
```
query (min 1), collection_id, token_budget (default 4096),
max_results (default 10), budget_policy (default "balanced"),
application_profile_id (default "workbench_default"),
retrieval_profile_id(opt), debug (default "none")
```

### Collections / Retrieval Profiles（代理到 admin）
| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| GET | `/workbench/collections` | 列 collections | JWT |
| POST | `/workbench/collections` | 创建 collection | `knowledge_admin` |
| GET | `/workbench/retrieval-profiles` | 列 retrieval profiles | JWT |

### Events（下游回调）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/internal/events/{service}` | 接收事件（service∈intake,approval,indexing） |

请求: `list[dict]`，每个 event 由对应 adapter 转为 projection event。
响应:
```
{ "service": "intake", "received": 3, "adapted": 4,
  "applied": 3, "skipped": 1, "errors": 0,
  "details": [{"event_id":"ev1","applied":true}, ...] }
```
校验: `X-Service-Key` header，与 `WORKBENCH_EVENT_KEY_{INTAKE,APPROVAL,INDEXING}` 比对。

## Outbound（workbench 发出的请求）

| 方向 | 客户端 | 端点 | 说明 |
|------|--------|------|------|
| -> document-service | `DocumentServiceClient` | `POST /upload` | 二进制文件存储 |
| -> intake-pipeline | `IntakeClient` | `POST /internal/source-files` | 注册 source file |
| -> intake-pipeline | `IntakeClient` | `GET /internal/source-files/{id}` | 源文件详情 |
| -> intake-pipeline | `IntakeClient` | `GET /internal/intake-jobs/{id}` | job 状态 |
| -> intake-publishing | `IntakeClient` | `GET /internal/published-documents/{id}` | 发布文档详情 |
| -> services/indexing | `IndexingClient` | `POST /internal/parse-previews` | 触发沙盒预览 |
| -> services/indexing | `IndexingClient` | `GET /internal/parse-snapshots/{id}` | 查 ParseSnapshot |
| -> services/indexing | `IndexingClient` | `GET /internal/parse-snapshots/{id}/chunks` | 查 snapshot chunks |
| -> services/indexing | `IndexingClient` | `GET /internal/chunks` | ACL 过滤查 chunks |
| -> services/indexing | `IndexingClient` | `GET /internal/indexed-documents` | 索引文档状态 |
| -> services/indexing | `IndexingClient` | `POST /internal/parser-profiles/validate` | ParserProfile 校验 |
| -> services/indexing | `IndexingClient` | `POST /internal/chunks/{id}/revisions` | 创建 chunk revision |
| -> approval-service | `ApprovalClient` | `GET /internal/tickets` | 审批票列表 |
| -> approval-service | `ApprovalClient` | `GET /internal/tickets/{id}` | 单票详情 |
| -> approval-service | `ApprovalClient` | `POST /internal/tickets/{id}/decide` | 审批决策 |
| -> approval-service | `ApprovalClient` | `GET /internal/tickets/{id}/agent-review` | AgentReview |
| -> services/access | `AccessClient` | `POST /v1/retrieve` | 检索验证 |
| -> services/admin | `AdminClient` | `GET /admin/collections` | 列 collections |
| -> services/admin | `AdminClient` | `GET /admin/collections/{id}` | Collection 配置 |
| -> services/admin | `AdminClient` | `POST /admin/collections` | 创建 collection |
| -> services/admin | `AdminClient` | `GET /admin/parser-profiles` | Parser profile 列表 |
| -> services/admin | `AdminClient` | `GET /admin/retrieval-profiles` | Retrieval profile 列表 |

## 配置环境变量
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JWT_SECRET` | **强制** | JWT 签名密钥 |
| `JWT_ALGORITHM` | `HS256` | 签名算法 |
| `JWT_ISSUER` | `""` | JWT issuer 校验（空=不校验） |
| `JWT_AUDIENCE` | `""` | JWT audience 校验（空=不校验） |
| `AUTH_MODE` | `smoke` | 鉴权模式 |
| `INDEXING_BASE_URL` | `http://127.0.0.1:18080` | indexing 服务 |
| `INGESTION_WORKER_URL` / `INTAKE_BASE_URL` | `http://127.0.0.1:18085` | intake 服务 |
| `APPROVAL_BASE_URL` | `http://127.0.0.1:18087` | approval 服务 |
| `ADMIN_BASE_URL` | `http://127.0.0.1:18084` | admin 服务 |
| `ACCESS_BASE_URL` | `http://127.0.0.1:18181` | access 服务 |
| `DOCUMENT_SERVICE_BASE_URL` | `http://localhost:8006` | 文档存储服务 |
| `PUBLISHING_BASE_URL` / `PUBLISHING_WORKER_BASE_URL` | `http://127.0.0.1:18086` | publishing 服务 |
| `RETRIEVAL_BASE_URL` | `http://127.0.0.1:18182` | retrieval 服务 |
| `ACCESS_INTERNAL_API_KEY` | `""` | access 服务 server-side key |
| `WORKBENCH_EVENT_KEY_INTAKE` | `""` | intake 事件回调校验 |
| `WORKBENCH_EVENT_KEY_APPROVAL` | `""` | approval 事件回调校验 |
| `WORKBENCH_EVENT_KEY_INDEXING` | `""` | indexing 事件回调校验 |
| `DATABASE_URL` | `postgresql+psycopg2://...` | 数据库连接 |
| `DEFAULT_HTTP_TIMEOUT` | `30.0` | 下游 HTTP 超时(秒) |

## 错误码
| 错误码 | HTTP | 说明 |
|--------|------|------|
| `DOWNSTREAM_NOT_IMPLEMENTED` | 501 | 下游 API 暂不存在 |
| `DOWNSTREAM_UNAVAILABLE` | 503 | 下游不可达或超时 |
| `CONFLICT` | 409 | 资源冲突 |
| `UNAUTHORIZED` | 401 | 认证失败 |
| `FORBIDDEN` | 403 | 权限不足/无 collection 权限 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `IDEMPOTENCY_CONFLICT` | 409 | 幂等冲突 |

## 幂等设计
- `upload_id` 作为上传命令的 idempotency_key
- `upload_id + parser_profile_id + sha256(override)[:16]` 作为预览 idempotency_key
- `chunk_edit_id` 作为 chunk revision idempotency_key
- `decision_request_id` 作为审批决策 idempotency_key
- 投影事件按 `event_id` 幂等（duplicate event_id 完全忽略）
- 投影 upsert 按 `aggregate_version` 乐观锁（低版本不覆盖高版本）

## 角色与权限
- `uploader`: 上传文件、选择 parser profile、查看 ParseSnapshot、触发沙盒
- `chunk_editor`: 创建/更新/删除/提交 chunk edits、发布后 chunk revision
- `reviewer`: 查看审批列表/详情/AgentReview、Approve/Reject/Return
- `knowledge_admin`: 创建 collection
- 一个人可同时拥有多个 roles；只有 admin roles 没有 workbench roles 的用户不能登录

## Canonical Wire 映射
| Canonical | 旧名 | 说明 |
|-----------|------|------|
| `query` | `query_text` | 检索查询文本 |
| `token_budget` | `max_context_tokens` | token budget |
| `evidence_items` | `result_chunks` | 检索结果列表 |
| `doc_id` | `final_doc_id` | 文档 ID |
| `evidence_id` | `chunk_id` | chunk/evidence ID |
| `content` | `display_text` | 展示内容 |
