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

1. `AccessAuthenticator` 读取 `X-API-Key` 与 `X-Agent-Instance-Id`
2. `ApiKeyRegistry` 从数据库表 `api_key_projection` 查 `agent_type_id`、`knowledge_scopes`、`roles`、`debug_permission`、`token_budget_limit`
   - 同时校验 `state = 'active'`、`expires_at` 未过期、`last_updated_at` 在 TTL 窗口内
   - 任一校验失败即 fail-closed，拒绝请求
3. `AccessGatewayService` 生成 `query_id`、`trace_id`
4. `DebugPolicy` 解析 `debug`
5. `RetrievalProfileSelector` 调用 retrieval `/internal/retrieval-profiles/{profileId}` 确认 profile 存在且有效
6. `RetrieveRequestBuilder` 校验请求里的 `collection_scope` 是 `knowledge_scopes` 的子集
7. `RetrievalClient` 调用 `retrieval /internal/retrieve`
8. `LoggingAccessTraceRecorder` 把入口审计写入 `run_traces`、`run_steps`

`RateLimitGuard` 现在只是预留挂点，当前代码还没有真正做限流。

## 3. 身份与权限模型

当前正式模型已经收口为：

- `api_key`
  - 决定”谁在调用”和”能查什么”
  - **但 access 不是 API Key 的事实源**；admin 才是
  - access 只消费 admin 同步过来的 `api_key_projection`，并做 TTL 校验
- `agent_instance_id`
  - 只是实例态标识
  - 用于 MCP session 绑定、审计、trace

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

- `query`
- `collection_scope`
- `filters`
- `language`
- `cross_languages`
- `keyword`
- `meta_data_filter`
- `retrieval_profile_id`
- `profile`
- `token_budget`
- `debug`

说明：

- `profile` 仍然是兼容别名，但正式字段是 `retrieval_profile_id`
- `collection_scope` 必须是当前 `api_key` 允许范围的子集
- `retrieval_profile_id` 必填，不再回退到 `ret_default`

### 4.2 MCP

当前 transport 是 Spring AI WebMVC Streamable HTTP：

- `POST /mcp`

当前 tool：

- `search_enterprise_knowledge`

tool 参数：

- `query`
- `knowledge_scope`
- `retrieval_profile_id`
- `token_budget`
- `debug`

说明：

- MCP tool 当前一次只查一个 `knowledge_scope`
- `McpKnowledgeScopeMapper` 会把它转成单元素 `collection_scope`
- 每个 MCP 请求独立携带 `X-API-Key` + `X-Agent-Instance-Id`，由 `AccessRequestContextFilter` 统一认证
- Streamable HTTP 使用 `Mcp-Session-Id` header 维护会话状态

协议版本说明：

- 当前 Spring AI MCP server 实际返回的协议版本是 `2024-11-05`
- 如果客户端发来更高版本，服务端会回退建议到这个版本

## 5. 与 retrieval 的边界

`access` 只向 `retrieval` 传受控内部请求，不传客户端自报权限。

实际下传的核心信息有：

- `query_id`
- `trace_id`
- `principal`
- `collection_scope`
- `query`
- `retrieval_profile_id`
- `filters`
- `token_budget`
- `debug_level`

`principal.principal_id` 当前由 `agent_type_id + ":" + agent_instance_id` 组成。

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
| `knowledge_scopes` | 允许查询的 collection 列表 |
| `roles` | 角色列表 |
| `debug_permission` | 是否有 debug 权限 |
| `token_budget_limit` | 最大上下文 token 数 |
| `state` | `active` / `disabled` / `revoked` / `expired` |
| `expires_at` | 过期时间（nullable） |
| `projection_version` | 用于缓存失效的版本号 |
| `last_updated_at` | admin 侧最后更新时间 |
| `synced_at` | 写入 access 的时间 |
| `runtime_synced` | 是否已成功同步 |

### 6.3 TTL 与失效

- `last_updated_at` 必须在配置的最大陈旧时间内（默认 60 分钟）
- 超时的 projection 被视为不可靠，`ApiKeyRegistry` 会拒绝并抛 `RegistryUnavailable`
- 这是 fail-closed 设计：宁可拒绝服务，也不接受过期的权限数据

### 6.4 State 校验与 fail-closed

`ApiKeyRegistry.resolve()` 在返回注册信息前必须同时满足：

1. `state = 'active'` — `disabled`/`revoked`/`expired` 一律拒绝
2. `expires_at IS NULL OR expires_at > NOW()` — 过期拒绝
3. `last_updated_at` 在 TTL 窗口内 — 超时拒绝

任一条件不满足 → `Unauthenticated` 或 `RegistryUnavailable`，不会降级到默认配置。

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
- `access.rate_limit_checked`
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
- `debug_ref`

## 9. 配置

当前主配置在 [src/main/resources/application.yaml](./src/main/resources/application.yaml)。

关键项：

- `server.port=18081`
- `spring.datasource.*`
- `access.default-retrieval-profile-id`
- `access.retrieval.base-url`
- `access.retrieval.connect-timeout`
- `access.retrieval.read-timeout`

## 10. 当前实现边界

文档必须和代码现状一致，当前边界如下：

- 已经是 DB-backed `api_key_projection`（通过 `/internal/api-key-projections/sync` 消费 admin 投影）
- 已经有 fail-closed 的 state / expires_at / TTL 校验
- 已经有真实 MCP session 绑定
- 已经把审计写入 DB
- 检索 profile 已走 retrieval 端真实投影校验，不再本地 fallback
- 还没有真正的限流实现
- 认证方式：`X-API-Key` + `X-Agent-Instance-Id` header，查 `api_key_projection` 表验权 — 不做 end-user JWT（JWT 认证在 admin/workbench-api 层，access 作为 Agent-facing gateway 使用 API key）
- 还没有在 access 本地做 key 生命周期操作（仍由 admin 控制）

