# access

`services/access` 是当前知识库的在线入口服务，基于 Spring Boot。

详细设计见 [access.md](./access.md)。

## 核心职责

- 对外 REST 入口
- 对外 MCP SSE 入口
- 读取 `X-API-Key` 与 `X-Agent-Instance-Id`
- 从 `api_key_projection` 缓存表解析调用方身份和可访问 scope（通过 `/internal/api-key-projections/sync` 消费 admin 投影）
- 把外部请求翻译成内部 retrieval 请求
- 调用 `services/retrieval`
- 把 `query_id` / `trace_id` / 调用信息写入 `run_traces`、`run_steps`

以下职责**不属于** access：

- 检索算法
- OpenSearch / Qdrant 直接访问
- 文档发布、索引写入、生命周期治理
- 让客户端自己上传 tenant / platform / HMAC 签名

## 当前服务面

对外：

- `GET /health`
- `POST /v1/retrieve`
- `GET /sse`
- `POST /mcp/messages?sessionId=...`

内部（admin → access projection sync）：

- `POST /internal/api-key-projections/sync`

## 当前客户端输入

- Header: `X-API-Key`
- Header: `X-Agent-Instance-Id`

access 根据 `X-API-Key` 查 `api_key_projection` 缓存表，校验 `state`、`expires_at`、`last_updated_at` TTL，fail-closed。

## REST 与 MCP

REST 请求体当前使用：

- `query`
- `collection_scope`
- `retrieval_profile_id`
- `token_budget`
- `debug`

MCP 当前只暴露一个 tool：

- `search_enterprise_knowledge`

tool 参数当前使用：

- `query`
- `knowledge_scope`
- `retrieval_profile_id`
- `token_budget`
- `debug`

## 运行时依赖

- 默认端口：`18081`
- 下游 retrieval 默认地址：`http://127.0.0.1:18082`
- 数据库连接来自 `spring.datasource.*`
- `api_key_projection`、`api_key_projection_idempotency`、`run_traces`、`run_steps` 在 access 本地数据库
- admin 通过 `/internal/api-key-projections/sync` 推送投影，access 不做 admin 表直连
- `retrieval_profile_id` 由 access 转发至 retrieval 校验，access 不本地缓存 profile
