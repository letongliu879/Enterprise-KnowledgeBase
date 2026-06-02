# Workbench + RAGFlow Frontend Overall Plan

## 1. 结论

当前不是继续补前端小问题的阶段。正确方向是：

- 保留我们自己的多页面前端，不整体替换成 RAGFlow web app。
- 只把 RAGFlow 的文档 / chunk 工作台能力迁入我们的 `/workbench/[ticketId]` 页面。
- 前端所有业务数据只调用 `workbench-api`。
- `workbench-api` 作为 Human Workflow BFF + SQL Projection Store + downstream adapter。
- 列表页读 SQL projection，不在请求时临时 fan-out 多个下游服务。
- `access` 对 workbench 用户也通过 `workbench-api` 转接，浏览器不接触 API key。
- AgentReview 必须输出可定位 finding，支持原始文档和 chunk 对照修改。

这份方案的重点是先完成后端改造，再搬 RAGFlow 工作台页。否则前端即使搬过来也会继续被多个后端接口和临时组装视图拖住。

## 2. 页面结构

`apps/web` 仍然是我们的前端应用，目标页面如下：

```text
/upload
  自动上传页
  批量上传、权限范围、上传进度、任务投影。

/review
  待审列表页
  只查 workbench SQL projection。

/workbench/[ticketId]
  工作台页
  基于 RAGFlow 文档 / chunk 页面迁移，叠加 AgentReview、审批、chunk edit draft。

/retrieval
  检索验证页
  前端只调 workbench-api，由 workbench-api 转接 access。

/collections
  集合 / 知识库概览页
  展示 collection、profile、readiness、projection freshness。
```

## 3. 后端改造总原则

### 3.1 唯一前端入口

浏览器只能访问：

```text
workbench-ui -> workbench-api
```

不允许：

- `workbench-ui -> admin`
- `workbench-ui -> access`
- `workbench-ui -> retrieval`
- `workbench-ui -> indexing`
- `workbench-ui -> intake`
- 浏览器保存或发送 `X-API-Key`

允许：

```text
workbench-api
  -> admin
  -> intake
  -> document-service / object storage
  -> indexing
  -> approval
  -> access
  -> retrieval, only for privileged internal debug
```

### 3.2 Workbench 不做事实 owner

`workbench-api` 可以拥有人的工作区视图和编辑意图，但不拥有治理事实。

| 对象 | 事实 owner | workbench 角色 |
|---|---|---|
| Collection / ACL / ParserProfile | admin | 只读使用 |
| SourceFile / IntakeJob | intake / document-service | 上传代理、状态投影 |
| ParseSnapshot / chunk preview / indexed chunk | indexing | 预览、编辑意图提交 |
| ApprovalTicket / AgentReview artifact | approval / intake | 展示、决策代理 |
| PublishedDocument | intake / publishing domain | 只读投影 |
| WorkbenchTaskProjection | workbench-api | 列表 read model |
| WorkbenchChunkEdit | workbench-api | 人工编辑意图 |
| QueryRun | workbench-api | 工作台检索验证记录 |

### 3.3 SQL 是 projection 主存储，Redis 只做缓存

workbench 列表、工作台状态、AgentReview finding 展示、检索验证记录必须落 SQL。

Redis 只用于：

- 短 TTL 查询缓存
- 分布式锁
- 幂等请求短缓存
- retrieval query embedding / recall cache
- 后端并发聚合的临时结果缓存

Redis 不作为 `workbench_task_projection`、`workbench_ticket_projection`、`workbench_document_projection` 的主存储。

## 4. 后端目标模块

`workbench-api` 内部需要分开，但不应该按每个功能都提前拆一个顶层模块。第一版应按变化原因拆成少数几个深模块：列表 read model、工作台详情聚合、写命令、下游适配。

建议把 `services/workbench-api/src/workbench_api` 调整为以下结构：

```text
workbench_api/
  auth/

  projections/
    models.py
    repository.py
    projectors.py
    reconciler.py
    routes.py

  workspace/
    routes.py
    service.py

  commands/
    routes.py
    service.py

  downstream_clients/
    admin_client.py
    access_client.py
    approval_client.py
    document_service_client.py
    indexing_client.py
    intake_client.py
  errors.py
  main.py
```

关键点：

- `projections` 是列表页和状态页的主读模块。
- `workspace` 是单个 ticket 工作台详情聚合模块，可以并发 fan-out，但只服务详情，不服务列表。
- `commands` 承载会改变状态或产生记录的动作，例如 upload、ticket decision、chunk edit、retrieve verify。
- `downstream_clients` 是所有下游 adapter 的唯一位置。
- `auth` 负责 JWT、role、tenant、collection scope。

不要一开始就把 `agent_review`、`chunk_edits`、`retrieval_verify`、`tickets`、`source_files` 全部拆成顶层模块。是否独立，应看它是否满足以下条件：

- 有自己的 SQL 表或状态机。
- 有自己的 contract / schema。
- 有复杂转换逻辑，而不是简单透传。
- 有独立测试价值。
- 会被多个上层入口复用。

具体建议：

- `chunk_edits` 初期可以放在 `commands` 下；如果 split / merge / revision / rollback 状态机变复杂，再独立。
- `agent_review` 初期可以放在 `workspace` 和 `projections` 下；如果 finding schema、prompt、投影和修复建议生成变复杂，再独立。
- `retrieval_verify` 初期可以放在 `commands` 下，因为它主要是 access proxy + `workbench_query_runs` 记录。
- `tickets` 如果只是 approval proxy 和 projection 查询，不需要顶层模块；如果后续承载复杂人工审批流，再独立。
- `source_files` 如果只是 content proxy，不需要顶层模块；如果后续支持转换预览、权限水印、下载审计，再独立。

这样拆分的目标不是目录整齐，而是让四类不同复杂度互不污染：

- 列表性能问题集中在 `projections`。
- 单页并发聚合和降级集中在 `workspace`。
- 写动作、幂等和 command envelope 集中在 `commands`。
- 下游协议变化集中在 `downstream_clients`。

## 5. SQL Projection Store

### 5.1 必须新增或调整的表

```text
workbench_task_projection
workbench_ticket_projection
workbench_document_projection
workbench_chunk_projection
workbench_agent_review_projection
workbench_chunk_edits
workbench_query_runs
workbench_projection_events
workbench_projection_reconcile_runs
```

现有 `workbench_upload_sessions` 可以保留，但不能继续承担完整列表 read model。它只适合保存上传会话和 UI 发起上下文。

### 5.2 `workbench_task_projection`

用途：`/upload`、`/review`、任务列表、顶部状态统计。

```text
projection_id
tenant_id
user_id
collection_id
upload_id
filename
mime_type
size_bytes

source_file_id
intake_job_id
parse_snapshot_id
ticket_id
published_doc_id
doc_id

source_file_state
intake_job_state
parse_snapshot_state
ticket_state
agent_review_state
published_document_state
index_build_state
active_index_version

overall_status
progress_pct
blocking_reason
error_code
error_message

created_at
last_event_at
projection_updated_at
stale_after
is_stale
version
```

推荐索引：

```sql
create index idx_wtp_user_list
on workbench_task_projection
  (tenant_id, user_id, collection_id, projection_updated_at desc);

create index idx_wtp_status
on workbench_task_projection
  (tenant_id, collection_id, overall_status, projection_updated_at desc);

create unique index uq_wtp_upload
on workbench_task_projection (upload_id);

create index idx_wtp_ticket
on workbench_task_projection (tenant_id, ticket_id);
```

### 5.3 `workbench_ticket_projection`

用途：`/review` 待审列表和筛选。

```text
ticket_id
tenant_id
collection_id
upload_id
source_file_id
parse_snapshot_id
doc_id

title
filename
state
priority
routing_recommendation
assignee_user_id

agent_decision
agent_risk_level
agent_finding_count
agent_blocking_finding_count

created_at
updated_at
last_event_at
projection_updated_at
version
```

### 5.4 `workbench_document_projection`

用途：`/collections` 文档列表、工作台 header、检索验证范围。

```text
doc_id
tenant_id
collection_id
source_file_id
parse_snapshot_id
published_doc_id
filename
mime_type
document_state
publish_state
active_index_version
chunk_count
page_count
parser_profile_id
parser_profile_name
created_at
updated_at
projection_updated_at
version
```

### 5.5 `workbench_chunk_projection`

用途：工作台 chunk 列表的快速展示和定位。它是 read model，不是 indexed chunk 真相。

```text
evidence_id
tenant_id
collection_id
doc_id
source_file_id
parse_snapshot_id
chunk_ordinal
content_preview
section_path_json
page_from
page_to
source_anchor_json
metadata_json
state
active_revision_id
projection_updated_at
version
```

### 5.6 `workbench_agent_review_projection`

用途：右侧 AgentReview panel 的 finding 列表。

```text
finding_id
tenant_id
collection_id
ticket_id
doc_id
source_file_id
parse_snapshot_id
evidence_id

severity
category
problem_summary
problem_detail
source_quote
chunk_quote
page_from
page_to
source_anchor_json
why_wrong
suggested_fix
suggested_operation
confidence

state
created_at
projection_updated_at
version
```

### 5.7 `workbench_query_runs`

用途：工作台检索验证页、排查 access/retrieval 结果。

```text
query_run_id
tenant_id
user_id
collection_id
query
token_budget
request_json
access_response_json
knowledge_context_json
latency_ms
cache_hit
status
error_code
error_message
created_at
```

## 6. Projection 更新机制

列表页不能在 HTTP 请求中临时查多个下游再组装。

目标机制：

```text
downstream owner event / sync callback
  -> workbench projection event ingest
  -> idempotent projector
  -> SQL projection tables
  -> frontend list query
```

### 6.1 事件来源

| 来源 | 更新 projection |
|---|---|
| workbench upload 创建 | task projection 初始行 |
| document-service source file 状态变化 | task / document projection |
| intake job 状态变化 | task projection |
| indexing ParseSnapshot ready | task / document / chunk projection |
| indexing chunk materialized / revision active | document / chunk projection |
| approval ticket created / updated | task / ticket projection |
| AgentReview artifact ready | ticket / agent_review projection |
| publish / index activated | task / document projection |
| workbench retrieval verify | query_runs |

### 6.2 幂等和乱序处理

每条 projection event 必须包含：

```text
event_id
event_type
tenant_id
collection_id
aggregate_type
aggregate_id
aggregate_version
occurred_at
payload
trace_id
```

处理规则：

- `event_id` 唯一，重复事件直接忽略。
- 同一 aggregate 只允许新版本覆盖旧版本。
- 旧事件不能覆盖新状态。
- projector 写入和 `workbench_projection_events` 记录在同一 SQL transaction。
- 下游不可用时 projection 标记 `is_stale=true`，不能伪装成功。

### 6.3 Reconciliation Job

必须有兜底 reconciliation：

```text
every 1-5 minutes:
  scan stale projection rows
  query owner services by stored ids
  recompute projection
  write projection_reconcile_runs
```

reconcile 的目的不是替代事件，而是修复漏事件、乱序和临时失败。

## 7. API 改造目标

### 7.1 列表页接口只读 SQL

这些接口只能查 projection，不允许 fan-out 下游：

```text
GET /workbench/tasks
GET /workbench/tasks/{upload_id}
GET /workbench/tickets
GET /workbench/documents
GET /workbench/collections
GET /workbench/readiness
```

必须支持：

- 分页
- 过滤
- 排序
- `projection_updated_at`
- `is_stale`
- `degraded_reason`

### 7.2 工作台详情接口可以并发聚合

详情页允许 `workbench-api` 并发读取下游，因为这是单个 ticket 的交互，不是列表轮询。

```text
GET /workbench/tickets/{ticket_id}/workspace
```

返回：

```text
ticket
document
source_file
parse_snapshot
chunks
chunk_edits
agent_review_findings
permissions
projection_freshness
degraded_parts
```

后端内部用并发：

```text
async gather:
  approval ticket detail
  document/source metadata
  parse snapshot
  chunk projection or indexing chunk preview
  workbench chunk edits
  agent review projection
```

要求：

- 每个下游有独立 timeout。
- 局部失败返回 `degraded_parts`，不阻塞整页。
- 同一请求共享 `trace_id`。
- 详情聚合结果可以短 TTL cache，但 SQL projection 仍是列表主读。

### 7.3 原始文档内容代理

```text
GET /workbench/source-files/{source_file_id}/content
GET /workbench/source-files/{source_file_id}/preview
```

职责：

- 校验 JWT。
- 校验 tenant / collection scope。
- 向 document-service 或 object storage 获取 signed content。
- 对 PDF/DOCX/PPT/XLSX 返回可预览 stream 或预览 descriptor。
- 不把原文二进制复制进 workbench 数据库。

### 7.4 RAGFlow 工作台适配接口

迁移 RAGFlow 前端后，adapter 需要这些后端接口：

```text
GET  /workbench/parse-snapshots/{parse_snapshot_id}
GET  /workbench/parse-snapshots/{parse_snapshot_id}/chunks
GET  /workbench/chunks/{evidence_id}
POST /workbench/parse-snapshots/{parse_snapshot_id}/chunk-edits
PUT  /workbench/chunk-edits/{chunk_edit_id}
POST /workbench/chunk-edits/{chunk_edit_id}/submit
PATCH /workbench/chunks/{evidence_id}
```

wire 字段必须使用 canonical 命名：

```text
content       not display_text
evidence_id   not chunk_id
doc_id        not final_doc_id
query         not query_text
token_budget  not max_context_tokens
```

### 7.5 Workbench 检索验证代理

前端不直接调 access。

```text
POST /workbench/retrieve
GET  /workbench/query-runs
GET  /workbench/query-runs/{query_run_id}
```

调用链：

```text
workbench-ui
  -> workbench-api: POST /workbench/retrieve
    -> validate JWT, role, collection ACL
    -> call access with server-side credential or internal trust
    -> access -> retrieval
    -> workbench-api writes workbench_query_runs
    -> frontend receives KnowledgeContext + diagnostics summary
```

`access` 仍然是外部 Agent/API key/MCP 的正式入口。workbench 用户通过 JWT 进入 workbench-api，由后端转接。

## 8. 并发与延迟策略

### 8.1 列表页

列表页目标：

```text
P95 < 200ms for normal SQL query
P95 < 500ms with filters and counts
0 downstream calls in request path
```

手段：

- SQL projection。
- 必要索引。
- 分页，不一次返回全部。
- 状态统计可使用 SQL aggregate 或定时物化。

### 8.2 详情页

详情页目标：

```text
P95 < 1.5s when downstream healthy
partial response when one downstream is slow
```

手段：

- `asyncio.gather` / AnyIO task group。
- 每个 downstream client 独立 timeout，例如 300-800ms。
- circuit breaker 或连续失败降级。
- 大 chunk 列表分页加载。
- 原文 preview 和 chunk panel 分开懒加载。

### 8.3 检索验证

检索验证目标：

```text
P95 < 2.5s for warm query
```

手段：

- access/retrieval 内部并发召回 OpenSearch + Qdrant。
- Redis 用于 query embedding cache / recall cache。
- workbench-api 记录 query run，不同步阻塞额外分析。

## 9. AgentReview 改造

当前 AgentReview 不应只返回一段文字。目标是 finding model：

```text
finding_id
severity
category
problem_summary
problem_detail
evidence_id
doc_id
source_file_id
parse_snapshot_id
page_from
page_to
source_anchor
source_quote
chunk_quote
why_wrong
suggested_fix
suggested_operation
confidence
```

后端要求：

- Agent reviewer prompt 必须要求输出 evidence anchor。
- AgentReview artifact 必须保留 `evidence_id`、`page_span`、`source_quote`。
- approval 或 intake 仍是 AgentReview artifact owner。
- workbench-api 投影成 `workbench_agent_review_projection`。
- 前端点击 finding 能定位原文和 chunk。
- finding 可以生成 chunk edit draft，但不直接改 live chunk。

## 10. Chunk 编辑语义

### 10.1 发布前编辑

```text
RAGFlow chunk editor
  -> POST /workbench/parse-snapshots/{id}/chunk-edits
  -> workbench_chunk_edits status=draft
  -> submit / approve
  -> indexing materializes ParseSnapshot + edits
```

### 10.2 发布后编辑

```text
RAGFlow chunk editor
  -> PATCH /workbench/chunks/{evidence_id}
  -> workbench-api creates ChunkRevision command
  -> indexing recomputes embedding
  -> indexing rewrites OpenSearch/Qdrant
  -> old chunk superseded
  -> retrieval cache purged
```

workbench 不允许：

- 直接 update indexed chunk。
- 直接写 OpenSearch/Qdrant。
- 只改本地 `workbench_chunk_edits` 就宣称修改完成。

## 11. RAGFlow 前端迁移范围

只迁移工作台页需要的模块：

```text
upstream/ragflow/web/src/pages/chunk
upstream/ragflow/web/src/pages/document-viewer
upstream/ragflow/web/src/components/document-preview
upstream/ragflow/web/src/components/chunk-method-dialog
upstream/ragflow/web/src/hooks/use-document-request.ts
upstream/ragflow/web/src/hooks/use-chunk-request.ts
upstream/ragflow/web/src/services/knowledge-service.ts
```

落点：

```text
apps/web/src/features/ragflow-workbench/
  adapters/
  components/
  hooks/
  pages/
  styles/
  types/
```

必须新增：

```text
apps/web/src/features/ragflow-workbench/adapters/workbench-ragflow-adapter.ts
```

映射规则：

```text
RAGFlow dataset id      -> collection_id
RAGFlow document id     -> source_file_id / parse_snapshot_id / doc_id
RAGFlow chunk id        -> evidence_id
RAGFlow chunk update    -> workbench chunk edit / indexing ChunkRevision
RAGFlow document status -> workbench projection status
```

## 12. 实施阶段

### Phase 0: 冻结方向

- 停止继续补当前手写 workbench detail 页面。
- 确认前端是多页面业务系统。
- 确认只迁移 RAGFlow 工作台相关模块。
- 确认 `workbench-api` 是唯一前端后端入口。

### Phase 1: 后端 projection 改造

- 新增 `workbench_task_projection`。
- 新增 `workbench_ticket_projection`。
- 新增 `workbench_document_projection`。
- 新增 `workbench_projection_events`。
- 把 `/workbench/tasks` 从运行时 fan-out 改成只读 SQL。
- 给 projection 增加分页、过滤、排序、stale 标记。
- 增加 projector 和 reconciliation job。

### Phase 2: Workspace 详情聚合接口

- 新增 `/workbench/tickets/{ticket_id}/workspace`。
- 并发读取 ticket、document、parse snapshot、chunk edits、AgentReview findings。
- 支持局部降级和 `degraded_parts`。
- 详情页不再由前端分别查多个服务。

### Phase 3: 原始文档与 chunk 对照

- 新增 source file content/preview 代理。
- 新增 chunk projection 或 chunk preview adapter。
- 支持 chunk 点击定位原文 page/anchor。
- 支持原文和 chunk 对照编辑。

### Phase 4: AgentReview finding 化

- 更新 AgentReview schema。
- 更新 agent reviewer prompt。
- 把 AgentReview artifact 投影成 finding。
- finding 支持定位原文、定位 chunk、生成 chunk edit draft。

### Phase 5: access 转接

- 新增 `AccessClient`。
- 新增 `/workbench/retrieve`。
- 写入 `workbench_query_runs`。
- `/retrieval` 页面不再直接调用 access。

### Phase 6: RAGFlow 工作台页迁移

- 创建 `apps/web/src/features/ragflow-workbench`。
- 迁移 RAGFlow document viewer / chunk 页面。
- 用 `workbench-ragflow-adapter.ts` 对接 workbench-api。
- 接入 `/workbench/[ticketId]`。

### Phase 7: 验证

- workbench-api contract tests。
- projection projector idempotency tests。
- reconciliation tests。
- workspace detail degraded response tests。
- access proxy authorization tests。
- E2E：上传 -> projection -> review -> workbench -> 原文预览 -> chunk edit -> AgentReview -> 审批 -> 检索验证。
- 延迟测试：列表页 SQL 查询、详情页并发聚合、检索验证 warm query。

## 13. 当前代码风险点

当前 `services/workbench-api/src/workbench_api/task_projection/service.py` 的风险是：

- `/workbench/tasks` 先查 upload sessions。
- 然后对每个 upload 逐个查 intake、approval、indexing。
- 当前实现是串行 loop。
- 列表越多，下游调用越多，延迟和失败面都会放大。
- 这正是需要 SQL projection 的原因。

目标不是把这个 loop 改成并发就结束。并发只能缓解单次慢，不能解决列表页 read model 错误。列表页必须改为 projection 读取；详情页才允许 workspace fan-out。

## 14. 非目标

当前阶段不做：

- 不整体搬 RAGFlow web app。
- 不让前端直接连 admin/access/retrieval/indexing/intake。
- 不把 projection 主存储放 Redis。
- 不让 workbench 直接写 live retrieval chunk。
- 不让 AgentReview 成为 workbench 可修改的事实源。
- 不用前端临时拼多个服务响应来替代后端 read model。

## 15. 最终状态

最终应该达到：

- 前端仍是我们的多页面业务系统。
- workbench 页复用 RAGFlow 成熟文档 / chunk 工作流。
- 前端只知道 `workbench-api`。
- 列表页读 SQL projection。
- 详情页由 workbench-api 并发聚合并可局部降级。
- access 由 workbench-api 代理给工作台用户。
- AgentReview 明确指出哪里有问题、有什么问题、为什么错、怎么改。
- chunk 修改受治理和 revision 管控，不绕过 indexing/retrieval owner。
