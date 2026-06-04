# services/workbench-api 最终设计

## 1. 定位

`services/workbench-api` 是 **Enterprise KnowledgeBase 平台的文档处理工作台**，面向文档处理人员、业务人员、审批人员。

它是 `workbench-ui` 前端**唯一的后端入口**。

核心原则只有两句：

- **在既有规则下处理内容**
- **不定义规则、不管理资源、不维持系统**

判定规则：

| 维度 | workbench | admin |
|------|-----------|-------|
| 操作对象 | 某份文档、某条 chunk、某个 ticket、某次导入任务 | parser profile、collection、检索策略、权限、索引、队列、审计 |
| 动作性质 | 用规则 | 改规则 |
| 影响范围 | 只到当前实例 | 影响后续同类对象或其他人 |

`workbench-api` 不是治理真相源。它不重新定义 collection 归属、不决定发布状态、不创建全局配置。它只消费已由 admin 定义好的规则，并在这些规则下处理具体内容。

核心价值：
- 文档上传与生命周期跟踪
- ParseSnapshot（解析快照：某份文件在某套 parser 配置下的解析结果冻结版）查看与 chunk（文本块：文档被切分后的最小检索单元）预览
- 上传时手动选择解析策略，或对单份文档做 parser profile 沙盒试跑（只选已有 profile，不创建全局 profile）
- chunk 人工编辑：发布前编辑 draft chunk，发布后发起 chunk revision 并由 indexing 重新入库替换
- AgentReview 结果查看：展示自动审核判断、风险证据、建议修复项，用于人工快速定位问题
- 审批工作台（Pending Ticket 列表、单票详情、Approve / Reject / Return）
- 任务状态聚合视图（上传 → intake job → ParseSnapshot → ticket 的完整链路）
- **检索验证**：代理调用 access 服务执行检索并记录 query run
- **Workspace 聚合**：单 ticket 工作区详情聚合（task + ticket + agent-review + chunk-edits + source-file）

## 2. 三方入口边界

| 入口 | 面向用户 | 核心场景 | 对应后端 |
|------|---------|---------|---------|
| `access` REST/MCP | 外部应用/AI Agent | 检索知识 | `services/access` |
| `workbench-api` | 文档处理人员/业务人员/审批人员 | 上传文档、预览 ParseSnapshot、调 parser 参数沙盒、chunk 确认、审批、检索验证 | `services/workbench-api` |
| `admin-console` | 平台管理员/运维 | 全局配置、质量评测、运维控制、override | `services/admin` |

## 3. 技术栈

- **单体 FastAPI**（Python）
- **REST**：所有操作（上传、查询、预览、审批决策、检索验证）
- **鉴权**：共享 `admin_users` 表 + JWT secret，本地验签
- **数据隔离**：query 前置过滤器，按 `tenant_id` + `allowed_collections` 过滤
- **Projection Store**：PostgreSQL 本地投影表，用于读性能优化和聚合视图
- **事件接收**：下游服务通过 `/internal/events/{service}` POST 事件驱动投影更新
- **后台协调**：`reconciliation_loop` 定时校验投影一致性

不引入 GraphQL。不引入 WebSocket/SSE（解析进度用轮询）。

### 3.1 契约基线

workbench 实施必须建立在已完成的 Contract Stabilization Gate 之上。所有新的 request/response、OpenAPI、examples 必须使用当前 canonical wire 字段：

| 概念 | Canonical wire |
|------|----------------|
| 检索查询文本 | `query` |
| token budget | `token_budget` |
| 检索结果列表 | `evidence_items` |
| 文档 ID | `doc_id` |
| evidence/chunk ID | `evidence_id` |
| 展示内容 | `content` |

禁止在新接口里重新引入 `query_text`、`max_context_tokens`、`result_chunks`、`final_doc_id`、`chunk_id`、`display_text` 作为 wire 字段。若 workbench 本地表或下游 adapter 仍要处理旧名，必须显式映射到 canonical wire，并有测试覆盖。

### 3.2 架构护栏

`services/workbench-api` 是 Human Workflow BFF + Projection Store，不是文档流程 owner。它只拥有人的工作区视图和编辑意图：

- `workbench_upload_sessions`
- `workbench_user_preferences`
- `workbench_chunk_edits`
- `workbench_query_runs`
- task/ticket/document/agent-review/chunk projection

它不拥有：

- source file
- intake job
- ParseSnapshot
- approval ticket
- AgentReview artifact
- published document
- indexed chunk
- chunk revision materialization result

护栏规则：

- 本地 `status` 都是 projection/cache，必须能从 owner 状态重建
- 所有跨服务写动作必须用 command 语义，带 `trace_id`、`idempotency_key`、`actor`
- owner API 失败时，本地 projection 不得标记成功
- chunk 修改产品上可以像直接编辑，架构上必须是 `ChunkEditIntent -> ChunkRevision -> materialized indexed chunk`
- workbench 不直接 patch active indexed chunk，不直接写 OpenSearch/Qdrant

## 4. 认证与鉴权

### 4.1 用户来源

用户账号统一由 `services/admin` 管理。`admin_users` 表是唯一的用户真相源。

`workbench-api` 不自建用户表，只读 `admin_users` 验证 JWT。

### 4.2 JWT 共享

- `services/admin` 签发 JWT，payload 含 `sub`、`email`、`roles`、`tenant_id`、`allowed_collections`（可配置 `iss`/`aud`）
- `workbench-api` 和 `admin` 共享 JWT secret（`JWT_SECRET` env var）；production mode 可通过 `JWT_ISSUER`/`JWT_AUDIENCE` 开启 issuer/audience 校验
- `workbench-api` 本地验签，不 RPC 调 admin；不提供 login 端点（login 在 admin 完成）

### 4.3 角色控制

`workbench-api` 只认以下 roles（代码中使用小写）：

| role | 权限 |
|------|------|
| `uploader` | 上传文件、选择允许的 parser profile、查看 ParseSnapshot、预览 chunk、触发沙盒试跑 |
| `chunk_editor` | 编辑发布前 draft chunk、对已发布 chunk 发起 revision 替换 |
| `reviewer` | 查看审批列表、看单票详情、查看 AgentReview 证据、Approve / Reject / Return |

一个人可以同时拥有多个 roles。如果用户只有 admin roles（`platform_admin`、`knowledge_admin` 等）而没有 workbench roles，则不能登录 workbench。

### 4.4 数据隔离

所有查询前置过滤：

- `tenant_id` 必须匹配 token 中的 tenant
- `collection_id` 必须在 token 的 `allowed_collections` 列表内

## 5. 操作模式

所有控制操作统一走三步：

1. **鉴权**：检查 JWT roles 和 collection 权限
2. **代理**：调下游服务的内部 API，绝不直接操作下游表或检索存储
3. **本地聚合**：把多下游结果串成前端需要的视图

所有会改变下游事实的操作都必须生成 command envelope：

```text
command_id
trace_id
idempotency_key
actor
tenant_id
collection_id
target_type
target_id
payload
```

`idempotency_key` 必须来自 workbench 本地稳定对象，例如 `upload_id`、`chunk_edit_id`、`decision_request_id`，不能使用随机重试 ID。

workbench 可以提供"直接编辑 chunk"的产品体验，但执行语义是：

- workbench 记录人的编辑意图和操作上下文
- `services/indexing` 创建 chunk revision、重算 embedding、重写 OpenSearch/Qdrant、替换旧 chunk、触发 retrieval cache 失效
- workbench 不直接 UPDATE indexed chunk 表，不直接写 OpenSearch，不直接写 Qdrant

如果下游 API 调用失败：
- 前端收到统一包装的错误码（如 `DOWNSTREAM_UNAVAILABLE`、`OP_TIMEOUT`、`CONFLICT`）
- 日志和 trace 中记录完整的下游失败原因

如果下游 API 暂时不存在，则该功能标记为"依赖下游 API，待补齐"。

## 6. 功能域（按代码实际实现）

### 6.1 文档上传与跟踪

- 接收文件上传（支持分片）
- 上传时选择 collection，并可选择该 collection 允许的 parser profile；未选择时使用 collection 默认策略
- 高权限用户可发起 per-document parser override，用于本次文档解析或沙盒预览，不创建全局 parser profile
- 生成 `upload_id`，本地创建 `workbench_upload_sessions`
- 上传内容时通过 `DocumentServiceClient` 调 `document-service` 的 `/upload` 存储二进制文件
- 内容上传成功后调 `intake-pipeline` 的 `/internal/source-files` 注册 source file
- 本地维护 `workbench_upload_sessions` 聚合状态
- 前端轮询 `GET /workbench/uploads/{id}` 看综合进度
- 下游代理：调 `document-service`（二进制存储）、调 `services/intake-pipeline`（source file / intake job 注册）

### 6.2 ParseSnapshot 查看与 chunk 预览

- 按 `source_file_id` 查看关联的 ParseSnapshot
- 展示 preview_text、outline、document_metadata
- chunk 列表查看（分页、按 section_path 分组）
- 单条 chunk 详情（wire 使用 `content`、metadata、page_spans；若下游内部仍叫 `display_text`，由 adapter 映射）
- 发布前展示 ParseSnapshot 中的 chunk preview；发布后展示 indexed chunk 与 chunk revision 历史
- 下游代理：调 `services/indexing` 的 `/internal/parse-snapshots/{id}`、`/internal/parse-snapshots/{id}/chunks` 和 `/internal/chunks`

### 6.3 Parser Profile 沙盒试跑

- 列出当前 collection 可用的 effective parser profiles（只读；控制面来源是 admin，运行时可执行视图由 indexing validate/canonicalize）
- 选某个已有 profile 对某份文档做实时预览
- 调 `services/indexing` 的 `/internal/parse-previews`
- 对比多个 profile 的预览结果
- **注意**：workbench 用户不能创建/编辑/删除 parser profile，只能选已有的用
- 下游代理：调 `services/admin`（collection 绑定、权限、可选 profile 列表）、调 `services/indexing`（profile 可执行校验、预览执行）

### 6.4 Chunk 人工编辑

workbench 的 chunk 相关 API、OpenAPI、examples 必须使用 canonical wire：

- `content` 对应旧的 `display_text`
- `evidence_id` 对应旧的 `chunk_id`
- `doc_id` 对应旧的 `final_doc_id`

新建 chunk edit / revision 接口不得直接暴露旧 wire 名。

workbench 支持两类 chunk 编辑：

1. **发布前编辑**
   - 基于 ParseSnapshot chunk preview 创建 `workbench_chunk_edits`
   - 支持 update / split / merge / delete / create
   - 通过 `POST /workbench/chunk-edits/{id}/submit` 提交到 indexing
   - 内部调用 `POST /internal/chunks/{evidence_id}/revisions`

2. **发布后编辑**
   - 用户在 indexed chunk 详情页直接修改内容、section_path、metadata 或发起 hide/delete
   - workbench 调 `services/indexing` 创建 `ChunkRevision`
   - indexing 重新计算 embedding，重写 OpenSearch + Qdrant，旧 chunk 标记为 superseded 或 `available_int=0`
   - indexing 激活新 revision 后通知/调用 `services/retrieval` 清理相关 cache

发布后 chunk 修改必须保留：

- base chunk id
- document/index revision
- edited_by、edit_reason
- before/after diff
- materialization status
- rollback/superseded_by 关系

#### 已实现的 chunk revision API（2026-05-28）

**workbench 端点**：
- `PATCH /workbench/chunks/{evidence_id}` — 发布后编辑，内部调用 indexing 创建 ChunkRevision
- `POST /workbench/chunk-edits/{chunk_edit_id}/submit` — 发布前编辑提交到 indexing

**indexing 端点**（由 workbench 调用）：
- `POST /internal/chunks/{evidence_id}/revisions` — 创建 revision（幂等）
- `GET /internal/chunk-revisions/{revision_id}` — 查询 revision（待补齐）
- `POST /internal/chunk-revisions/{revision_id}/materialize` — 物化 revision（待补齐）

**retrieval 端点**：
- `POST /internal/cache/purge` — 按 scope 清理检索缓存（待补齐）

### 6.5 审批工作台

- Pending Ticket 列表（支持按 collection、state 过滤；**优先读 SQL projection**，无 downstream fan-out）
- 单票详情：ParseSnapshot 预览 + agent review 结果 + approval audit log（**projection 优先，stale 时 fallback approval-service**）
- AgentReview 展示内容包括 decision、quality findings、risk flags、evidence anchors、model/version/prompt hash、suggested fixes、degraded/failure reason（**优先读 projection**）
- 操作：Approve / Reject / Return（含 reason 输入）
- 查看历史决策记录
- **注意**：override（对已决策 ticket 的人工覆盖）不在 workbench，在 admin
- 下游代理：调 `approval-service` 内部 API
- AgentReview artifact 的 owner 是 intake/approval 链路，workbench 只展示，不改写自动审核事实

### 6.6 任务状态聚合视图

workbench 本地维护 `workbench_task_projection` 表，把多下游状态串成一条线：

```
upload_session
  -> source_file (intake-pipeline)
  -> intake_job (intake-pipeline)
  -> ParseSnapshot (indexing)
  -> approval_ticket (approval-service)
  -> published_document (publishing domain)
```

前端只查 workbench 的聚合接口，不用自己串多个服务。

`workbench_task_projection.overall_status` 是 UI 聚合状态，不是流程事实源。它必须能从 source_file、intake_job、ParseSnapshot、approval_ticket、published_document 重新计算；下游事实变化时，以 owner 服务状态为准。

推荐实现方式：

```
status = derive(
  source_file_state,
  intake_job_state,
  parse_snapshot_state,
  ticket_state,
  published_document_state,
  index_build_state,
  active_index_version,
)
```

**状态推导优先级**（高到低）：

| 条件 | 推导 status | 说明 |
|------|------------|------|
| `published_document_state == "ARCHIVED"` | `archived` | 已归档 |
| `published_document_state == "RETRACTED"` | `retracted` | 已撤回 |
| `active_index_version` 存在 | `published` | 已有活跃索引版本 |
| `index_build_state == "BUILDING"` | `indexing` | 索引构建中 |
| `ticket_state == "approved"` | `approved` | 审批已通过，待发布/索引 |
| `ticket_state == "rejected"` | `rejected` | 审批已拒绝 |
| `ticket_state == "pending"` | `reviewing` | 审批中 |
| `intake_job_state == "FAILED"` | `failed` | 解析失败 |
| `intake_job_state in ("CREATED", "PARSING")` | `parsing` | 解析中 |
| `source_file_state == "READY"` | `uploading` | 文件已就绪，待解析 |
| 默认 | `uploading` | 初始状态 |

### 6.7 检索验证（新增）

workbench 提供检索验证功能，前端通过 JWT 调用 workbench，workbench 用 server-side API key 代理调用 `services/access`：

- `POST /workbench/retrieve` — 执行检索，记录到 `workbench_query_runs`
- `GET /workbench/query-runs` — 查询历史检索记录
- `GET /workbench/query-runs/{query_run_id}` — 单条检索详情

每个请求生成 `query_run_id` 和 `trace_id`，记录请求、响应、latency、状态。

### 6.8 Source File 代理（新增）

workbench 不存储原始二进制，只代理：

- `GET /workbench/source-files/{id}/content` — 返回 source file 元数据和下载 URL
- `GET /workbench/source-files/{id}/preview` — 返回预览信息（page_count、thumbnail_url 等）

通过 `IntakeClient` 调 `intake-pipeline` 的 `/internal/source-files/{id}`。

### 6.9 Workspace 聚合（新增）

- `GET /workbench/tickets/{ticket_id}/workspace` — 聚合单 ticket 工作区视图：
  - ticket 详情
  - task projection（上传链路）
  - agent review findings
  - chunk edits
  - source file 元数据

### 6.10 文档投影查询（新增）

- `GET /workbench/documents` — 从 SQL projection 查询文档列表，支持按 collection、document_state 过滤，分页排序

### 6.11 事件接收与投影更新（新增）

- `POST /internal/events/{service}` — 接收下游服务（intake/approval/indexing）的事件回调
- 事件写入 `workbench_projection_events`（append-only）
- `ProjectionProjector` 将事件应用到对应的投影表
- 后台 `reconciliation_loop` 定期校验投影一致性

## 7. 下游内部 API 依赖清单

workbench 的以下功能依赖下游服务暴露内部 API。如果 API 暂不存在，该功能标记为"待补齐"：

### 7.1 已实现的下游 API

| 功能 | 下游服务 | 内部 API | 状态 |
|------|---------|----------|------|
| 文件二进制上传 | `document-service` | `POST /upload` | **已实现** |
| 文件上传注册 | `intake-pipeline` | `POST /internal/source-files` | **已实现** |
| 上传任务状态 | `intake-pipeline` | `GET /internal/intake-jobs/{id}` | **已实现** |
| 源文件详情 | `intake-pipeline` | `GET /internal/source-files/{id}` | **已实现** |
| 已发布文档详情 | `intake-pipeline` | `GET /internal/published-documents/{id}` | **已实现** |
| 审批票列表 | `approval-service` | `GET /internal/tickets` | **已实现**（fallback） |
| 单票详情 | `approval-service` | `GET /internal/tickets/{id}` | **已实现**（fallback） |
| AgentReview artifact | `approval-service` | `GET /internal/tickets/{id}/agent-review` | **已实现**（fallback） |
| 审批决策 | `approval-service` | `POST /internal/tickets/{id}/decide` | **已实现** |
| 沙盒预览触发 | `services/indexing` | `POST /internal/parse-previews` | **已实现** |
| ParseSnapshot 查看 | `services/indexing` | `GET /internal/parse-snapshots/{id}` | **已实现** |
| chunk 查询 | `services/indexing` | `GET /internal/chunks` | **已实现** |
| 索引文档状态 | `services/indexing` | `GET /internal/indexed-documents` | **已实现** |
| ParserProfile 校验 | `services/indexing` | `POST /internal/parser-profiles/validate` | **已实现** |
| 发布后 chunk revision | `services/indexing` | `POST /internal/chunks/{id}/revisions` | **已实现** |
| 检索验证 | `services/access` | `POST /v1/retrieve` | **已实现** |
| Collection 配置 | `services/admin` | `GET /admin/collections/{id}` | **已实现** |
| ParserProfile 列表 | `services/admin` | `GET /admin/parser-profiles` | **已实现** |

### 7.2 待补齐的下游 API

以下 API 暂不存在或不稳定，workbench 调用时可能返回 `DOWNSTREAM_NOT_IMPLEMENTED`（HTTP 501）：

| 功能 | 下游服务 | 需要的内部 API |
|------|---------|--------------|
| ParseSnapshot chunk 预览 | `services/indexing` | `GET /internal/parse-snapshots/{id}/chunks` |
| chunk revision 查询 | `services/indexing` | `GET /internal/chunk-revisions/{revision_id}` |
| chunk revision 物化 | `services/indexing` | `POST /internal/chunk-revisions/{revision_id}/materialize` |
| retrieval cache 清理 | `services/retrieval` | `POST /internal/cache/purge` |

## 8. 本地数据模型

workbench 只维护本地工作区状态和人的编辑意图（不与其他服务共享写权）：

### 8.1 `workbench_upload_sessions`

```
upload_id          PK
user_id            FK -> admin_users.user_id
tenant_id
collection_id
source_file_id     nullable -> intake-pipeline
intake_job_id      nullable -> intake-pipeline
parse_snapshot_id  nullable -> indexing
ticket_id          nullable -> approval-service
selected_parser_profile_id nullable
parser_override_json nullable
status             uploading / parsing / reviewing / approved / rejected / published / failed
progress_pct       int (0-100)
filename
mime_type
size_bytes
error_message      nullable
access_scope_json  nullable
created_at
updated_at
```

`status` 是 UI 聚合状态，可以由下游 owner 状态重建，不作为 source file、approval 或 publish 的事实状态。

### 8.2 `workbench_user_preferences`

```
preference_id      PK
user_id            FK -> admin_users.user_id
preference_type    default_parser_profile / default_collection / view_mode
preference_value   JSON
created_at
updated_at
```

### 8.3 `workbench_chunk_edits`

```
chunk_edit_id      PK
tenant_id
collection_id
source_file_id
parse_snapshot_id  nullable
base_evidence_id
edit_scope         pre_publish / post_publish
operation          update / split / merge / delete / create / hide
content            nullable
vector_text        nullable
section_path       JSON nullable
metadata_patch     JSON nullable
citation_payload   JSON nullable
source_block_ids   JSON nullable
edit_reason
edited_by          FK -> admin_users.user_id
status             draft / submitted / materialized / active / rejected / failed
downstream_revision_id nullable -> indexing
created_at
updated_at
```

发布前 edit 在 approval/materialization 时由 indexing 合并；发布后 edit 立即转为 indexing `ChunkRevision`，由 indexing 负责重算 embedding、重写索引并替换旧 chunk。

### 8.4 `workbench_query_runs`（新增）

```
query_run_id       PK
tenant_id
user_id
collection_id
query              text
token_budget       int
request_json       JSON
access_response_json JSON
knowledge_context_json JSON
latency_ms         int
cache_hit          boolean
status             pending / success / failed
error_code         nullable
error_message      nullable
created_at
```

### 8.5 Projection 表（新增）

```
workbench_task_projection        — 任务聚合视图
workbench_ticket_projection      — 审批票缓存
workbench_document_projection    — 文档目录
workbench_agent_review_projection — AgentReview findings
workbench_chunk_projection       — Chunk 缓存
workbench_projection_events      — 事件日志（append-only）
workbench_projection_reconcile_runs — 协调运行记录
```

## 9. 事实所有权矩阵

| 对象 | 事实 owner | workbench 角色 | 写路径 |
|------|------------|----------------|--------|
| `Collection` | `services/admin` | 只读选择、按权限使用 | admin API |
| `ParserProfile` | 控制面 `services/admin`，运行时 `services/indexing` | 只读选择、per-document override | admin API + indexing preview API |
| `SourceFile` / `IntakeJob` | `intake-pipeline` | 上传、看进度 | intake internal API |
| `ParseSnapshot` | `services/indexing` | 预览、对比 | indexing internal API |
| `AgentReviewArtifact` | `intake-pipeline` / `approval-service` | 展示证据、辅助定位问题 | owner internal API |
| `ApprovalTicket` | `approval-service` | pending review、decide | approval internal API |
| `WorkbenchUploadSession` | `services/workbench-api` | UI 聚合投影 | workbench 本地表 |
| `WorkbenchChunkEdit` | `services/workbench-api` | 记录人工编辑意图 | workbench 本地表 + indexing API |
| `ChunkRevision` / indexed chunk replacement | `services/indexing` | 发起修改、查看结果 | indexing internal API |
| `PublishedDocument` | publishing domain in `intake-pipeline` | 只读结果 | intake/publishing internal API |
| `QueryRun` | `services/workbench-api` | 检索验证记录 | workbench 本地表 |
| `DocumentProjection` | `services/workbench-api` | 文档目录投影 | workbench 本地表（事件驱动） |

## 10. REST API 核心路由

```text
# 认证（login 在 admin service，workbench 仅验签）
GET  /workbench/auth/me             # 当前用户信息（从 JWT 解析）

# 文档上传与跟踪
POST   /workbench/uploads
GET    /workbench/uploads
GET    /workbench/uploads/{id}
DELETE /workbench/uploads/{id}
POST   /workbench/uploads/{id}/content   # 上传二进制内容

# ParseSnapshot 与 chunk
GET /workbench/parse-snapshots/{id}
GET /workbench/parse-snapshots/{id}/chunks
GET /workbench/chunks/{evidence_id}
PATCH /workbench/chunks/{evidence_id}                    # 发布后编辑，内部创建 indexing ChunkRevision

# Parser Profile 沙盒
GET    /workbench/parser-profiles          # 只读，返回当前 collection 可用 profiles 及 indexing canonical view
POST   /workbench/parse-previews           # 触发沙盒预览
GET    /workbench/parse-previews/{id}      # 查询预览结果

# 发布前 chunk edits
POST   /workbench/parse-snapshots/{id}/chunk-edits
GET    /workbench/parse-snapshots/{id}/chunk-edits
PUT    /workbench/chunk-edits/{id}
DELETE /workbench/chunk-edits/{id}
POST   /workbench/chunk-edits/{id}/submit  # 提交到 indexing

# 审批工作台
GET    /workbench/tickets                  # Pending Ticket 列表（优先读 projection）
GET    /workbench/tickets/{id}             # 单票详情（projection 优先，fallback approval）
GET    /workbench/tickets/{id}/agent-review # AgentReview 结果与证据（projection 优先）
POST   /workbench/tickets/{id}/decide      # Approve / Reject / Return

# 任务聚合
GET /workbench/tasks                       # 当前用户的任务列表（聚合视图，读 projection）
GET /workbench/tasks/{upload_id}           # 单任务完整链路（读 projection）

# Workspace 聚合
GET /workbench/tickets/{ticket_id}/workspace  # 单 ticket 工作区聚合

# Source File 代理
GET /workbench/source-files/{id}/content   # 源文件元数据 + 下载 URL
GET /workbench/source-files/{id}/preview   # 源文件预览信息

# 检索验证
POST /workbench/retrieve                   # 代理检索到 access 服务
GET  /workbench/query-runs                 # 检索历史
GET  /workbench/query-runs/{id}            # 单条检索详情

# 文档投影
GET /workbench/documents                   # 文档列表（读 projection）

# 事件接收（下游服务回调）
POST /internal/events/{service}            # service ∈ {intake, approval, indexing}

# 健康检查
GET /workbench/health
```

## 11. 与 packages/ragflow_runtime 的关系

`workbench-api` **绝不直接调用 `upstream/ragflow`，也不直接调用 `packages/ragflow_runtime`**。

所有解析/分块能力通过 `services/indexing` 间接接入：

```
workbench-api
  -> POST /internal/parse-previews  -> indexing
     -> ParsePreviewRunner -> RAGFlowAppRuntime -> packages/ragflow_runtime.rag_app.{parser_id}
  -> GET /internal/parse-snapshots/{id} -> indexing
     -> 返回已冻结的 ParseSnapshot
```

`packages/ragflow_runtime` 是本项目内受控 runtime package，由 `services/indexing` 封装使用；`upstream/ragflow` 只是来源隔离区/参考代码，不是 workbench 的设计依赖。

workbench 只消费 `ParseSnapshot`、chunk preview、indexed chunk 和 chunk revision 结果，不关心 runtime 内部细节。

## 12. 与 services/admin 的关系

```
admin-console  ->  admin  ->  管理全局配置（parser profile、collection、权限）
workbench-ui   ->  workbench-api ->  在已有规则下处理内容
```

- 用户账号由 admin 管理，workbench 只读验签
- collection 配置和默认绑定由 admin 定义，workbench 用户只能在允许的 collection 内操作
- parser profile 由 admin 管理；workbench 只读可用 profiles，并在触发预览/解析时由 indexing 按 canonical runtime view 执行
- 审批 override 在 admin，普通审批在 workbench

## 13. Agent 实施约束与验收标准

本设计交给实现 agent 执行时，必须按以下约束落地。禁止只做 workbench 本地状态闭环来绕过 intake、indexing、approval、admin 的 owner 边界。

### 13.1 Contracts-first

开始实现前必须先运行并确认项目级 Contract Stabilization Gate 仍为绿色：

```text
cd packages/contracts
uv run pytest tests/ -v

cd services/access
mvn test

cd services/retrieval
mvn test -Dtest='!RealSqliteIndexingRegistrySmokeTest'
```

任一 gate 失败时，先修契约，不得继续实现 workbench。

`services/workbench-api` 当前还没有独立 OpenAPI 文件，实施前必须先补：

- `contracts/openapi/workbench-api.yaml`
- upload/session、parser profile selection、parse preview、chunk edit、chunk revision、ticket detail、AgentReview artifact 的 request/response schema
- `contracts/examples/workbench_*.json`

所有跨服务 request/response 字段名以 `contracts/` 为准。service-local DTO 只能镜像 contracts，不得单独演化。
新增 workbench wire 字段必须遵守第 3.1 节 canonical wire；旧字段名只能作为内部持久化列或 adapter 输入输出，不得进入 OpenAPI/examples。

### 13.2 禁止的捷径

实现 agent 不得采用以下方式交付：

- 只在 `workbench_upload_sessions.status` 内模拟完整流程，不调用 intake/indexing/approval owner API
- 直接写 source file、approval ticket、published document、indexed chunk、OpenSearch 或 Qdrant
- 编辑 chunk 时只改 workbench 本地表，不创建 indexing `ChunkRevision`
- 上传选择 parser profile 时绕过 admin collection 权限和 indexing canonical runtime view
- 把 AgentReview 结果复制成 workbench 自己的事实源并允许修改
- 用 mock/stub 代替下游联调，却不留下 contract test、failure test 和明确的 pending API gate

### 13.3 必须拆分的交付阶段

Phase 0：契约补齐

- 新增 `contracts/openapi/workbench-api.yaml`
- 定义 `WorkbenchUploadSession`、`WorkbenchChunkEdit`、`ChunkRevisionRequest`、`AgentReviewView`、`WorkbenchTaskView`
- 为上传、选择 parser profile、ParseSnapshot chunk preview、发布前 edit、发布后 chunk revision、ticket detail 建 examples

Phase 1：上传与任务投影

- workbench 创建 upload session
- 调 document-service 存储二进制
- 调 intake 注册 source file / intake job
- 本地 session 只保存 UI projection 和下游 id 映射
- session status 可由 owner 状态重建
- upload command 使用 `upload_id` 作为 idempotency key

Phase 2：解析策略选择与预览

- workbench 从 admin 获取 collection 权限、默认绑定和可选 ParserProfile
- 调 indexing 获取/验证 canonical runtime view
- 上传时可选择 parser_profile_id；高级权限可带 per-document override
- 调 indexing parse preview，返回 ParseSnapshot / chunk preview
- parse preview command 使用 `upload_id + parser_profile_id + override_hash` 作为 idempotency key

Phase 3：AgentReview 与审批

- ticket 列表和详情来自 projection（approval-service fallback）
- AgentReview artifact 来自 projection（approval-service fallback）
- workbench 展示 decision、risk flags、quality findings、evidence anchors、suggested fixes
- approve/reject/return 只能调用 approval-service decide API

Phase 4：chunk 人工编辑

- 发布前 edit：创建 `workbench_chunk_edits`，approval/materialization 时交给 indexing 合并
- 发布后 edit：调用 indexing 创建 `ChunkRevision`
- indexing 完成 embedding、OpenSearch/Qdrant 重写、旧 chunk supersede、retrieval cache 失效
- workbench 只展示 revision 状态，不自行标记 indexed chunk 已替换
- chunk revision command 使用 `chunk_edit_id` 作为 idempotency key

Phase 5：检索验证与 Workspace 聚合（新增）

- `POST /workbench/retrieve` 代理到 access 服务，记录 query run
- `GET /workbench/query-runs` 查询本地检索历史
- `GET /workbench/tickets/{id}/workspace` 聚合多下游数据为单视图
- `GET /workbench/documents` 提供文档目录投影查询

### 13.4 联调验收

每个跨服务能力必须至少有一条契约测试和一条集成测试：

- Upload integration：workbench -> document-service -> intake，返回 source_file_id/intake_job_id，并能轮询 owner 状态
- Preview integration：workbench -> admin/indexing，选择 profile 后生成 ParseSnapshot
- Ticket integration：workbench -> approval，能拉 ticket detail 和 AgentReview artifact
- Pre-publish edit integration：chunk edit 能随 indexing materialization 入库
- Post-publish edit integration：已入库 chunk 修改后，indexing 创建新 revision、旧 chunk 下线、新 chunk 可检索
- Retrieval integration：workbench -> access，检索返回 knowledge_context 并记录 query run
- Failure test：任一下游 409/404/5xx，workbench 返回统一错误码，不把本地 projection 标成成功
- Authorization test：跨 tenant、无 collection 权限、无 `chunk_editor` / `reviewer` 权限必须 fail closed

### 13.5 Chunk 修改验收条件

发布后 chunk 修改不能只看 workbench API 返回 200，必须验证完整链路：

1. workbench 收到 `PATCH /workbench/chunks/{id}`
2. indexing 创建 `ChunkRevision`
3. indexing 重算 embedding
4. OpenSearch 新 record 可见
5. Qdrant 新 point 可见
6. 旧 chunk `available_int=0` 或 `superseded_by` 指向新 revision
7. retrieval cache 被 purge 或 profile/content epoch 更新
8. retrieval 查询不再返回旧内容
9. audit 记录包含 before/after、edited_by、edit_reason

### 13.6 契约对齐风险

当前项目仍处于 `JSON Schema 唯一真相源 + 本地镜像过渡` 状态。实施 workbench/admin 前，执行 agent 必须检查：

- 新增 OpenAPI/schema/example 是否落在 `contracts/`
- Python Pydantic 是否同步 `packages/contracts`
- Java access/retrieval 如需消费新字段，是否同步 local mirror 或补 contract test
- Jackson snake_case / camelCase 是否通过真实反序列化测试验证

不得因为 Python 侧能跑通，就认为 Java consumer 或跨服务 wire 契约已经对齐。

## 14. 实现记录（Implementation Notes）

本节记录已落地实现与待办状态，供后续维护参考。

### 14.1 已完成的交付

**Phase 0：契约补齐** — 已完成

- `contracts/openapi/workbench-api.yaml`：完整 OpenAPI 3.1.0 规范，覆盖所有 `/workbench/` 路由
- `contracts/schemas/WorkbenchUploadSession.schema.json`
- `contracts/schemas/WorkbenchChunkEdit.schema.json`
- `contracts/schemas/ChunkRevisionRequest.schema.json`
- `contracts/schemas/AgentReviewView.schema.json`
- `contracts/schemas/WorkbenchTaskView.schema.json`
- `contracts/examples/workbench_*.json`：8 个示例文件
- `packages/contracts/src/reality_rag_contracts/enums.py`：新增 `WorkbenchRole`（`uploader`, `chunk_editor`, `reviewer`）
- `packages/contracts/src/reality_rag_contracts/models.py`：新增 workbench Pydantic 模型
- `packages/persistence/src/reality_rag_persistence/models.py`：新增 `WorkbenchUploadSessionModel`、`WorkbenchUserPreferenceModel`、`WorkbenchChunkEditModel`

**Phase 1-5：服务骨架与功能实现** — 已完成

- `services/workbench-api/pyproject.toml`：依赖配置
- `services/workbench-api/src/workbench_api/main.py`：FastAPI 应用入口
- `services/workbench-api/src/workbench_api/deps.py`：JWT 验签、角色检查、`CurrentUser`
- `services/workbench-api/src/workbench_api/errors.py`：统一错误码（`DOWNSTREAM_NOT_IMPLEMENTED`、`DOWNSTREAM_UNAVAILABLE`、`CONFLICT` 等）
- `services/workbench-api/src/workbench_api/downstream_clients/`：async httpx 客户端（indexing、intake、approval、admin、access、document-service）
- `services/workbench-api/src/workbench_api/auth/routes.py`：`GET /workbench/auth/me`
- `services/workbench-api/src/workbench_api/upload_sessions/`：上传会话 CRUD + document-service 代理 + intake 代理
- `services/workbench-api/src/workbench_api/parser_selection/`：只读 parser profile 列表
- `services/workbench-api/src/workbench_api/parse_preview/`：沙盒预览代理
- `services/workbench-api/src/workbench_api/parse_snapshot/`：ParseSnapshot / chunk 代理
- `services/workbench-api/src/workbench_api/chunks/`：`GET /workbench/chunks/{id}`、`PATCH /workbench/chunks/{id}`（发布后 revision）
- `services/workbench-api/src/workbench_api/tickets/`：ticket 列表/详情/决策代理 + AgentReview 展示（projection 优先）
- `services/workbench-api/src/workbench_api/chunk_edits/`：发布前 chunk edit CRUD（本地表）+ 提交到 indexing
- `services/workbench-api/src/workbench_api/task_projection/`：任务聚合视图（读 projection）
- `services/workbench-api/src/workbench_api/workspace/`：Workspace 聚合路由
- `services/workbench-api/src/workbench_api/source_files/`：Source file content/preview 代理
- `services/workbench-api/src/workbench_api/commands/retrieval.py`：检索验证代理 + query run 记录
- `services/workbench-api/src/workbench_api/events/`：下游事件接收 + adapter
- `services/workbench-api/src/workbench_api/projections/`：SQL projection store + projector + reconciler + 读路由

**测试覆盖** — 已完成

- `services/workbench-api/tests/`：13 个测试文件，覆盖 auth、uploads、tickets、chunk-edits、chunk-revision、parse-previews、parse-snapshots、parser-profiles、task-projection、agent-review、agent-review-matching、approval-events、wire-drift-guard
- `packages/contracts/tests/test_schema_validation.py`：扩展 workbench schema 验证 + wire drift guard
- 所有 gate 当前通过：contracts、workbench-api

### 14.2 Downstream API 状态

#### 已实现的下游 API

| 功能 | 下游服务 | 内部 API |
|------|---------|----------|
| 文件二进制上传 | `document-service` | `POST /upload` |
| 文件上传注册 | `intake-pipeline` | `POST /internal/source-files` |
| 上传任务状态 | `intake-pipeline` | `GET /internal/intake-jobs/{id}` |
| 源文件详情 | `intake-pipeline` | `GET /internal/source-files/{id}` |
| 已发布文档详情 | `intake-pipeline` | `GET /internal/published-documents/{id}` |
| 审批票列表 | `approval-service` | `GET /internal/tickets` |
| 单票详情 | `approval-service` | `GET /internal/tickets/{id}` |
| 审批决策 | `approval-service` | `POST /internal/tickets/{id}/decide` |
| AgentReview artifact | `approval-service` | `GET /internal/tickets/{id}/agent-review` |
| 沙盒预览触发 | `services/indexing` | `POST /internal/parse-previews` |
| ParseSnapshot 查看 | `services/indexing` | `GET /internal/parse-snapshots/{id}` |
| chunk 查询 | `services/indexing` | `GET /internal/chunks` |
| 索引文档状态 | `services/indexing` | `GET /internal/indexed-documents` |
| ParserProfile 校验 | `services/indexing` | `POST /internal/parser-profiles/validate` |
| 发布后 chunk revision | `services/indexing` | `POST /internal/chunks/{id}/revisions` |
| 检索验证 | `services/access` | `POST /v1/retrieve` |
| Collection 配置 | `services/admin` | `GET /admin/collections/{id}` |
| ParserProfile 列表 | `services/admin` | `GET /admin/parser-profiles` |

#### 尚未实现的下游 API

以下 API 暂不存在，workbench 调用时返回 `DOWNSTREAM_NOT_IMPLEMENTED`（HTTP 501）：

| 功能 | 下游服务 | 需要的内部 API |
|------|---------|--------------|
| ParseSnapshot chunk 预览 | `services/indexing` | `GET /internal/parse-snapshots/{id}/chunks` |
| chunk revision 查询 | `services/indexing` | `GET /internal/chunk-revisions/{revision_id}` |
| chunk revision 物化 | `services/indexing` | `POST /internal/chunk-revisions/{revision_id}/materialize` |
| retrieval cache 清理 | `services/retrieval` | `POST /internal/cache/purge` |

### 14.3 架构合规检查清单

- [x] 不直接写 source file、intake job、ParseSnapshot、approval ticket、published document、indexed chunk
- [x] 不直接写 OpenSearch、Qdrant、Redis
- [x] 不创建全局 ParserProfile
- [x] 所有跨服务写动作带 command envelope（`command_id`、`trace_id`、`idempotency_key`、`actor`、`tenant_id`、`collection_id`、`target_type`、`target_id`、`payload`）
- [x] `idempotency_key` 稳定：`upload_id`（上传）、`upload_id + parser_profile_id + override_hash`（预览）、`chunk_edit_id`（chunk revision）
- [x] 使用 canonical wire：`query`、`token_budget`、`evidence_items`、`doc_id`、`evidence_id`、`content`
- [x] AgentReview 只读展示，不修改自动审核事实
- [x] 本地 `status` 为 UI 聚合投影，可由 owner 状态重建
- [x] 失败时返回统一错误码，不把本地 projection 标成成功
- [x] 角色检查 fail closed：`uploader`、`chunk_editor`、`reviewer`
- [x] 检索验证不暴露 access service 的 API key 到前端
- [x] Projection 读端点优先读 SQL，减少 downstream fan-out
- [x] 事件接收有 service key 校验，防止未授权写入
