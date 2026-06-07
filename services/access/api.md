# access 对外接口契约

## Inbound（access 接收的请求）

### 对外 REST

#### `POST /v1/retrieve` — 检索入口
`ExternalRetrieveRequest`:
```
query              : string       (必填)
collection_scope   : string[]     (必填, 必须是 api_key 允许范围的子集)
filters            : object       (可选)
language           : string       (可选)
cross_languages    : string[]     (可选)
keyword            : boolean      (可选)
meta_data_filter   : object       (可选)
retrieval_profile_id : string     (可选, 正式字段)
profile            : string       (可选, 兼容别名, 与 retrieval_profile_id 冲突时报错)
token_budget       : integer      (可选, wire 名 token_budget)
debug              : string       (可选, none|basic|full)
```
返回 `KnowledgeContext`

#### `GET /health` — 健康检查
返回 `AccessHealthResponse`:
```
service          : "access"
status           : "ok" | "degraded"
retrieval_status : "ok" | "unavailable" | "unknown"
```

#### `GET /actuator/health` — Spring Boot Actuator 健康检查
#### `GET /actuator/info` — Spring Boot Actuator 信息
（以上不经过认证过滤器）

### 对外 MCP

#### `POST /mcp` — MCP Streamable HTTP 端点
Spring AI MCP Server, protocol `STREAMABLE`, transport `Streamable HTTP`

当前暴露一个 tool:
- **`search_enterprise_knowledge`**
  - `query` (string, 必填) — 用户问题
  - `knowledge_scope` (string, 可选) — 知识库 scope/collection id；不传则搜所有授权 scope
  - `token_budget` (integer, 可选)
  - `debug` (string, 可选, none|basic|full)

> `knowledge_scope` 省略时自动搜索 API Key 有权访问的全部 scope。`retrieval_profile_id` 对 Agent 透明，走服务端默认 profile。

MCP 请求通过 `X-API-Key` + `X-Agent-Instance-Id` header 认证，Streamable HTTP 使用 `Mcp-Session-Id` header 维护会话状态。

### 内部（admin → access）

#### `POST /internal/api-key-projections/sync` — 推送 API Key 投影
`ApiKeyProjectionSyncRequest`:
```
command_id       : string    (必填)
trace_id         : string    (必填)
idempotency_key  : string    (必填)
actor            : string    (必填)
tenant_id        : string    (必填)
target_type      : string    (必填, = "api_key_projection")
target_id        : string    (必填, = api_key_id)
payload          : ApiKeyProjection
```
`ApiKeyProjection`:
```
api_key_id         : string
tenant_id          : string
agent_type_id      : string
knowledge_scopes   : string[]
roles              : string[]
debug_permission   : boolean
token_budget_limit : integer
state              : string (active|disabled|revoked|expired)
expires_at         : instant (nullable)
projection_version : integer
last_updated_at    : instant
```
返回 `ApiKeyProjectionSyncResponse`:
```
synced_at       : instant
runtime_synced  : boolean
```
幂等（`idempotency_key`），重复投递不会重复写入。

## Inbound 认证与安全

| 端点 | 认证要求 | 说明 |
|------|---------|------|
| `POST /v1/retrieve` | `X-API-Key` + `X-Agent-Instance-Id` | 查 api_key_projection 表 |
| `POST /mcp` | `X-API-Key` + `X-Agent-Instance-Id` | 查 api_key_projection 表 |
| `GET /health` | 无 | 不经过 filter |
| `GET /actuator/*` | 无 | 不经过 filter |
| `POST /internal/*` | 无需 header | 需 127.0.0.1/localhost IP 白名单 |

## Outbound（access 发出的请求）

| 方向 | 端点 | 说明 |
|------|------|------|
| -> retrieval | `POST /internal/retrieve` | 受控检索请求 |
| -> retrieval | `GET /health` | 健康检查 |
| -> retrieval | `GET /internal/retrieval-profiles/{profileId}` | 校验 retrieval profile 存在性 |

### `POST /internal/retrieve` 请求体
`InternalRetrieveRequest`:
```
query_id              : string
trace_id              : string
principal             : InternalPrincipal
  user_id               : string (= agentTypeId:agentInstanceId)
  role_ids              : string[] (= roles)
  group_ids             : string[] (= knowledgeScopes)
  attributes            : object
collection_scope      : string[]
query                 : string (wire 名 query)
language              : string (可选)
cross_languages       : string[] (可选)
keyword               : boolean (可选, 默认 false)
meta_data_filter      : object (可选)
retrieval_profile_id  : string
filters               : object (可选)
include_deprecated    : boolean (硬编码 false)
token_budget          : integer (wire 名 token_budget)
debug_level           : string (none|basic|full)
```
Header: `X-Trace-Id`, `X-Query-Id`

### `POST /internal/retrieve` 响应体
`KnowledgeContext`:
```
query_id                 : string
principal_context        : object
index_version_used       : string[]
collection_plans_used    : object[]
evidence_items           : ResultChunk[] (wire 名 evidence_items)
  collection_id            : string
  doc_id                   : string (wire 名 doc_id)
  evidence_id              : string (wire 名 evidence_id)
  document_index_revision_id : string
  content                  : string (wire 名 content)
  section_path             : string[]
  page_spans               : {page_from, page_to}[]
  score                    : double
  source_stage             : string
  why_selected             : string
grouped_sources          : object[]
citations                : object[]
token_budget_used        : int
retrieval_debug          : object
```

## 关键数据模型

### `ApiKeyProjection`（DB 表 `api_key_projection`）
| 字段 | 类型 | 说明 |
|------|------|------|
| `api_key_id` | VARCHAR(128) PK | API Key ID |
| `tenant_id` | VARCHAR(64) NOT NULL | 所属租户 |
| `agent_type_id` | VARCHAR(128) NOT NULL | agent 类型 |
| `knowledge_scopes` | JSON string[] | 允许查询的 collection 列表 |
| `roles` | JSON string[] | 角色列表 |
| `debug_permission` | BOOLEAN | 是否有 debug 权限 |
| `token_budget_limit` | INTEGER | token 预算上限 |
| `state` | VARCHAR(32) | active / disabled / revoked / expired |
| `expires_at` | TIMESTAMP (nullable) | 过期时间 |
| `projection_version` | INTEGER | 版本号 |
| `last_updated_at` | TIMESTAMP | admin 侧最后更新时间 |
| `synced_at` | TIMESTAMP | 写入 access 时间 |
| `runtime_synced` | BOOLEAN | 是否已同步 |

### 审计表 `run_traces`
`run_trace_id` = `access_<queryId>`, `run_kind` = `access`

### 审计表 `run_steps`
记录了 `access.request_accepted` / `access.retrieval_call` / `access.response` / `access.failure`

### Error Code
| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `ACC_UNAUTHENTICATED` | 401 | API key 未知/非 active/已过期 |
| `ACC_FORBIDDEN` | 403 | scope 越权 / debug 无权限 / MCP session drift |
| `ACC_INVALID_REQUEST` | 400 | 参数校验失败 / retrieval_profile 冲突 / debug 值非法 / profile 不存在 |
| `ACC_API_KEY_REGISTRY_UNAVAILABLE` | 500 | 投影数据查询失败 / TTL 超时 |
| `ACC_RETRIEVAL_TIMEOUT` | 504 | retrieval 超时 |
| `ACC_RETRIEVAL_UNAVAILABLE` | 503 | retrieval 不可达 / 返回错误 |
| `ACC_INTERNAL_ERROR` | 500 | 未预期的内部错误 |

## 配置环境变量及默认值
| 配置 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| `access.default-retrieval-profile-id` | — | `ret_default` | 默认检索 profile |
| `access.retrieval.base-url` | — | `http://127.0.0.1:18082` | retrieval 服务地址 |
| `access.retrieval.connect-timeout` | — | `1s` | 连接超时 |
| `access.retrieval.read-timeout` | — | `3s` | 读取超时 |
| `server.port` | — | `18081` | 服务端口 |
| `spring.datasource.*` | `DATABASE_URL`/`DATABASE_USERNAME`/`DATABASE_PASSWORD`/`DATABASE_DRIVER` | PostgreSQL `127.0.0.1:5432/reality_rag` | 数据库 |

## Wire Format 约定

access 与 retrieval 之间的 wire format 使用 canonical snake_case 字段名：
- `query`（不是 `query_text`）
- `token_budget`（不是 `max_context_tokens`）
- `evidence_items`（不是 `result_chunks`）
- `doc_id`（不是 `final_doc_id`）
- `evidence_id`（不是 `chunk_id`）
- `content`（不是 `display_text`）
