# services/admin 最终设计

## 1. 定位

`services/admin` 是 **Enterprise KnowledgeBase 平台的管理后台**，面向平台管理员、运维人员。

它是 `admin-console` 前端**唯一的后端入口**。前端不直接对接 `indexing`、`approval-service`、`retrieval`、`access`。

`services/admin` 不只是"代理转发"，它有自己必须承担的业务逻辑：

- **统一鉴权**：所有 admin 操作经过同一套角色权限检查
- **统一审计**：所有控制操作必须写 `ops_audit_log`
- **查询聚合**：trace timeline、跨表审计等查询在 admin 层做聚合，前端不可能直接查 DB
- **错误包装**：下游失败时返回统一错误码，不暴露内部细节
- **平台控制面**：`collections`、用户、角色、API Key、Parser Profile、Retrieval Profile、collection 默认绑定由 admin 作为管理 owner
- **本地配置**：`alert_rules`、`eval_datasets`、`bad_cases` 等是 admin 本地数据模型（待补齐）
- **代理执行**：对 chunk、approval、index 等运行时状态的控制操作，通过内部 API 转发给正确的 runtime owner 执行

核心价值：
- Collection 管理与全局配置管理（parser profile、retrieval profile、api key）
- 审批覆盖（对已决策 ticket 的人工 override）—— **待补齐**
- 质量评测闭环 —— **待补齐**
- 运维控制与审计

## 2. 三方入口边界

平台最终态有三个前端入口，彼此独立：

| 入口 | 面向用户 | 核心场景 | 对应后端 |
|------|---------|---------|---------|
| `access` REST/MCP | 外部应用/AI Agent | 检索知识 | `services/access` |
| `workbench-api` | 文档处理人员/业务人员/审批人员 | 上传文档、ParseSnapshot 预览、调 parser 参数沙盒、chunk 确认、审批 | `services/workbench-api` |
| `admin-console` | 平台管理员/运维 | 全局配置、审批覆盖、质量评测、运维控制 | `services/admin` |

## 3. 技术栈

- **单体 FastAPI**（Python）—— **已实现**
- **REST**：控制操作（retry、cancel、approve、archive、配置 CRUD）—— **已实现（部分）**
- **GraphQL**：审计查询聚合（trace timeline、跨表关联、分页过滤）—— **待补齐**
- **鉴权**：query 前置过滤器（数据隔离）+ resolver 层敏感字段控制 —— **待补齐**
- **认证**：`admin_users` 表 + pbkdf2_sha256 密码哈希 + HS256 JWT（可配置 issuer/audience 校验）；smoke/test mode 使用默认 secret，production mode 通过 `ADMIN_JWT_ISSUER`/`ADMIN_JWT_AUDIENCE` + `AUTH_MODE=production` 关闭默认 secret —— **已实现**

不引入动态 schema。不引入 GraphQL mutation 做控制操作。

### 3.1 契约基线

admin 实施必须建立在已完成的 Contract Stabilization Gate 之上。所有新 API 和 examples 必须使用当前 canonical wire 字段：

| 概念 | Canonical wire |
|------|----------------|
| 检索查询文本 | `query` |
| token budget | `token_budget` |
| 检索结果列表 | `evidence_items` |
| 文档 ID | `doc_id` |
| evidence/chunk ID | `evidence_id` |
| 展示内容 | `content` |

禁止在新跨服务 API 中重新引入 `query_text`、`max_context_tokens`、`result_chunks`、`final_doc_id`、`chunk_id`、`display_text` 作为 wire 字段。若底层既有数据库列或本地 domain 字段仍使用旧名，必须在 adapter 层显式映射到 canonical wire。发布域内部仍可保留 `final_doc_id` 作为持久化/domain 名，但 admin 对外 API 应暴露 `doc_id`。

### 3.2 架构护栏

`services/admin` 应按模块化控制面实现，不要做成单层杂糅的 routes/repository 容器。当前已实现：

- `identity`：`admin_users`、`admin_sessions`、JWT、角色与租户过滤 —— **已实现**
- `collection_catalog`：Collection、生命周期、默认绑定、访问策略 —— **已实现**
- `profile_registry`：ParserProfile、RetrievalProfile、API Key 控制面 —— **已实现**
- `ops_audit`：ops_audit_log 查询 —— **已实现**
- `document_ops`：published document archive/retract/reindex —— **已实现**
- `ops_control`：override、reindex、archive、retract、cache purge —— **部分实现（仅 archive/retract/reindex）**
- `observability`：trace timeline、audit、metrics、eval、bad case —— **待补齐**

护栏规则：

- published profile 不能原地改，只能新 version / new publish —— **已实现**
- collection 默认绑定必须版本化，历史任务可回放 —— **已实现**
- GraphQL 只读 read model / projection，不直接驱动控制动作 —— **待补齐**
- 所有控制动作必须带 `trace_id`、`idempotency_key`、`actor` —— **已实现（document_ops）**
- owner API 失败时，本地 projection 不得标记成功 —— **已实现**

## 4. 操作模式

所有控制操作统一走三步：

1. **鉴权**：检查 `admin_user` 的角色权限 —— **已实现**
2. **审计**：写 `ops_audit_log`（actor、action、target、before_state、after_state、reason）—— **已实现**
3. **执行**：控制面对象写 admin 本地表；运行时对象调 owner 服务内部 API，绝不直接操作下游表 —— **已实现**

所有控制动作都必须有稳定 command envelope：

```text
command_id
trace_id
idempotency_key
actor
tenant_id
collection_id
target_type
target_id
reason
payload
```

`idempotency_key` 必须来自 admin 本地稳定对象或业务目标，例如 `ops_audit_log_id`、`api_key_id:rotate:version`、`collection_id:binding:version`，不能使用随机重试 ID。

如果下游 API 调用失败：
- 前端收到统一包装的错误码（如 `DOWNSTREAM_UNAVAILABLE`、`OP_TIMEOUT`、`CONFLICT`），不暴露下游内部错误细节
- 日志和 trace 中记录完整的下游失败原因

如果下游 API 暂时不存在，则 admin 的该功能标记为"依赖下游 API，待补齐"。

## 5. 功能域

### 5.1 审批覆盖（Override）—— 待补齐

- **注意**：普通审批（Pending Ticket 列表、单票详情、Approve / Reject / Return）在 `workbench-api`
- admin 只处理 **Override**：对已决策 ticket 的人工覆盖
- 操作需更高级别权限（`PLATFORM_ADMIN` 或 `KNOWLEDGE_ADMIN`）
- 必须记录 override 原因，写 `ops_audit_log`
- 下游代理：调 `approval-service` 的 `/internal/tickets/{id}/override`
- **状态**：路由尚未实现

### 5.2 分块策略工作台（Parser Profile 模板）—— 已实现

- Parser Profile CRUD：定义 `naive`、`presentation`、`paper`、`qa` 等 profile 的名称、版本、默认参数和可用范围 —— **已实现**
- `services/admin` 是 Parser Profile 控制面 owner，负责创建、编辑、发布、停用和 collection 默认绑定 —— **已实现**
- `services/indexing` 是 Parser Profile 运行时 owner，负责校验 profile 是否可执行、解析语义、ParseSnapshot 生成和 materialization
- **生效发布流程**：
  1. admin 创建/编辑 profile（状态为 `draft`）—— **已实现**
  2. 发布时，admin 调用 `services/indexing` 的 `POST /internal/parser-profiles/validate` —— **已实现**
  3. indexing 返回 `canonical_config`、`profile_hash`、`validator_version`、`warnings` —— **已实现**
  4. 若 `valid=false`，admin 拒绝发布，写 `ops_audit_log`（`after_state=rejected`），返回 409 —— **已实现**
  5. 若 `valid=true`，admin 将 `runtime_canonical_config`、`profile_hash`、`validator_version`、`warnings` 写入 profile 记录，状态变为 `published` —— **已实现**
  6. 对已 `published` profile 再次发布时，自动创建新 version（旧版本 `retired`）—— **已实现**
- published ParserProfile 采用不可变版本；修改已发布配置时只能生成新 version，不允许原地覆盖旧 version —— **已实现**
- Collection 绑定：哪个 collection 默认用哪个 parser profile；绑定关系由 admin 持有，profile 可执行性由 indexing 校验 —— **已实现**
- **注意**：沙盒预览（选 profile 试跑单份文档、对比 chunk 结果）在 `workbench-api`
- admin 只管理全局模板和绑定关系，不直接做沙盒预览

### 5.3 Chunk 人工干预（运维兜底）—— 待补齐

- 按 `doc_id` + `index_version` 查看 chunk 列表（adapter 映射到底层 `final_doc_id`）—— **待补齐**
- 隐藏/显示单个 chunk → 调 `services/indexing` 内部 API —— **待补齐**
- 发布后 chunk 内容修改属于 `workbench-api` 的人工处理场景；admin 只提供运维兜底入口，实际替换仍由 `services/indexing` 创建 chunk revision、重新 embedding、重新写入索引
- 触发重新分块 → 发起新的 `IndexBuildRequested`（通过 intake-pipeline 的发布流程）
- 批量操作：按 collection 批量 hide/unhide —— **待补齐**

### 5.4 检索策略配置（Retrieval Profile Management）—— 已实现

- Retrieval Profile CRUD：BM25 权重、vector 权重、rerank 模型、expansion 策略、pack budget、fail policy —— **已实现（profile_config JSON 存储）**
- Profile 版本历史 —— **已实现**
- Collection 绑定：哪个 collection 用哪个 profile —— **已实现（通过 collection_profile_bindings）**
- `services/admin` 是 Retrieval Profile 控制面 owner，负责创建、编辑、发布、停用和 collection 默认绑定 —— **已实现**
- `services/retrieval` 是 Retrieval Profile 运行时 owner，负责校验 profile 是否可执行、召回/融合/rerank/pack 语义、read-path cache key 和执行行为
- **生效发布流程**：
  1. admin 创建/编辑 profile（状态为 `draft`）—— **已实现**
  2. 发布时，admin 调用 `services/retrieval` 的 `POST /internal/retrieval-profiles/validate` —— **已实现**
  3. retrieval 返回 `canonical_config`、`profile_hash`、`validator_version`、`warnings` —— **已实现**
  4. 若 `valid=false`，admin 拒绝发布，写 `ops_audit_log`（`after_state=rejected`），返回 409 —— **已实现**
  5. 若 `valid=true`，admin 将 `runtime_canonical_config`、`profile_hash`、`validator_version`、`warnings` 写入 profile 记录，状态变为 `published` —— **已实现**
  6. 对已 `published` profile 再次发布时，自动创建新 version（旧版本 `retired`）—— **已实现**
- published RetrievalProfile 采用不可变版本；修改已发布配置时只能生成新 version，并触发 profile hash / cache epoch 变化 —— **已实现**
- Retrieval cache 操作只允许通过 retrieval 内部 API 暴露的 purge/inspect 能力执行，admin 不直接操作 Redis key
- **发布时同步 projection**：发布成功后调用 `POST /internal/retrieval-profile-projections/sync` 同步到 retrieval runtime —— **已实现**

### 5.5 Collection 管理 —— 已实现

- `services/admin` 是 Collection Catalog 的事实 owner，负责 Collection CRUD、生命周期、默认策略绑定和基础访问策略 —— **已实现**
- Collection 默认绑定使用 versioned binding 记录；历史任务必须能回放到当时生效的 parser/retrieval/approval 绑定 —— **已实现**
- 配置 authority_level、access_policy —— **已实现**
- 绑定 parser_profile、retrieval_profile —— **已实现**
- 查看 collection 下的文档列表（published_documents）—— **待补齐**
- 批量操作：批量 reindex、批量 archive —— **待补齐**
- 下游服务不自行创建 collection，只引用 `collection_id` 并通过 admin internal API 或 collection projection 获取 collection 配置
- 批量 reindex、archive、retract 等文档/索引动作仍代理到 `services/intake-pipeline` / `services/indexing` 的 owner API

### 5.6 API Key 管理 —— 已实现

- ApiKey Registry CRUD —— **已实现**
- 分配 knowledge_scopes、roles、debug_permission、token_budget 限额 —— **已实现**
- 启用/禁用 key —— **已实现**
- 创建、轮换、吊销、过期、scope 修改都由 `services/admin` 管理 —— **已实现**
- 查看 key 的调用频率和审计日志 —— **待补齐**
- `services/admin` 是 API Key 控制面 owner，持有 key registry 和 key lifecycle —— **已实现**
- `services/access` 是 API Key 运行时 consumer，负责请求认证、scope enforcement、限流、调用审计和本地验证缓存
- access 只能通过 admin 暴露的只读 projection、只读表权限或同步 API 获取 key registry，不拥有 API Key 写权
- **API Key projection 同步到 access**：客户端代码已存在（`AccessClient.sync_api_key_projection`），但尚未在 API Key 生命周期操作中调用 —— **待补齐**

### 5.7 发布文档管理 —— 已实现

- Published Document 列表（支持按 collection、state 过滤）—— **待补齐**
- 查看生命周期状态、active index version、asset paths —— **待补齐**
- 操作：Archive / Retract / Reindex / Restore —— **已实现（archive/retract/reindex）**
- 下游代理：调 `services/intake-pipeline`（publishing domain）和 `services/indexing` 内部 API —— **已实现**

#### 已实现的管理端点

```text
POST /admin/documents/{final_doc_id}/archive   # 归档已发布文档 —— 已实现
POST /admin/documents/{final_doc_id}/retract   # 撤回已发布文档 —— 已实现
POST /admin/documents/{final_doc_id}/reindex   # 触发重新索引 —— 已实现
```

**权限要求**：`knowledge_admin` 或 `platform_admin`

**命令信封**：所有操作均使用标准 command envelope

```json
{
  "command_id": "cmd_001",
  "trace_id": "trc_001",
  "idempotency_key": "idem_001",
  "actor": "admin@example.com",
  "reason": "annual archive"
}
```

**archive / retract 流程**：
1. 鉴权（检查 `knowledge_admin` / `platform_admin`）
2. 调 publishing-worker 的 archive/retract 端点更新 published_document 状态
3. 写 `ops_audit_log`（`action=DOCUMENT_ARCHIVED` / `DOCUMENT_RETRACTED`）
4. 下游失败时返回统一错误码，不写本地 success 状态

**reindex 流程**：
1. 鉴权
2. 从 indexing 查询当前 parse snapshot（通过 `parse_snapshot_id`）
3. 构造完整 `IndexBuildRequestedCommand`，`request_type="reindex"`
4. 调 indexing `POST /internal/index-jobs` 提交重建任务
5. 写 `ops_audit_log`（`action=DOCUMENT_REINDEXED`）
6. 返回 `job_id` 供轮询

**失败处理**：
- publishing-worker / indexing 不可达：返回 `DOWNSTREAM_UNAVAILABLE`
- 文档不存在：返回 `404`
- 无权操作：返回 `403`

### 5.8 审计与链路追踪 —— 部分实现

- **Ops Audit Log**（REST）：所有 admin 操作记录 —— **已实现（GET/POST /admin/ops/audit-log）**
- **Trace Timeline**（GraphQL）：trace + steps + artifacts + 跨服务关联（intake job / ticket / index build）—— **待补齐**
- **Job History**（GraphQL）：所有 job 类型的状态历史 —— **待补齐**
- **Approval Audit**（GraphQL）：ticket + audit log 完整链路 —— **待补齐**
- 聚合查询只能读取 owner 服务暴露的只读视图、投影表或报表 schema，不能用跨服务 join 的结果驱动控制操作

### 5.9 质量评测（Eval）—— 待补齐

- **评测集管理**：question-answer pair 的 CRUD —— **待补齐**
- **Bad Case 管理**：录入 bad case，关联 query/chunk/expected_result，追踪修复状态 —— **待补齐**
- **自动评测流水线触发**：对指定 collection + profile 跑自动评测 —— **待补齐**
- **质量趋势看板**：NDCG、MRR、Recall@K 趋势 —— **待补齐**
- 评测结果数据模型由 admin 本地维护 —— **待补齐**

### 5.10 系统监控 —— 待补齐

- 服务健康状态（聚合各服务 `/health`）—— **待补齐**
- 队列深度（intake job 积压、index build 排队）—— **待补齐**
- LLM 调用成本（读 `llm_call_log` + `llm_cost_daily`）—— **待补齐**
- Collection 容量（chunk 数、存储量）—— **待补齐**
- 告警规则配置（job 失败率阈值、队列深度阈值、成本阈值）—— **待补齐**

## 6. 下游内部 API 依赖清单

admin 的以下功能依赖下游服务暴露内部 API。如果 API 暂不存在，该功能标记为"待补齐"：

| 功能 | 下游服务 | 需要的内部 API | 状态 |
|------|---------|--------------|------|
| 审批覆盖 | `approval-service` | `POST /internal/tickets/{id}/override` | 待补齐 |
| 解析预览 | `services/indexing` | `POST /internal/parse-previews`（已有）| 已实现（client 存在）|
| 查询 ParseSnapshot | `services/indexing` | `GET /internal/parse-snapshots/{id}`（已有）| 已实现（reindex 中使用）|
| Chunk 隐藏/显示 | `services/indexing` | `PATCH /internal/chunks/{id}/visibility` | 待补齐 |
| 索引版本激活/回滚 | `services/indexing` | `POST /internal/index-versions/{id}/activate` | 待补齐 |
| 索引版本清理 | `services/indexing` | `POST /internal/index-versions/{id}/cleanup` | 待补齐 |
| 发布文档 archive | `publishing-worker` | `POST /internal/published-documents/{id}/archive` | 已实现 |
| 发布文档 retract | `publishing-worker` | `POST /internal/published-documents/{id}/retract` | 已实现 |
| Parser Profile 校验/canonicalize | `services/indexing` | `POST /internal/parser-profiles/validate` | 已实现 |
| Retrieval Profile 校验/canonicalize | `services/retrieval` | `POST /internal/retrieval-profiles/validate` | 已实现 |
| Retrieval Profile projection 同步 | `services/retrieval` | `POST /internal/retrieval-profile-projections/sync` | 已实现 |
| API Key projection 同步 | `services/access` | `POST /internal/api-key-projections/sync` | 待补齐（client 已存在，未在生命周期中调用）|
| Retrieval cache 清理/查看 | `services/retrieval` | `POST /internal/cache/purge` / `GET /internal/cache/stats` | 待补齐 |

## 7. 控制面与运行时所有权矩阵

| 对象 | 控制面 owner | 运行时 owner/consumer | admin 角色 | workbench 角色 | 写路径 |
|------|--------------|----------------------|------------|----------------|--------|
| `Collection` | `services/admin` | 各服务引用 collection_id | CRUD、生命周期、默认绑定、访问策略 | 只读选择、按权限使用 | admin 本地表 |
| `AdminUser` / human roles | `services/admin` | admin/workbench 本地验签 | CRUD、登录、JWT 签发 | 本地验签、只读角色 | admin 本地表 |
| `ParserProfile` | `services/admin` | `services/indexing` | CRUD、发布、停用、绑定 collection 默认值 | 只读选择、per-document override | admin 本地表 + indexing validate |
| `RetrievalProfile` | `services/admin` | `services/retrieval` | CRUD、发布、停用、绑定 collection 默认值 | 无 | admin 本地表 + retrieval validate + projection sync |
| `ApiKey` / external scope | `services/admin` | `services/access` | 创建、轮换、吊销、scope 管理 | 无 | admin 本地表 + access projection（待补齐）|
| `SourceFile` / `IntakeJob` | `intake-pipeline` | `intake-pipeline` | 查询、重放、运维（待补齐） | 上传、看进度 | intake internal API |
| `ApprovalTicket` | `approval-service` | `approval-service` | override（待补齐） | pending review、decide | approval internal API |
| `AgentReviewArtifact` | `intake-pipeline` / `approval-service` | approval/workbench 展示 | 查询、审计 | 展示证据、辅助定位问题 | owner internal API |
| `PublishedDocument` | publishing domain in `intake-pipeline` | retrieval/indexing/access 读取投影 | archive/retract/reindex（已实现） | 只读结果 | intake/publishing internal API |
| `ParseSnapshot` | `services/indexing` | `services/indexing` | 查询、诊断 | 预览、对比 | indexing internal API |
| `ChunkRevision` / indexed chunk replacement | `services/indexing` | indexing/retrieval | 运维兜底（待补齐） | 发起人工修改 | indexing internal API |

## 8. Admin 本地数据模型

admin 需要维护自己的表（不与其他服务共享写权）：

### 8.1 `admin_users` —— 已实现

| 字段 | 类型 | 约束 |
|------|------|------|
| `user_id` | String(128) | PK |
| `email` | String(255) | unique, not null |
| `password_hash` | String(255) | not null |
| `display_name` | String(255) | default "" |
| `roles` | JSON | default list |
| `clearance_level` | Integer | default 0 |
| `allowed_tenants` | JSON | default list |
| `allowed_collections` | JSON | default list |
| `created_at` | DateTime | default utcnow |
| `updated_at` | DateTime | default utcnow |
| `last_login_at` | DateTime | nullable |

### 8.2 `admin_sessions` —— 已实现

| 字段 | 类型 | 约束 |
|------|------|------|
| `session_id` | String(128) | PK |
| `user_id` | String(128) | FK(admin_users), not null |
| `token_hash` | String(255) | not null |
| `expires_at` | DateTime | not null |
| `ip_address` | String(64) | default "" |
| `user_agent` | String(512) | default "" |

### 8.3 `collections` —— 已实现

| 字段 | 类型 | 约束 |
|------|------|------|
| `collection_id` | String(64) | PK |
| `tenant_id` | String(64) | FK(tenants), not null |
| `name` | String(255) | not null |
| `description` | String(1024) | default "" |
| `lifecycle_state` | String(32) | default "active", not null |
| `authority_level` | Integer | default 0 |
| `access_policy` | JSON | default dict |
| `default_parser_profile_id` | String(64) | default "" |
| `default_retrieval_profile_id` | String(64) | default "" |
| `default_approval_policy_id` | String(64) | default "" |
| `created_by` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |
| `updated_by` | String(128) | default "" |
| `updated_at` | DateTime | default utcnow |

### 8.4 `collection_profile_bindings` —— 已实现

| 字段 | 类型 | 约束 |
|------|------|------|
| `binding_id` | String(128) | PK |
| `tenant_id` | String(64) | FK(tenants), not null |
| `collection_id` | String(64) | FK(collections), not null |
| `parser_profile_id` | String(128) | default "" |
| `retrieval_profile_id` | String(128) | default "" |
| `approval_policy_id` | String(128) | default "" |
| `effective_from` | DateTime | not null |
| `effective_to` | DateTime | nullable |
| `binding_version` | Integer | default 1, not null |
| `config_hash` | String(128) | default "" |
| `created_by` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |

索引：`ix_bindings_collection_version` (collection_id, binding_version)

### 8.5 `alert_rules` —— 待补齐

| 字段 | 类型 | 约束 |
|------|------|------|
| `rule_id` | String(64) | PK |
| `rule_type` | String(32) | not null |
| `threshold_value` | Float | |
| `collection_id` | String(64) | nullable |
| `enabled` | Boolean | default True |
| `created_by` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |
| `updated_at` | DateTime | default utcnow |

### 8.6 `eval_datasets` —— 待补齐

| 字段 | 类型 | 约束 |
|------|------|------|
| `dataset_id` | String(64) | PK |
| `tenant_id` | String(64) | not null |
| `collection_id` | String(64) | not null |
| `name` | String(255) | not null |
| `description` | String(1024) | default "" |
| `question_answer_pairs` | JSON | default list |
| `created_by` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |

### 8.7 `bad_cases` —— 待补齐

| 字段 | 类型 | 约束 |
|------|------|------|
| `bad_case_id` | String(64) | PK |
| `dataset_id` | String(64) | FK, nullable |
| `query` | String(2048) | |
| `expected_evidence_id` | String(128) | |
| `actual_evidence_id` | String(128) | |
| `collection_id` | String(64) | |
| `retrieval_profile_id` | String(128) | |
| `status` | String(32) | default "open" |
| `assigned_to` | String(128) | nullable |
| `resolution_note` | String(2048) | nullable |
| `created_by` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |
| `updated_at` | DateTime | default utcnow |

### 8.8 `parser_profiles` —— 已实现

| 字段 | 类型 | 约束 |
|------|------|------|
| `parser_profile_id` | String(128) | PK |
| `name` | String(255) | not null |
| `description` | String(1024) | default "" |
| `parser_id` | String(64) | default "naive" |
| `parser_config` | JSON | default dict |
| `runtime_canonical_config` | JSON | nullable |
| `profile_hash` | String(128) | default "" |
| `validator_version` | String(64) | default "" |
| `warnings` | JSON | default list |
| `version` | Integer | default 1, not null |
| `state` | String(32) | default "draft", not null |
| `created_by` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |
| `updated_by` | String(128) | default "" |
| `updated_at` | DateTime | default utcnow |

### 8.9 `retrieval_profiles_admin` —— 已实现

**注意**：表名为 `retrieval_profiles_admin`，不是 `retrieval_profiles`。`retrieval_profiles` 表是 retrieval 运行时使用的 projection 表。

| 字段 | 类型 | 约束 |
|------|------|------|
| `retrieval_profile_id` | String(128) | PK |
| `name` | String(255) | not null |
| `description` | String(1024) | default "" |
| `profile_config` | JSON | default dict |
| `runtime_canonical_config` | JSON | nullable |
| `profile_hash` | String(128) | default "" |
| `validator_version` | String(64) | default "" |
| `warnings` | JSON | default list |
| `version` | Integer | default 1, not null |
| `state` | String(32) | default "draft", not null |
| `created_by` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |
| `updated_by` | String(128) | default "" |
| `updated_at` | DateTime | default utcnow |

### 8.10 `api_key_registry` —— 已实现

| 字段 | 类型 | 约束 |
|------|------|------|
| `api_key_id` | String(128) | PK |
| `tenant_id` | String(64) | FK(tenants), default "" |
| `display_name` | String(255) | default "" |
| `agent_type_id` | String(128) | default "" |
| `key_hash` | String(255) | default "" |
| `knowledge_scopes` | JSON | default list |
| `roles` | JSON | default list |
| `debug_permission` | Boolean | default False, not null |
| `max_context_tokens` | Integer | default 4096, not null |
| `token_budget_limit` | Integer | default 4096, not null |
| `state` | String(32) | default "active", not null |
| `expires_at` | DateTime | nullable |
| `created_by` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |
| `updated_by` | String(128) | default "" |
| `updated_at` | DateTime | default utcnow |
| `last_rotated_at` | DateTime | nullable |

索引：`ix_api_key_registry_state`, `ix_api_key_registry_tenant`

**注意**：`token_budget_limit` 是 admin 控制面字段；`max_context_tokens` 是兼容旧 Java 服务的内部列名。如果 `services/access` 既有持久化或 projection 仍使用 `max_context_tokens` 内部列名，必须由 API Key projection adapter 显式映射，不能把旧列名暴露成 admin wire 字段。

### 8.11 `ops_audit_log` —— 已实现

| 字段 | 类型 | 约束 |
|------|------|------|
| `audit_id` | String(64) | PK |
| `command_id` | String(128) | default "" |
| `trace_id` | String(64) | default "" |
| `idempotency_key` | String(512) | default "" |
| `actor_id` | String(128) | not null |
| `tenant_id` | String(64) | default "" |
| `collection_id` | String(64) | nullable |
| `action` | String(32) | not null |
| `target_type` | String(32) | not null |
| `target_id` | String(128) | not null |
| `before_state` | String(256) | nullable |
| `after_state` | String(256) | nullable |
| `reason` | String(2048) | nullable |
| `payload_hash` | String(128) | default "" |
| `created_at` | DateTime | default utcnow |

索引：`ix_ops_audit_target`, `ix_ops_audit_actor`, `ix_ops_audit_created`, `ix_ops_audit_trace`, `ix_ops_audit_idempotency`

## 9. GraphQL Schema —— 待补齐

当前代码中**未实现** GraphQL 端点。以下为设计阶段的 schema 草案：

```graphql
type Trace {
  trace_id: String!
  run_kind: String!
  tenant_id: String!
  collection_id: String!
  root_status: String!
  created_at: DateTime!
  steps: [TraceStep!]!
  artifacts: [TraceArtifact!]!
  linked_intake_job: IntakeJob
  linked_approval_ticket: ApprovalTicket
  linked_index_build_job: IndexBuildJob
}

type TraceStep {
  step_name: String!
  status: String!
  summary: String!
  details_json: JSON
  created_at: DateTime!
}

type TraceArtifact {
  artifact_ref: String!
  artifact_kind: String!
  summary: String!
  details_json: JSON
  created_at: DateTime!
}

type ApprovalTicket {
  ticket_id: String!
  state: String!
  preliminary_doc_id: String!
  collection_id: String!
  routing_recommendation: String!
  decision: String
  decision_actor: String
  confirmed_tags: [String!]
  audit_logs: [ApprovalAuditLog!]!
  parse_snapshot: ParseSnapshot
}

type PublishedDocument {
  published_document_id: String!
  doc_id: String!
  collection_id: String!
  state: String!
  active_index_version: String!
  version: Int!
  created_at: DateTime!
}

type Chunk {
  evidence_id: String!
  doc_id: String!
  collection_id: String!
  index_version_id: String!
  available_int: Int!
  content: String!
  section_path: [String!]!
  metadata: JSON
}

type Query {
  traceTimeline(trace_id: String!): Trace
  traces(
    tenant_id: String
    collection_id: String
    run_kind: String
    status: String
    limit: Int
    offset: Int
  ): [Trace!]!
  
  approvalTickets(
    state: String
    collection_id: String
    limit: Int
    offset: Int
  ): [ApprovalTicket!]!
  
  publishedDocuments(
    collection_id: String
    state: String
    limit: Int
    offset: Int
  ): [PublishedDocument!]!
  
  chunks(
    doc_id: String!
    index_version_id: String
    available_only: Boolean
  ): [Chunk!]!
}
```

## 10. REST API 核心路由

以下为**实际已实现**的路由列表，标注实现状态：

```text
# Health
GET  /health                                    # 已实现

# Auth
POST /admin/auth/login                          # 已实现 —— email + password → JWT
POST /admin/auth/logout                         # 已实现 —— 作废 session（TODO: 完整 session invalidation）
GET  /admin/auth/me                             # 已实现 —— 当前用户信息

# Collections
GET    /admin/collections                       # 已实现
POST   /admin/collections                       # 已实现
GET    /admin/collections/{collection_id}       # 已实现
PATCH  /admin/collections/{collection_id}       # 已实现
POST   /admin/collections/{collection_id}/lifecycle   # 已实现
GET    /admin/collections/{collection_id}/bindings    # 已实现
GET    /admin/collections/{collection_id}/bindings/current   # 已实现
POST   /admin/collections/{collection_id}/bindings    # 已实现

# Parser Profiles
GET    /admin/parser-profiles                   # 已实现
POST   /admin/parser-profiles                   # 已实现
GET    /admin/parser-profiles/{parser_profile_id}   # 已实现
PATCH  /admin/parser-profiles/{parser_profile_id}   # 已实现
POST   /admin/parser-profiles/{parser_profile_id}/publish   # 已实现
POST   /admin/parser-profiles/{parser_profile_id}/transition   # 已实现

# Retrieval Profiles
GET    /admin/retrieval-profiles                # 已实现
POST   /admin/retrieval-profiles                # 已实现
GET    /admin/retrieval-profiles/{retrieval_profile_id}   # 已实现
PATCH  /admin/retrieval-profiles/{retrieval_profile_id}   # 已实现
POST   /admin/retrieval-profiles/{retrieval_profile_id}/publish   # 已实现
POST   /admin/retrieval-profiles/{retrieval_profile_id}/transition   # 已实现

# API Keys
GET    /admin/api-keys                          # 已实现
POST   /admin/api-keys                          # 已实现
GET    /admin/api-keys/{api_key_id}             # 已实现
PATCH  /admin/api-keys/{api_key_id}             # 已实现
POST   /admin/api-keys/{api_key_id}/rotate      # 已实现
POST   /admin/api-keys/{api_key_id}/disable     # 已实现
POST   /admin/api-keys/{api_key_id}/revoke      # 已实现

# Ops Audit
GET    /admin/ops/audit-log                     # 已实现
POST   /admin/ops/audit-log                     # 已实现

# Document Lifecycle Ops
POST   /admin/documents/{final_doc_id}/archive  # 已实现
POST   /admin/documents/{final_doc_id}/retract  # 已实现
POST   /admin/documents/{final_doc_id}/reindex  # 已实现

# 以下为设计阶段定义但尚未实现的路由：

# 运维控制 —— 待补齐
POST   /admin/ops/jobs/{id}/retry               # 待补齐
POST   /admin/ops/jobs/{id}/cancel              # 待补齐
POST   /admin/ops/index-versions/{id}/rollback  # 待补齐
POST   /admin/ops/index-versions/{id}/cleanup   # 待补齐
POST   /admin/ops/intake-jobs/{id}/replay       # 待补齐
POST   /admin/ops/published-documents/{id}/restore   # 待补齐
POST   /admin/ops/tickets/{id}/override         # 待补齐
POST   /admin/ops/chunks/{id}/hide              # 待补齐
POST   /admin/ops/chunks/{id}/unhide            # 待补齐
POST   /admin/ops/collections/{id}/reindex      # 待补齐

# 评测 —— 待补齐
GET    /admin/eval/datasets                     # 待补齐
POST   /admin/eval/datasets                     # 待补齐
GET    /admin/eval/datasets/{id}                # 待补齐
DELETE /admin/eval/datasets/{id}                # 待补齐
GET    /admin/eval/bad-cases                    # 待补齐
POST   /admin/eval/bad-cases                    # 待补齐
GET    /admin/eval/bad-cases/{id}               # 待补齐
PUT    /admin/eval/bad-cases/{id}               # 待补齐
POST   /admin/eval/runs                         # 待补齐
GET    /admin/eval/runs/{id}                    # 待补齐

# 监控 —— 待补齐
GET    /admin/health/services                   # 待补齐
GET    /admin/metrics/queues                    # 待补齐
GET    /admin/metrics/llm-costs                 # 待补齐
GET    /admin/metrics/collection-capacity       # 待补齐
GET    /admin/alert-rules                       # 待补齐
POST   /admin/alert-rules                       # 待补齐
PUT    /admin/alert-rules/{id}                  # 待补齐
DELETE /admin/alert-rules/{id}                  # 待补齐

# GraphQL —— 待补齐
POST   /admin/graphql                           # 待补齐
```

## 11. Agent 实施约束与验收标准

本设计交给实现 agent 执行时，必须按以下约束落地。禁止只做本地 CRUD 闭环来绕过跨服务契约。

### 11.1 Contracts-first

开始实现前必须先运行并确认项目级 Contract Stabilization Gate 仍为绿色：

```text
cd packages/contracts
uv run pytest tests/ -v

cd services/access
mvn test

cd services/retrieval
mvn test -Dtest='!RealSqliteIndexingRegistrySmokeTest'
```

任一 gate 失败时，先修契约，不得继续实现 admin。

所有跨服务 API、DTO、事件和示例必须先落到 `contracts/`：

- HTTP API：先更新 `contracts/openapi/admin.yaml`，再实现 FastAPI 路由
- DTO shape：先更新或新增 `contracts/schemas/*.schema.json`
- 示例 payload：补 `contracts/examples/*.json`
- Python 模型：同步 `packages/contracts` / `packages/persistence`
- Java consumer mirror：如果 access/retrieval 需要消费 admin projection，必须同步本地 mirror 或生成代码

实现不得在 service-local model 中私自发明 wire 字段。字段名、枚举值、required/nullable 语义以 `contracts/` 为准。
新增 admin wire 字段必须遵守第 3.1 节 canonical wire；旧字段名只能作为内部持久化列或 adapter 输入输出，不得进入 OpenAPI/examples。

### 11.2 禁止的捷径

实现 agent 不得采用以下方式交付：

- 只实现 `services/admin` 本地表 CRUD，但不更新 `contracts/openapi/admin.yaml`
- 让 admin 直接写 `indexing`、`retrieval`、`access`、`approval-service`、`intake-pipeline` 的 owner 表
- 让 admin 直接操作 retrieval Redis cache key
- 在 admin 内部复制 parser/retrieval/access 的运行时逻辑
- 用 mock/stub 假装下游已联通，却不留下明确的 contract test 和 TODO gate
- 新增字段只改 Python Pydantic，不同步 JSON Schema / OpenAPI / examples

### 11.3 必须拆分的交付阶段

**当前进度：Phase 1 基本完成，Phase 2 部分完成**

Phase 0：契约补齐

- 补齐 `contracts/openapi/admin.yaml` 中缺失的 Collection、ParserProfile、RetrievalProfile、ApiKey、ops audit、cache purge 管理接口
- 补齐 `AdminCollection`、`ParserProfile`、`RetrievalProfile`、`ApiKeyRegistry` 的 schema 和 examples
- 明确 profile validate/canonicalize API 的 request/response shape

Phase 1：admin 本地控制面 —— **已完成**

- `admin_users`、`admin_sessions`、`collections`、`collection_profile_bindings`
- `parser_profiles`、`retrieval_profiles_admin`、`api_key_registry`
- `ops_audit_log`
- 权限校验、tenant/collection 过滤
- API wire 使用 `token_budget_limit`；access projection 如需 `max_context_tokens`，在 adapter 中映射并覆盖测试

Phase 2：runtime owner 联调 —— **部分完成**

- admin 发布 ParserProfile 前调用 indexing validate/canonicalize —— **已完成**
- admin 发布 RetrievalProfile 前调用 retrieval validate/canonicalize —— **已完成**
- admin 发布 RetrievalProfile 后同步 retrieval projection —— **已完成**
- API Key 创建/禁用/轮换后同步 access projection 或刷新 access key cache —— **待补齐**
- Collection 默认绑定变更后，相关服务能读到 projection 或 internal API —— **待补齐**
- profile publish / api key lifecycle / collection binding 变更都必须使用稳定 idempotency key，保证重试不产生双写 —— **已实现**

Phase 3：运维与观测 —— **待补齐**

- approval override、published document archive/retract/reindex —— **部分完成（archive/retract/reindex 已实现）**
- index activate/rollback/cleanup
- retrieval cache purge/stats
- GraphQL read-only timeline 和 audit 查询
- eval datasets、bad cases、alert rules
- health aggregation、metrics、monitoring

### 11.4 联调验收

每个跨服务能力必须至少有一条契约测试和一条集成测试：

- Contract test：用 `contracts/examples` 验证 request/response 与 schema 一致
- Service integration test：admin 调真实 owner service 的 test server 或 contract stub
- Failure test：owner service 返回 4xx/409/5xx 时，admin 返回统一错误码并写 `ops_audit_log`
- Authorization test：无权限 collection、跨 tenant、缺角色必须 fail closed

### 11.5 API Key 与 profile 的验收条件

API Key：

- admin 创建 key 后，access 能用该 key 完成认证
- admin 禁用/吊销 key 后，access 在规定 cache TTL 内拒绝该 key
- scope 变更后，access 的 retrieval request scope 与 admin registry 一致
- token budget 限额从 admin `token_budget_limit` 正确同步/映射到 access runtime consumer

ParserProfile：

- admin 保存 published profile 前，必须经过 indexing validate/canonicalize —— **已满足**
- workbench 上传选择该 profile 后，indexing preview 使用同一个 canonical runtime view
- profile retire 后，不能再被新上传任务选择，但历史 ParseSnapshot 保留原 profile 引用

RetrievalProfile：

- admin 保存 published profile 前，必须经过 retrieval validate/canonicalize —— **已满足**
- collection 默认 retrieval profile 变更后，retrieval 使用新 profile hash 构造 cache key
- profile 变更必须触发相关 retrieval cache purge 或 content/profile epoch 更新
- retrieval profile projection 同步到 retrieval runtime —— **已满足**
