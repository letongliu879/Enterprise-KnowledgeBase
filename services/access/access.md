# access 运行时设计

## 1. 定位

`access` 是知识库对外入口，不是检索内核。

它的职责只有四件事：

1. 接住外部 REST / MCP 请求
2. 根据 `api_key` 查服务端登记信息
3. 构造受控的内部 retrieval 请求
4. 记录可追溯的访问审计

检索排序、召回、扩展、上下文打包都在 `services/retrieval`。

## 2. 当前主链

当前代码实际执行顺序如下：

1. `AccessRequestContextFilter` 对非 `/health`、`/actuator`、`/internal` 请求执行认证
2. `AccessAuthenticator` 读取 `X-API-Key` 与 `X-Agent-Instance-Id`
3. `ApiKeyRegistry` 从数据库表 `api_key_projection` 查 `agent_type_id`、`knowledge_scopes`、`roles`、`debug_permission`、`token_budget_limit`
   - 同时校验 `state = 'active'`、`expires_at` 未过期、`last_updated_at` 在 TTL 窗口内（代码硬编码 60 分钟）
   - 任一校验失败即 fail-closed，拒绝请求
4. `AccessGatewayService` 生成 `query_id`、`trace_id`
5. `LoggingAccessTraceRecorder` 记录 `access.request_accepted`
6. `DebugPolicy` 解析 `debug`
   - `none` 直接放行
   - `basic` 需要 `debug_permission`，否则降级为 `none`
   - `full` 需要 `debug_permission`，否则抛 `ACC_FORBIDDEN`
7. `RetrievalProfileSelector` 选择 `retrieval_profile_id`
   - 优先 `retrieval_profile_id`，其次兼容别名 `profile`，最后回退到配置项 `access.default-retrieval-profile-id`（默认 `ret_default`）
   - 若两者同时存在且不一致，直接抛 `ACC_INVALID_REQUEST`
   - 选定后调用 retrieval `GET /internal/retrieval-profiles/{profileId}` 确认存在且有效
8. `RetrieveRequestBuilder` 校验请求里的 `collection_scope` 是 `knowledge_scopes` 的子集
9. `LoggingAccessTraceRecorder` 记录 `access.retrieval_call`
10. `RetrievalClient` 调用 retrieval `POST /internal/retrieve`
11. `LoggingAccessTraceRecorder` 记录 `access.response` 或 `access.failure`

## 3. 身份与权限模型

当前正式模型已经收口为：

- `api_key`
  - 决定"谁在调用"和"能查什么"
  - **但 access 不是 API Key 的事实源**；admin 才是
  - access 只消费 admin 同步过来的 `api_key_projection`，并做 TTL 校验
- `agent_instance_id`
  - 只是实例态标识
  - 用于审计、trace
  - MCP Streamable HTTP 会话通过 `Mcp-Session-Id` header 维护状态

这意味着：

- 一个 `api_key` 可以对应很多 agent 实例
- 不能把 `agent_instance_id` 当成权限来源
- 客户端不再上传 tenant / platform
- 服务端不再依赖 HMAC 签名字段

## 4. 对外协议

### 4.1 REST

入口：

- `POST /v1/retrieve`

当前主字段：

- `query` (string, 必填)
- `collection_scope` (string[], 必填)
- `filters` (object)
- `language` (string)
- `cross_languages` (string[])
- `keyword` (boolean)
- `meta_data_filter` (object)
- `retrieval_profile_id` (string)
- `profile` (string, `retrieval_profile_id` 的兼容别名)
- `token_budget` (integer)
- `debug` (string, `none|basic|full`)

说明：

- `profile` 仍然是兼容别名，但正式字段是 `retrieval_profile_id`；两者冲突时报 `ACC_INVALID_REQUEST`
- `collection_scope` 必须是当前 `api_key` 允许范围的子集
- `retrieval_profile_id` 若未提供，回退到配置项 `access.default-retrieval-profile-id`（默认 `ret_default`），然后向 retrieval 确认存在

### 4.2 MCP

当前 transport 是 Spring AI MCP Server Streamable HTTP：

- `POST /mcp`

当前 tool：

- `search_enterprise_knowledge`

tool 参数：

- `query` (string, 必填)
- `knowledge_scope` (string, 必填)
- `retrieval_profile_id` (string)
- `token_budget` (integer)
- `debug` (string)

说明：

- MCP tool 当前一次只查一个 `knowledge_scope`
- `McpKnowledgeScopeMapper` 会把它转成单元素 `collection_scope`，并校验该 scope 在 api_key 允许范围内
- 每个 MCP 请求独立携带 `X-API-Key` + `X-Agent-Instance-Id`，由 `AccessRequestContextFilter` 统一认证
- Streamable HTTP 使用 `Mcp-Session-Id` header 维护会话状态
- `AccessRequestContextFilter` 会检测 session principal drift：若 `Mcp-Session-Id` 已绑定到其他 `api_key_id` / `agent_type_id` / `agent_instance_id` / `knowledge_scopes`，返回 403

协议版本说明：

- 当前 Spring AI MCP server 实际返回的协议版本是 `2024-11-05`
- 如果客户端发来更高版本，服务端会回退建议到这个版本

## 5. 与 retrieval 的边界

`access` 只向 `retrieval` 传受控内部请求，不传客户端自报权限。

实际下传的核心信息有：

- `query_id`
- `trace_id`
- `principal`（`principal_id` 由 `agent_type_id + ":" + agent_instance_id` 组成）
- `collection_scope`
- `query`
- `language`
- `cross_languages`
- `keyword`
- `meta_data_filter`
- `retrieval_profile_id`
- `filters`
- `include_deprecated`（硬编码 `false`）
- `token_budget`
- `debug_level`

## 6. API Key Projection Sync 架构

access 不再直接读取 admin 的 `api_key_registry` 表。admin 通过显式同步把 runtime 需要的最小字段推送到 access。

### 6.1 同步端点

- `POST /internal/api-key-projections/sync`

请求体为 command envelope：

- `command_id`, `trace_id`, `idempotency_key`, `actor`
- `tenant_id`, `target_type` (= `api_key_projection`), `target_id` (= `api_key_id`)
- `payload` — `ApiKeyProjection`

`idempotency_key` 保证同一 key 重复投递不会重复写入。

### 6.2 运行时表

access 维护自己的 `api_key_projection` 表：

| 字段 | 说明 |
|---|---|
| `api_key_id` | 主键 |
| `tenant_id` | 所属租户 |
| `agent_type_id` | 绑定的 agent 类型 |
| `knowledge_scopes` | 允许查询的 collection 列表（JSON） |
| `roles` | 角色列表（JSON） |
| `debug_permission` | 是否有 debug 权限 |
| `token_budget_limit` | 最大上下文 token 数 |
| `state` | `active` / `disabled` / `revoked` / `expired` |
| `expires_at` | 过期时间（nullable） |
| `projection_version` | 用于缓存失效的版本号 |
| `last_updated_at` | admin 侧最后更新时间 |
| `synced_at` | 写入 access 的时间 |
| `runtime_synced` | 是否已成功同步 |

### 6.3 TTL 与失效

- `last_updated_at` 必须在代码硬编码的最大陈旧时间内（60 分钟）
- 超时的 projection 被视为不可靠，`ApiKeyRegistry` 会拒绝并抛 `RegistryUnavailable`（HTTP 500）
- 这是 fail-closed 设计：宁可拒绝服务，也不接受过期的权限数据

### 6.4 State 校验与 fail-closed

`ApiKeyRegistry.resolve()` 在返回注册信息前必须同时满足：

1. `state = 'active'` — `disabled`/`revoked`/`expired` 一律拒绝
2. `expires_at IS NULL OR expires_at > NOW()` — 过期拒绝
3. `last_updated_at` 在 TTL 窗口内 — 超时拒绝

任一条件不满足 → `Unauthenticated`（401）或 `RegistryUnavailable`（500），不会降级到默认配置。

### 6.5 所有权边界

- **admin** 是 API Key 生命周期的事实源（创建、轮转、禁用、吊销）
- **access** 只是 runtime consumer，通过 projection sync 接收只读副本
- access 不回写 admin 表，也不在本地做 key 的生命周期操作
- `api_key_projection` 只是带 TTL 的缓存，不是事实源

## 7. 数据库事实源

当前运行时直接依赖这些表：

- `api_key_projection`
- `api_key_projection_idempotency`
- `run_traces`
- `run_steps`

其中：

- `api_key_projection` 是接入权限的运行时缓存（带 TTL 校验）
- `api_key_projection_idempotency` 记录已处理的同步命令 idempotency_key
- `run_traces` 记录一次查询的根状态
- `run_steps` 记录 access 入口的阶段步骤

`ApiKeyRegistry` 当前不再读 YAML，也不再读 `api_key_registry`。

## 8. 审计与排错

access 侧至少会记录这些步骤：

- `access.request_accepted`
- `access.retrieval_call`
- `access.response`
- `access.failure`

排查时优先按 `trace_id` 或 `query_id` 查：

1. `run_traces.run_trace_id = access_<query_id>`
2. `run_steps.trace_id = <trace_id>`

当前会写入的关键信息包括：

- `api_key_id`
- `agent_type_id`
- `agent_instance_id`
- `knowledge_scopes`
- `retrieval_profile_id`
- `result_count`
- `citation_count`
- `debug_ref`
- `error_type` / `error_message`（失败时）

## 9. 配置

当前主配置在 [src/main/resources/application.yaml](./src/main/resources/application.yaml)。

关键项：

- `server.port=18081`
- `spring.datasource.*`
- `access.default-retrieval-profile-id`（默认 `ret_default`）
- `access.retrieval.base-url`（默认 `http://127.0.0.1:18082`）
- `access.retrieval.connect-timeout`（默认 `1s`）
- `access.retrieval.read-timeout`（默认 `3s`）
- `spring.ai.mcp.server.enabled=true`
- `spring.ai.mcp.server.name=reality-rag-access`
- `spring.ai.mcp.server.version=0.1.0`
- `spring.ai.mcp.server.type=SYNC`
- `spring.ai.mcp.server.protocol=STREAMABLE`
- `spring.ai.mcp.server.streamable-http.mcp-endpoint=/mcp`

## 10. 当前实现边界

文档必须和代码现状一致，当前边界如下：

- 已经是 DB-backed `api_key_projection`（通过 `/internal/api-key-projections/sync` 消费 admin 投影）
- 已经有 fail-closed 的 state / expires_at / TTL 校验
- 已经有真实 MCP Streamable HTTP 端点（`/mcp`）和 session principal drift 检测
- 已经把审计写入 DB（`run_traces`、`run_steps`）
- 检索 profile 已走 retrieval 端真实校验，不再本地 fallback
- 还没有真正的限流实现
- 认证方式：`X-API-Key` + `X-Agent-Instance-Id` header，查 `api_key_projection` 表验权 — 不做 end-user JWT（JWT 认证在 admin/workbench-api 层，access 作为 Agent-facing gateway 使用 API key）
- 还没有在 access 本地做 key 生命周期操作（仍由 admin 控制）
- `AccessAuthenticator` 中预留了 `/sse` 的 clientType 判断，但服务端并未实际暴露 `/sse` 端点
