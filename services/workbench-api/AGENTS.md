# workbench-api — Human Workflow BFF + Projection Store

## 定位
workbench-api 是 workbench-ui 唯一后端入口，面向文档处理人员/审批人员。

**做**：上传与跟踪、parser 选择与沙盒、ParseSnapshot 预览、chunk 人工编辑、审批工作台、任务聚合、检索验证、Source File 代理、Workspace 聚合、事件驱动投影。

**不做**：定义规则、管理资源、维持系统。不直接写 OpenSearch/Qdrant、不直接写 source file/intake job/approval ticket/published document、不创建全局 ParserProfile。

## 边界原则
- 所有跨服务写操作必须用 command envelope（command_id, trace_id, idempotency_key, actor, tenant_id, collection_id, target_type, target_id, payload）
- `idempotency_key` 必须来自 workbench 本地稳定对象：`upload_id`（上传）、`upload_id + parser_profile_id + override_hash`（预览）、`chunk_edit_id`（chunk revision）
- 本地 `status` 是 UI 聚合状态，必须能从下游 owner 状态重建
- Projection 读端点优先读 SQL，减少 downstream fan-out
- 失败时返回统一错误码（DOWNSTREAM_NOT_IMPLEMENTED / DOWNSTREAM_UNAVAILABLE / CONFLICT），不把本地 projection 标成成功
- 角色检查 fail closed：`uploader`、`chunk_editor`、`reviewer`
- 使用 canonical wire：`query`、`token_budget`、`evidence_items`、`doc_id`、`evidence_id`、`content`
- AgentReview 只读展示，不修改自动审核事实
- 检索验证不暴露 access service 的 API key 到前端

## 核心数据流
```
Upload: 前端 -> POST /workbench/uploads -> 本地 SQL insert -> 
         POST /workbench/uploads/{id}/content -> DocumentServiceClient.upload_file -> 
         IntakeClient.create_source_file -> task projection 更新

Parse Preview: POST /workbench/parse-previews -> IndexingClient.create_parse_preview
               -> indexing 生成 ParseSnapshot

Approval: GET /workbench/tickets -> TicketProjectionRepository (projection 优先)
          POST /workbench/tickets/{id}/decide -> ApprovalClient.decide_ticket
          
Chunk Edit (pre-publish): 本地 workbench_chunk_edits CRUD -> 
  POST /workbench/chunk-edits/{id}/submit -> IndexingClient.create_chunk_revision

Chunk Edit (post-publish): PATCH /workbench/chunks/{evidence_id} ->
  IndexingClient.create_chunk_revision

Retrieval: POST /workbench/retrieve -> AccessClient.retrieve -> 记录 workbench_query_runs

Event -> POST /internal/events/{service} -> adapter 转换 -> ProjectionProjector 更新投影表
```

## 路由模块清单
见 routes 目录：auth、upload_sessions、parser_selection、parse_preview、parse_snapshot、chunks、chunk_edits、tickets、task_projection、workspace、source_files、commands/retrieval、events、projections、collections、retrieval_profiles、health

## 事实所有权矩阵
| 对象 | owner | workbench 角色 |
|------|-------|----------------|
| Collection | services/admin | 只读选择 |
| ParserProfile | admin(控制面) / indexing(运行时) | 只读选择、per-document override |
| SourceFile / IntakeJob | intake-pipeline | 上传、看进度 |
| ParseSnapshot | services/indexing | 预览、对比 |
| AgentReviewArtifact | intake-pipeline / approval-service | 展示证据 |
| ApprovalTicket | approval-service | pending review、decide |
| WorkbenchUploadSession | workbench-api | UI 聚合投影 |
| WorkbenchChunkEdit | workbench-api | 编辑意图 |
| ChunkRevision + indexed chunk | services/indexing | 发起修改、看结果 |
| PublishedDocument | intake-pipeline | 只读结果 |
| QueryRun | workbench-api | 检索验证记录 |
| DocumentProjection | workbench-api | 文档目录投影(事件驱动) |

## 本地投影表
- `workbench_task_projection` — 任务聚合（upload/source_file/intake_job/snapshot/ticket/publish）
- `workbench_ticket_projection` — 审批票缓存
- `workbench_document_projection` — 文档目录
- `workbench_agent_review_projection` — AgentReview findings
- `workbench_chunk_projection` — Chunk 缓存
- `workbench_projection_events` — 事件日志（append-only）
- `workbench_projection_reconcile_runs` — 协调运行记录

## 状态推导优先级
见 `_derive_overall_status`（projections/projector.py）和 `_correct_status`（task_projection/routes.py）：
`archived > retracted > published (active_index) > indexing > published (publish_succeeded) > approved > rejected > reviewing > failed > parsing > publishing > published (intake_job) > ready > uploaded > uploading`

## 约束
- 不自建用户表，只读 `admin_users` 验证 JWT
- 不提供 login 端点（login 在 admin 完成）
- Projection reconciler 是修复机制不是主更新路径（主路径是事件驱动）
- 下游 API 返回 404/501 时统一抛 DOWNSTREAM_NOT_IMPLEMENTED（前端收到 501）
- Access client 使用 `ACCESS_INTERNAL_API_KEY` 作为 server-side credentials
- `JWT_SECRET` 为强制环境变量

## 已知实现细节与潜在问题
- **硬编码 collection_id**：`chunk_edits/routes.py:28` 创建 edit 时写死 `collection_id="col_default"`，未从 context 或请求中获取真实值
- **无 DI 容器**：`chunks/routes.py` 每请求 `ChunkService(IndexingClient())`，`tickets/routes.py` 每请求 `TicketService(ApprovalClient())`，未复用 client 实例
- **tenant ACL 未实现**：`deps.py:29` `CurrentUser.can_access_tenant()` 始终返回 `True`
- **GET parse-preview 占位**：`parse_preview/routes.py:24-29` 返回硬编码 `{"status": "pending"}`，因 indexing 未提供 GET 端点
- **幂等性占位**：`upload_sessions/repository.py:37-39` `get_by_idempotency()` 始终返回 `None`
- **Chunk preview_limit 硬编码**：`events/adapters/indexing_adapter.py:86` 写死 `preview_limit=100`
- **health 端点重复**：`main.py:61-63` 定义 `/workbench/health`，同时 `health/routes.py:10` 注册了下级路由 `/all`
- **downstream client 无 connection pooling 复用**：每次创建新 `httpx.AsyncClient`（config 中指定 timeout，但 client 实例未在模块级共享）
- **parse_snapshot ACL 回退**：`parse_snapshot/service.py` 先读 snapshot 的 collection_id，找不到则查 upload_session 表补充
- **task auto-recovery 限制**：`task_projection/routes.py:187` 每次只恢复最多 3 条 stuck projection

## 跨模块开发提示
- 新增路由时在 main.py 中 include_router；新增下游 API 时先在 config.py 加 base_url，再在 clients.py 加方法；新增投影类型时在 projector.py 加 apply 逻辑，在 repository.py 加 repository，在 persistence 加 Model
- 修改 AGENTS.md 或 api.md 时，同步更新 workbench-api.md（最终设计文档）以及 contracts/openapi/workbench-api.yaml
