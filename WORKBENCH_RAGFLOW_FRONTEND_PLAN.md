# Workbench Frontend Overall Plan

## 1. 背景与结论

当前 `apps/web` 的 workbench 页面是手写拼装出来的前端壳子，已经暴露出几个结构性问题：

- 前端同时知道 `admin`、`workbench-api`、`access`、`retrieval`，后端入口不集中。
- workbench 列表/任务状态存在临时查询多个下游服务并组装视图的倾向。
- 文档工作台缺少成熟的“原始文档 + chunk 对照编辑”体验。
- AgentReview 目前不能清楚表达“哪里有问题、有什么问题、怎么改”。
- 继续补当前页面不能从根上解决体验和架构问题。

结论：

保留我们的多页前端，但把“工作台页”改为基于 RAGFlow 现有文档/chunk 工作台页面迁移而来。`workbench-api` 作为唯一前端入口，负责 BFF、SQL projection、权限校验和下游 adapter。

## 2. 目标页面结构

`apps/web` 仍然是我们的前端应用，不整体替换成 RAGFlow。页面职责如下：

```text
/upload
  自动上传页
  批量上传、权限范围、上传进度、任务投影。

/review
  待审列表页
  从 workbench SQL projection 查询 ticket/task 列表。

/workbench/[ticketId]
  工作台页
  基于 RAGFlow 文档/chunk 页面迁移。
  增加 AgentReview、审批、chunk edit draft。

/retrieval
  检索验证页
  前端只调用 workbench-api，由 workbench-api 转接 access。

/collections
  集合/知识库概览页
  展示 collection、profile、readiness 等治理上下文。
```

## 3. 工作台页目标形态

`/workbench/[ticketId]` 是核心页面，应基于 RAGFlow 的文档和 chunk 工作台体验。

页面布局：

```text
┌──────────────────────────────────────────────────────────────┐
│ Ticket / Document header                                      │
├───────────────────┬────────────────────────┬─────────────────┤
│ 原始文档预览       │ RAGFlow chunk 工作台     │ AgentReview      │
│ PDF/DOCX/PPT/XLSX │ chunk 列表/编辑/定位     │ 问题/证据/建议修复 │
│ 页码/anchor        │ draft edits             │ 审批动作          │
└───────────────────┴────────────────────────┴─────────────────┘
```

核心能力：

- 查看原始文档。
- 查看 parse snapshot。
- 查看 chunk 列表。
- 点击 chunk 定位原文页码或 anchor。
- 编辑 chunk，但不直接改 live chunk。
- 发布前编辑写入 `workbench_chunk_edits`。
- 发布后编辑通过 indexing 创建 chunk revision。
- 右侧展示 AgentReview findings。
- 点击 AgentReview finding 定位到原文和 chunk。
- 从 AgentReview finding 一键生成 chunk edit draft。
- 人工执行 approve/reject/return。

## 4. 从 RAGFlow 迁移的前端模块

优先迁移以下 RAGFlow 前端模块：

```text
upstream/ragflow/web/src/pages/chunk
upstream/ragflow/web/src/pages/document-viewer
upstream/ragflow/web/src/components/document-preview
upstream/ragflow/web/src/components/chunk-method-dialog
upstream/ragflow/web/src/hooks/use-document-request.ts
upstream/ragflow/web/src/hooks/use-chunk-request.ts
upstream/ragflow/web/src/services/knowledge-service.ts
```

迁移方式：

```text
apps/web/src/features/ragflow-workbench/
  adapters/
  components/
  hooks/
  pages/
  styles/
  types/
```

不要把 RAGFlow 整个 web app 搬进来。只迁移工作台页需要的文档预览、chunk 结果、chunk 编辑、parser/chunk method 相关模块。

## 5. 前端适配层

RAGFlow 原前端通常按 dataset/document/chunk 调用它自己的后端接口。迁入后必须通过 adapter 统一改成 workbench-api。

建议新增：

```text
apps/web/src/features/ragflow-workbench/adapters/workbench-ragflow-adapter.ts
```

职责：

- 把 RAGFlow 页面需要的 dataset/document/chunk 数据结构映射到 workbench-api 返回值。
- 隐藏我们的 `ticket_id`、`parse_snapshot_id`、`source_file_id`、`evidence_id` 差异。
- 让迁移来的 RAGFlow UI 尽量少感知业务后端细节。

示例映射：

```text
RAGFlow document id       -> parse_snapshot_id / source_file_id
RAGFlow chunk id          -> evidence_id
RAGFlow dataset id        -> collection_id
RAGFlow document status   -> workbench projection status
RAGFlow chunk update      -> workbench_chunk_edits draft 或 indexing chunk revision
```

## 6. 前后端边界

前端只调用 `workbench-api`：

```text
workbench-ui
  -> workbench-api
       -> admin
       -> intake
       -> document-service
       -> indexing
       -> approval
       -> access
       -> retrieval, only for privileged debug
```

不允许：

- workbench 前端直接调用 `admin`。
- workbench 前端直接调用 `access`。
- workbench 前端直接调用 `retrieval`。
- workbench 前端保存或发送 `X-API-Key`。

允许：

- `workbench-api` 用 JWT 校验当前用户。
- `workbench-api` 根据用户权限和 collection scope 转接 `access`。
- `workbench-api` 在 debug 权限下调用 `retrieval` 内部诊断接口。

## 7. Workbench API 目标接口

工作台页需要：

```text
GET  /workbench/tickets/{ticket_id}
GET  /workbench/tickets/{ticket_id}/agent-review
POST /workbench/tickets/{ticket_id}/decide

GET  /workbench/source-files/{source_file_id}/content
GET  /workbench/parse-snapshots/{parse_snapshot_id}
GET  /workbench/parse-snapshots/{parse_snapshot_id}/chunks

GET  /workbench/parse-snapshots/{parse_snapshot_id}/chunk-edits
POST /workbench/parse-snapshots/{parse_snapshot_id}/chunk-edits
PUT  /workbench/chunk-edits/{chunk_edit_id}
POST /workbench/chunk-edits/{chunk_edit_id}/submit

POST /workbench/retrieve
GET  /workbench/query-runs
GET  /workbench/query-runs/{query_id}
```

列表页需要：

```text
GET /workbench/tasks
GET /workbench/documents
GET /workbench/tickets
GET /workbench/collections
GET /workbench/readiness
```

列表页接口必须读 SQL projection，不应实时查询多个下游服务再组装。

## 8. SQL Projection Store

workbench 自己维护 SQL 投影表。SQL 是主存储，Redis 只做缓存。

建议表：

```text
workbench_task_projection
workbench_ticket_projection
workbench_document_projection
workbench_chunk_projection
workbench_agent_review_projection
workbench_query_runs
workbench_projection_events
```

`workbench_task_projection` 示例字段：

```text
upload_id
tenant_id
user_id
collection_id
filename
source_file_id
intake_job_id
parse_snapshot_id
ticket_id
published_document_id
final_doc_id
source_file_state
intake_job_state
parse_snapshot_state
ticket_state
published_document_state
index_build_state
active_index_version
overall_status
progress_pct
last_event_at
projection_updated_at
stale_after
error_message
```

推荐索引：

```sql
create index idx_wtp_user_list
on workbench_task_projection (tenant_id, user_id, collection_id, projection_updated_at desc);

create index idx_wtp_status
on workbench_task_projection (tenant_id, collection_id, overall_status, projection_updated_at desc);

create unique index uq_wtp_upload
on workbench_task_projection (upload_id);
```

## 9. 数据更新策略

更新来源：

- workbench upload 创建时，立即写本地 projection。
- document-service 原始文件状态变化，更新 source file projection。
- intake job 状态变化，更新 task/document projection。
- indexing parse snapshot/chunk/index 状态变化，更新 document/chunk projection。
- approval ticket 和 AgentReview 变化，更新 ticket/agent review projection。
- retrieval/access query run 写入 `workbench_query_runs`。

可靠性：

- 每个下游事件带 `event_id` 或版本号。
- projection 更新必须幂等。
- 旧版本事件不能覆盖新状态。
- 定时 reconciliation job 兜底修复漏事件。
- 下游失败时 projection 标记 stale/degraded，不伪装成功。

## 10. 原始文档与 Chunk 对照编辑

原始文档由 document-service 或 object storage 持有，workbench-api 只做代理和权限校验。

数据流：

```text
DocumentViewer
  -> GET /workbench/source-files/{source_file_id}/content
       -> document-service/object storage

ChunkPanel
  -> GET /workbench/parse-snapshots/{parse_snapshot_id}/chunks
       -> indexing or workbench chunk projection

ChunkEdit
  -> POST /workbench/parse-snapshots/{parse_snapshot_id}/chunk-edits
       -> workbench_chunk_edits

SubmitEdit
  -> POST /workbench/chunk-edits/{chunk_edit_id}/submit
       -> indexing chunk revision or pre-publish materialization
```

编辑语义：

- 发布前编辑：写 `workbench_chunk_edits`，审批/发布时由 indexing 合并。
- 发布后编辑：由 indexing 创建 chunk revision，重算 embedding，更新检索索引。
- workbench 不直接写 live retrieval chunk。

## 11. AgentReview 改造

当前 AgentReview 展示不够，需要改成可定位的 finding。

目标字段：

```text
finding_id
severity
category
problem_summary
problem_detail
evidence_id
chunk_id
page_from
page_to
source_quote
chunk_quote
why_wrong
suggested_fix
suggested_operation
confidence
```

前端行为：

- 右侧显示 finding 列表。
- 点击 finding 定位原文页码。
- 点击 finding 定位对应 chunk。
- 显示 source quote 和 chunk quote 对比。
- 显示 why wrong 和 suggested fix。
- 支持从 suggested fix 创建 chunk edit draft。

后端要求：

- Agent reviewer prompt 必须要求输出 evidence anchor。
- AgentReview artifact 必须保留 evidence_id/page_span/source_quote。
- workbench-api 将 AgentReview 投影为页面友好的 finding model。

## 12. 检索验证

workbench 前端不直接调用 access。

数据流：

```text
POST /workbench/retrieve
  -> workbench-api 校验 JWT、collection ACL、debug 权限
  -> access
  -> retrieval
  -> workbench-api 记录 query_run
  -> 前端展示 KnowledgeContext
```

`access` 仍然是外部 Agent/API key/MCP 的正式入口。workbench 用户通过 JWT 使用 workbench-api，不在浏览器里接触 API key。

## 13. 并发与延迟策略

列表页：

- 只读 SQL projection。
- 不 fan-out 下游服务。
- 支持分页、过滤、排序。

详情页：

- 允许并发读取多个详情接口。
- fan-out 由 workbench-api 执行。
- 使用 `asyncio.gather` 或等价并发机制。
- 每个下游独立 timeout。
- 局部失败返回 degraded，不阻塞整页。

检索：

- retrieval 内部后续应支持 OpenSearch/Qdrant 并行召回。
- 多 collection plan 可并发。
- query embedding 和 recall cache 使用 Redis。
- Redis 不作为 workbench projection 主存储。

## 14. 实施阶段

### Phase 0: 冻结错误方向

- 停止继续补当前手写 review detail/workbench 页面。
- 确认 `apps/web` 保留多页结构。
- 确认只迁移 RAGFlow 的工作台页能力。

### Phase 1: Workbench API 与 Projection

- 建 `workbench_task_projection`。
- 建 `workbench_ticket_projection`。
- 建 `workbench_document_projection`。
- 将 `/workbench/tasks`、`/workbench/tickets`、`/workbench/documents` 改为读 SQL projection。
- 增加 projection update/reconcile 机制。

### Phase 2: RAGFlow 工作台页迁移

- 创建 `apps/web/src/features/ragflow-workbench`。
- 迁移 RAGFlow `pages/chunk`。
- 迁移 RAGFlow `pages/document-viewer`。
- 迁移 RAGFlow `components/document-preview`。
- 迁移必要 hooks 和 styles。
- 接入 `/workbench/[ticketId]`。

### Phase 3: API Adapter

- 新增 `workbench-ragflow-adapter.ts`。
- 适配 document/chunk/parser API。
- 将 RAGFlow 的 dataset/document/chunk id 映射到我们的 collection/source/parse/evidence id。
- 禁止迁移后的页面直接调用非 workbench-api 后端。

### Phase 4: 原文 + Chunk 对照编辑

- 实现 source file content proxy。
- 实现 parse snapshot chunk projection。
- 实现 chunk edit draft。
- 实现 chunk edit submit。
- 将 RAGFlow chunk 编辑操作映射到 workbench edit 语义。

### Phase 5: AgentReview 定位能力

- 更新 AgentReview schema。
- 更新 agent reviewer prompt。
- approval 或 workbench-api 输出可定位 findings。
- 工作台页右侧展示 AgentReview panel。
- 点击 finding 跳转原文和 chunk。
- 支持从 finding 创建 edit draft。

### Phase 6: 检索验证转接

- 新增 `/workbench/retrieve`。
- workbench-api 转接 access。
- 写入 `workbench_query_runs`。
- 前端 `/retrieval` 页面不再直接调用 access。

### Phase 7: 验证与性能

- 前端构建测试。
- workbench-api contract tests。
- E2E：上传 -> 投影 -> 工作台 -> 原文预览 -> chunk edit -> AgentReview -> 审批。
- 延迟测试：列表页 SQL 查询、工作台详情并发 fan-out、检索验证。

## 15. 非目标

当前阶段不做：

- 不整体替换成完整 RAGFlow web app。
- 不让前端直接连接 admin/access/retrieval/indexing/intake。
- 不把 projection 主存储放 Redis。
- 不让 workbench 直接写 live retrieval chunk。
- 不重写 RAGFlow 已经成熟的 document/chunk 工作台体验。

## 16. 最终目标

最终状态：

- 我们的前端仍是多页业务系统。
- 自动上传页、review 列表、检索验证、集合页保持我们的产品语义。
- 工作台页基于 RAGFlow 的成熟文档/chunk 工作流。
- `workbench-api` 是前端唯一后端入口。
- 列表页读 SQL projection。
- 详情页由 workbench-api 并发聚合。
- AgentReview 能明确指出哪里有问题、有什么问题、怎么改。
- 人工编辑和审批都受治理，不直接绕过 indexing/retrieval owner。
