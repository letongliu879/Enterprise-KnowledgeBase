# intake-pipeline 对外接口契约

## Inbound（intake-pipeline 接收的请求）

### document-service API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | 上传文件（multipart），需 `collection_id` + `visibility` |
| POST | `/internal/upload-sessions` | 创建上传 session |
| POST | `/internal/upload-sessions/{id}/complete` | 完成上传，返回生成的 source_files |
| POST | `/internal/object-blobs/get-or-create` | 按 content_hash 获取或创建 object blob |
| POST | `/internal/object-blobs/{id}/gc` | GC 无引用 object blob |
| GET | `/internal/source-files/{id}` | 查询 source file 状态与元数据 |
| POST | `/internal/source-files` | 注册 source file（command 语义，带 idempotency） |
| POST | `/internal/source-files/{id}/claim` | claim source file（`{ "job_id": "..." }`） |
| POST | `/internal/source-files/{id}/mark-consumed` | 标记已消费（`{ "job_id": "..." }`） |
| POST | `/internal/source-files/{id}/mark-cleanable` | 标记可清理（`{ "job_id": "..." }`） |
| POST | `/internal/source-files/{id}/start-scan` | 启动恶意扫描 |
| POST | `/internal/source-files/{id}/complete-scan` | 完成恶意扫描 |
| POST | `/internal/source-files/{id}/release-claim` | 释放 claim |
| POST | `/internal/source-files/{id}/gc` | GC source file |
| POST | `/internal/dedup-check` | 重复检查（`{ "content_hash", "collection_id" }`） |
| GET | `/internal/source-files/{id}/preview` | 查询 source preview 元数据 |
| GET | `/internal/source-files/{id}/preview/content` | 读取 source preview 内容流（可返回 preview_url 的代理流） |

### intake-orchestrator API (ingestion-worker)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/metrics` | Prometheus metrics |
| POST | `/internal/ingestion/convert` | 提交转换任务（`ConversionRequest`） |
| GET | `/internal/intake-jobs/{id}` | 查询 intake job 状态 |

### conversion-worker API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/internal/conversion/run` | 执行转换（`ConversionRunRequest`） |
| POST | `/internal/source-previews/render` | 为 source file 生成或复用 preview 资产，返回 preview descriptor |
| GET | `/internal/source-previews/{source_file_id}/content` | 读取 preview 资产内容流 |

`ConversionRunRequest`:
```
intake_job_id, collection_id, source_file_path, tenant_id,
collection_authority_level, index_version,
existing_published_doc_id_by_source_hash (opt),
latest_version_by_logical_id (opt)
```

`POST /internal/source-previews/render` body:
```
source_file_id, collection_id, source_file_path, filename, mime_type
```

返回：
```
source_file_id, filename, mime_type,
preview_available, preview_status, preview_kind,
preview_mime_type, preview_url, thumbnail_url, page_count
```

语义约束：
- 该接口是 preview asset 的 owner 入口；可同步生成，也可命中已有缓存
- `preview_url` 指向 conversion-worker 自己的内容端点；上游如 `document-service` 可代理重写为自己的 `/internal/source-files/{id}/preview/content`
- `preview_status=ready` 时，`preview_url` 必须可读
- `preview_status=failed` 时，应返回 machine-readable 的失败原因（至少写入日志）
- `preview_status=unsupported` 时，不得用 `canonical_md` / `preview_text` 冒充 Source

### agent-review-worker API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/internal/review/run` | 执行审核（`ReviewRunRequest`） |

`ReviewRunRequest`:
```
intake_job_id, collection_id, preliminary_doc_id, logical_document_id,
canonical_content, collection_authority_level, review_model
```

### approval-service API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/internal/approval/system-decide` | 纯函数：从 quality report + agent review 判定 publish_status |
| POST | `/internal/approval/auto-approve` | 系统自动批准，生成 final_doc_id |
| POST | `/internal/approval/auto-reject` | 系统自动拒绝 |
| POST | `/internal/approval/pending` | 创建人工审批工单 |
| POST | `/internal/approval/{id}/approve` | 人工批准 |
| POST | `/internal/approval/{id}/reject` | 人工拒绝 |
| POST | `/internal/approval/{id}/return` | 人工打回指定阶段 |
| POST | `/internal/approval/{id}/expire` | 工单超时关闭 |
| GET | `/internal/approval/{intake_job_id}/history` | 查询工单历史 |
| GET | `/internal/tickets` | 列表查询（filter by tenant_id/collection_id/state） |
| GET | `/internal/tickets/{id}` | 查询工单详情 |
| POST | `/internal/tickets/{id}/decide` | 决策工单（idempotent by idempotency_key） |
| GET | `/internal/tickets/{id}/agent-review` | 查询 agent review artifact |

### publishing-worker API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/internal/publishing/persist` | 持久化文档与策略（`PersistRequest`） |
| GET | `/internal/published-documents/{final_doc_id}` | 查询已发布文档 |
| POST | `/internal/published-documents/{id}/archive` | 归档文档 |
| POST | `/internal/published-documents/{id}/retract` | 撤回文档 |
| POST | `/internal/published-documents/{id}/deprecate` | 标记 deprecated |
| POST | `/internal/published-documents/{id}/reindex` | 重新索引 |

### indexing-service API (intake-pipeline facade)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/internal/indexing/run` | 执行索引构建（`IndexJobRequest`） |
| POST | `/internal/indexing/activate` | 激活索引版本（`IndexSwitchRequest`） |
| POST | `/internal/indexing/rollback` | 回滚索引版本（`IndexSwitchRequest`） |

## Outbound（intake-pipeline 发出的请求）

| 方向 | 端点 | 说明 |
|------|------|------|
| -> indexing | POST /internal/parse-previews | 请求预解析（`ParsePreviewRequested`） |
| -> indexing | POST /internal/index-jobs | 提交索引构建（`IndexBuildRequestedCommand`） |
| -> indexing | POST /internal/index-versions/{id}/activate | 激活索引版本 |
| -> retrieval | POST /internal/index-projections/sync | 同步 index projection（生命周期变更时） |
| -> workbench | POST /internal/events/{service} | 转发事件到 workbench 投影 |

## 关键数据模型

### Source Preview Asset
`preview_status = pending | ready | failed | unsupported`

推荐返回字段：
```
source_file_id, filename, mime_type,
preview_available, preview_status, preview_kind,
preview_url, thumbnail_url, page_count, preview_mime_type
```

语义约束：
- `preview_kind` 表示前端消费的正式预览载体，而不是原始文件后缀
- `preview_available=true` 仅表示存在可消费的 preview 资产
- `preview_status=ready` 时，`preview_url` 或 `preview/content` 必须可读
- `preview_status=unsupported` 时，前端应退回 Download
- `canonical_md` / `preview_text` 不得作为 Source 预览的替代物
- `document-service` 是 source file 对外读取入口，但不是 preview 资产 owner；对于 Office 等非原生可预览格式，必须委托 `conversion-worker`

### SourceFileState
`UPLOADING -> UPLOADED -> SCANNING -> READY -> CLAIMED -> CONSUMED -> CLEANABLE -> CLEANED`
任意非终态 -> `FAILED`

### IntakeJobState
`CREATED -> CONVERSION_QUEUED -> CONVERSION_RUNNING -> CONVERSION_SUCCEEDED -> REVIEW_QUEUED -> REVIEW_RUNNING -> REVIEW_SUCCEEDED -> APPROVAL_REQUESTED -> AWAITING_APPROVAL -> APPROVAL_DECIDED -> PUBLISH_QUEUED -> PUBLISH_RUNNING -> PUBLISHED`
终态: `PUBLISHED / REJECTED / FAILED / CANCELLED / EXPIRED`
打回路径: `AWAITING_APPROVAL -> APPROVAL_DECIDED(return) -> CONVERSION_QUEUED / REVIEW_QUEUED`

### ApprovalTicketState
`SYSTEM_DECIDED`
`PENDING -> APPROVED / REJECTED / RETURNED / EXPIRED`

### PublishState
`PUBLISH_CREATED -> ASSET_WRITING -> ASSET_WRITTEN -> PERSISTING -> PERSISTED -> INDEXING -> INDEXED -> PUBLISH_SUCCEEDED`
任意阶段 -> `PUBLISH_RETRY_SCHEDULED / PUBLISH_FAILED`

### PublishedDocumentState
`PUBLISHED -> ARCHIVED / DEPRECATED / RETRACTED / REINDEXING`

### StageName 枚举
`conversion`, `agent_review`, `publishing`

### 核心 ID 前缀
| ID | 前缀 | 生成方 |
|----|------|--------|
| upload_id | `upl_` | document-service |
| source_file_id | `src_` | document-service |
| object_id | `obj_sha256_` | document-service |
| intake_job_id | `job_` | orchestrator |
| stage_attempt_id | `att_` | orchestrator |
| ticket_id | `atck_` | approval-service |
| publish_id | `pub_` | orchestrator |
| trace_id | `trc_` | 入口生成，链路透传 |

### 存储路径规范
```
collections/{collection_id}/docs/{final_doc_id}/canonical.md
collections/{collection_id}/docs/{final_doc_id}/sanitized.md
collections/{collection_id}/docs/{final_doc_id}/metadata.json
collections/{collection_id}/docs/{final_doc_id}/quality_report.json
collections/{collection_id}/docs/{final_doc_id}/review_report.json
```

推荐补充 preview 资产路径：
```
collections/{collection_id}/source-files/{source_file_id}/preview/preview.pdf
collections/{collection_id}/source-files/{source_file_id}/preview/thumbnail.png
collections/{collection_id}/source-files/{source_file_id}/preview/pages/{n}.png
collections/{collection_id}/source-files/{source_file_id}/preview/preview.html
```

推荐运行时落盘路径：
```
${REALITY_RAG_INTAKE_RUNTIME_DIR}/source-preview/{source_file_id}/preview.pdf
${REALITY_RAG_INTAKE_RUNTIME_DIR}/source-preview/{source_file_id}/preview.html
${REALITY_RAG_INTAKE_RUNTIME_DIR}/source-preview/{source_file_id}/manifest.json
```

## 配置环境变量

| 变量 | 说明 |
|------|------|
| `DOCUMENT_SERVICE_URL` | document-service HTTP 地址 |
| `APPROVAL_SERVICE_URL` | approval-service HTTP 地址 |
| `INDEXING_SERVICE_URL` | indexing-service HTTP 地址 |
| `RETRIEVAL_SERVICE_URL` | retrieval-service HTTP 地址（生命周期同步用） |
| `WORKBENCH_API_BASE_URL` | workbench 事件接收地址 |
| `WORKBENCH_EVENT_KEY_{SERVICE}` | workbench event 认证 key |
| `OUTBOX_POLL_INTERVAL_SECONDS` | outbox 轮询间隔（默认 5s） |
| `REALITY_RAG_INTAKE_RUNTIME_DIR` | intake 运行时资产目录 |
| `DOCUMENT_STAGING_DIR` | document-service 临时文件目录 |
| `APP_ENV` | 环境名称（production 时预加载 indexing backend） |

## 错误码与幂等

| error_code | retryable | HTTP |
|------------|-----------|------|
| `DOCUMENT_HASH_MISMATCH` | false | 400 |
| `DOCUMENT_TOO_LARGE` | false | 413 |
| `SOURCE_FILE_NOT_READY` | false | 409 |
| `SOURCE_FILE_ALREADY_CLAIMED` | false | 409 |
| `CONVERSION_UNSUPPORTED_TYPE` | false | 422 |
| `CONVERSION_TIMEOUT` | true | 504 |
| `REVIEW_PROVIDER_TIMEOUT` | true | 504 |
| `REVIEW_SCHEMA_INVALID` | true | 502 |
| `APPROVAL_TICKET_NOT_PENDING` | false | 409 |
| `PUBLISH_INDEX_UNAVAILABLE` | true | 503 |
| `CONFIG_VERSION_NOT_FOUND` | false | 500 |

幂等规则：
- 所有写操作必须支持 `Idempotency-Key`
- outbox event 通过 `event_id` 去重
- stage task 通过 `stage_task_id` 幂等执行（DB lease 机制）
- index build 通过 `idempotency_key` 幂等
- publish 通过 `publish_id` 和 `final_doc_id` unique 约束保证幂等
- index projection sync 带 `command_id`（UUID），retrieval 侧幂等
- cache purge 和 lifecycle sync 为 fail-open：目标不可达时只 warning 不阻断
