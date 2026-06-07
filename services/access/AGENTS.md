# access — 知识库对外入口服务

## 定位
access 是知识库的在线接入网关，不是检索内核。

**只做四件事**：
1. 接住外部 REST / MCP 请求
2. 根据 `X-API-Key` 查 `api_key_projection` 缓存表，解析调用方身份和可访问 scope
3. 把外部请求翻译成受控的内部 retrieval 请求
4. 记录可追溯的访问审计（`run_traces`、`run_steps`）

**不做的事**：检索排序/召回/扩展/上下文打包、OpenSearch/Qdrant 直连、文档发布/索引写入/生命周期治理、API Key 生命周期管理、限流。

## 边界原则
- `services/retrieval` 负责检索算法和上下文打包，access 只做翻译和转发
- access 不是 API Key 的事实源；admin 才是。access 只消费 admin 同步过来的 `api_key_projection`，并做 TTL 校验
- 客户端不再上传 tenant / platform / HMAC 签名——这些来自服务端投影
- `collection_scope` 必须是 `knowledge_scopes` 的子集，否则抛 `ACC_FORBIDDEN`
- 认证 fail-closed：`state != active` / 已过期 / 投影超时 → 拒绝，不降级
- `/internal/*` 只允许 127.0.0.1 / localhost 访问
- `/health` 和 `/actuator/*` 不经过认证过滤器
- MCP session principal drift 检测：同一 `Mcp-Session-Id` 换了 `api_key_id`/`agent_type_id`/`agent_instance_id`/`knowledge_scopes` → 403
- cache purge fail-open 类比：access 侧不做 fail-open，所有校验都是 fail-closed

## 核心数据流
```
外部请求 -> AccessRequestContextFilter (认证)
  -> AccessAuthenticator (读 X-API-Key + X-Agent-Instance-Id)
  -> ApiKeyRegistry (查 api_key_projection 表 + state/expiresAt/TTL 校验)
  -> AccessGatewayService (生成 query_id / trace_id)
    -> DebugPolicy (debug 权限判断)
    -> RetrievalProfileSelector (选择/校验 retrieval_profile_id)
    -> RetrieveRequestBuilder (校验 collection_scope 子集)
    -> LoggingAccessTraceRecorder (access.retrieval_call)
    -> RetrievalClient (POST /internal/retrieve)
    -> LoggingAccessTraceRecorder (access.response / access.failure)
  -> 返回 KnowledgeContext
```

## 关键对象
- `AccessRequestContext`：一次认证通过的请求上下文，包含 `apiKeyId` / `tenantId` / `agentTypeId` / `agentInstanceId` / `knowledgeScopes` / `roles` / `debugPermission` / `clientType` / `maxContextTokens`
- `ApiKeyProjection`：admin 同步过来的 API Key 运行时投影，含 `state` / `expiresAt` / `projectionVersion` / `lastUpdatedAt`
- `ApiKeyRegistry.AgentRegistration`：`resolve()` 返回的注册信息（从 DB 投影反序列化）
- `ExternalRetrieveRequest`：外部 REST 请求体
- `InternalRetrieveRequest`：发给 retrieval 的内部请求体（含 `principal` / `traceId` / `queryId`）
- `KnowledgeContext`：retrieval 返回的检索结果

## 安全校验逻辑（按顺序）
```
1. state == "active"? 否则 UNAUTHENTICATED (401)
2. expiresAt == null OR expiresAt > now? 否则 UNAUTHENTICATED (401)
3. MAX_PROJECTION_STALENESS_MINUTES > 0 时 lastUpdatedAt 在 TTL 内? 否则 RegistryUnavailable (500)
   （当前生产代码 MAX_PROJECTION_STALENESS_MINUTES = 0，即不检查）
4. collection_scope ⊆ knowledgeScopes? 否则 FORBIDDEN (403)
```

## Debug 权限逻辑
- `none` → 直接放行
- `basic` → `debugPermission=true` 放行，否则降级为 `none`
- `full` → `debugPermission=true` 放行，否则抛 `ACC_FORBIDDEN`

## Retrieval Profile 选择逻辑（优先级）
```
1. retrieval_profile_id (显式指定)
2. profile (兼容别名，与 1 冲突时报错)
3. access.default-retrieval-profile-id 配置项 (默认 ret_default)
选定后调用 retrieval GET /internal/retrieval-profiles/{id} 确认存在
```

## 约束
- `profile` 仍是兼容别名，但正式字段是 `retrieval_profile_id`；两者同时存在且不一致时抛 `ACC_INVALID_REQUEST`
- MCP tool 当前一次只查一个 `knowledge_scope`，`McpKnowledgeScopeMapper` 转成单元素 `collection_scope`
- RestClient 超时：connect=1s, read=3s（配置项 `access.retrieval.*`）
- Wire format 使用 snake_case，`query_text` → `query`，`max_context_tokens` → `token_budget`
- `KnowledgeContext.ResultChunk` wire 名：`evidence_items`/`doc_id`/`evidence_id`/`content`
- 数据库表通过 `@PostConstruct` DDL 自动创建，无需手动建表
- MCP protocol version = `2024-11-05`（客户端发更高版本时会回退建议到此版本）
- `run_traces.run_trace_id` 格式：`access_<queryId>`
- 配置前缀 `access.*`，统一入口 `AccessProperties`（`access.default-retrieval-profile-id`、`access.retrieval.*`）
- 还没有限流实现、没有 `/sse` 端点（`AccessAuthenticator` 中预留了 clientType 判断）
- `MAX_PROJECTION_STALENESS_MINUTES` 当前硬编码为 0（开发模式不校验 TTL），上线前需改为 60
