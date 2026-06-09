# services/workbench-api 设计说明

## 1. 定位

`services/workbench-api` 是 Enterprise KnowledgeBase 的文档工作台后端。

它面向三类使用者：
- 文档处理人员
- 人工复核人员
- 具备治理权限的知识库管理员

它不是 owner service，不定义全局规则，也不直接维护检索索引或发布状态事实。
它的职责是：
- 聚合多个 owner service 的事实
- 提供面向前端页面的工作台视图
- 在既有权限与治理规则下代理受控动作

## 2. 核心边界

### workbench-api 拥有
- `workbench_upload_sessions`
- `workbench_chunk_edits`
- `workbench_query_runs`
- task / ticket / document / agent-review / chunk projection
- 文档页、复核页、上传页需要的聚合视图

### workbench-api 不拥有
- `source_file`
- `intake_job`
- `parse_snapshot`
- `approval_ticket`
- `published_document`
- `indexed_chunk`
- OpenSearch / Qdrant 中的真实索引状态

### 设计原则
- 所有下游写操作都走 owner API
- 本地状态是 projection，不是事实源
- 失败时返回统一错误码，不能把本地投影误标成成功
- 文档页与复核页都优先消费聚合视图，而不是前端自己拼多条接口

## 3. 当前能力

### 上传与任务链路
- 创建上传会话
- 上传文件内容
- 追踪 `upload -> source_file -> intake_job -> review -> publish -> index`

### 解析与原文查看
- 查看 `ParseSnapshot`
- 查看 ParseSnapshot chunks
- 查看 source preview 与 source preview content

### Chunk 工作流
- pre-publish draft edit
- post-publish chunk revision

### Review 工作流
- ticket 列表与详情
- AgentReview 查看
- reviewer 决策
- ticket 视角 workspace 聚合

### 文档管理台
- 文档列表投影
- 文档视角 workspace 聚合
- 文档详情页内嵌 review cockpit
- 单文档 `archive / retract / reindex`
- 批量 `archive / retract / reindex`

## 4. 文档管理台设计

### 4.1 文档列表

文档列表路由：
- `GET /workbench/documents`

列表返回除投影基础字段外，还会补充：
- `ticket_id`
- `ticket_status`
- `task_status`
- `has_source_file`
- `has_parse_snapshot`
- `has_active_index`
- `latest_updated_at`
- `degraded_reason`

实现要求：
- ticket/task 摘要通过批量 projection 查找补齐
- 不能对每个文档单独走 workspace-style 解析，避免 N+1 SQL 查询

### 4.2 文档详情工作台

文档详情主接口：
- `GET /workbench/documents/{doc_id}/workspace`

返回至少包含：
- `document`
- `task`
- `ticket`
- `source_file`
- `parse_snapshot`
- `chunks`
- `chunk_edits`
- `agent_review`
- `capabilities`
- `projection_freshness`
- `degraded_parts`
- `trace_id`

文档工作台是文档详情页的唯一主数据源。前端不应再自行拼装：
- 文档投影详情
- ParseSnapshot 详情
- chunk 列表
- review 摘要

### 4.3 文档与 review 的关系

当文档有关联 ticket 时：
- 文档详情页直接内嵌 review cockpit
- reviewer 若有权限且 ticket 为 pending，可直接在文档页决策
- 否则只显示只读 review 摘要与决策信息

ticket 选择规则：
1. 优先选择与该文档关联且 `pending` 的 ticket
2. 否则回退到最新一条关联 ticket

## 5. 文档生命周期动作

### 5.1 对外接口
- `POST /workbench/documents/{doc_id}/archive`
- `POST /workbench/documents/{doc_id}/retract`
- `POST /workbench/documents/{doc_id}/reindex`
- `POST /workbench/documents/batch/archive`
- `POST /workbench/documents/batch/retract`
- `POST /workbench/documents/batch/reindex`

### 5.2 权限边界

文档生命周期动作只允许：
- `knowledge_admin`
- `platform_admin`

### 5.3 状态边界

生命周期动作不是“只要有 `doc_id` 就能做”。

必须满足：
- 文档处于已发布且可管理状态
- `archive / retract` 只对可管理的已发布文档开放
- `reindex` 还要求存在 `parse_snapshot_id`

不应对以下文档展示或执行生命周期动作：
- `PENDING`
- 未发布
- 已归档
- 已撤回
- 缺失必要上下文的投影文档

### 5.4 幂等语义

- `archive` / `retract`
  使用稳定幂等键，按已发布文档维度去重

- `reindex`
  必须为每次请求生成新的幂等键
  原因：同一文档允许被多次主动重建索引，不能因为复用固定键而被错误去重

### 5.5 批量语义

批量动作采用 best-effort：
- 每个文档独立执行
- 总体返回 200
- 返回逐项成功/失败结果
- 不做 all-or-nothing

## 6. 下游依赖

### 主要调用
- `DocumentServiceClient -> POST /upload`
- `IntakeClient -> /internal/source-files/*`
- `IntakeClient -> /internal/intake-jobs/*`
- `IntakeClient -> /internal/published-documents/*`
- `IndexingClient -> /internal/parse-previews`
- `IndexingClient -> /internal/parse-snapshots/*`
- `IndexingClient -> /internal/chunks/*`
- `ApprovalClient -> /internal/tickets/*`
- `AccessClient -> POST /v1/retrieve`
- `AdminClient -> /admin/collections*`
- `AdminClient -> /admin/retrieval-profiles*`
- `AdminClient -> /admin/documents/{final_doc_id}/{archive|retract|reindex}`

### 仍未完成的下游能力
- chunk revision 查询
- chunk revision materialize 查询/控制
- retrieval cache purge

这些缺口存在时，workbench 必须返回统一的 `DOWNSTREAM_NOT_IMPLEMENTED`，而不是伪造成功路径。

## 7. 错误语义

统一错误码：
- `DOWNSTREAM_NOT_IMPLEMENTED`
- `DOWNSTREAM_UNAVAILABLE`
- `CONFLICT`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `BAD_REQUEST`

特别说明：
- 文档生命周期动作若上下文不完整，应返回 `409 CONFLICT`
- 文档生命周期动作若角色不符，应返回 `403 FORBIDDEN`
- 文档生命周期动作若文档不在可管理状态，应返回 `409 CONFLICT`

## 8. 前端消费约定

### 文档列表页
- 使用 `/workbench/documents`
- 支持多选和批量动作
- 批量动作前必须收集 reason

### 文档详情页
- 使用 `/workbench/documents/{doc_id}/workspace`
- source / chunks / agent review / lifecycle 都从 workspace 派生

### Source 与 Parsed Text
- `Source` 只消费 source preview
- `Parsed text` 只消费 ParseSnapshot `preview_text`

## 9. 契约与测试

当前应保持同步的契约文件：
- `contracts/openapi/workbench-api.yaml`
- `contracts/schemas/WorkbenchWorkspaceDetail.schema.json`
- `contracts/schemas/WorkbenchDocumentWorkspaceDetail.schema.json`
- `contracts/schemas/WorkbenchDocumentLifecycleActionRequest.schema.json`
- `contracts/schemas/WorkbenchDocumentLifecycleActionResult.schema.json`
- `contracts/schemas/WorkbenchBatchDocumentActionRequest.schema.json`
- `contracts/schemas/WorkbenchBatchDocumentActionResult.schema.json`
- `contracts/examples/workbench_*.json`

关键测试：
- `packages/contracts/tests/test_schema_validation.py`
- `services/workbench-api/tests/test_document_management.py`
- `services/workbench-api/tests/test_workspace.py`
- `services/workbench-api/tests/test_task_projection.py`
- `apps/web/e2e/documents.spec.ts`

## 10. 最新状态（2026-06-09）

已完成：
- 文档工作台聚合接口
- 文档列表管理字段扩展
- 单文档与批量生命周期代理
- 生命周期权限与状态门控
- `reindex` 的新幂等键语义
- 文档列表去除 per-document workspace 风格解析，避免 N+1
- 前端文档列表管理台
- 前端文档详情工作台
- OpenAPI / schema / examples / E2E 同步
