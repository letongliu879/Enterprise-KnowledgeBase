# access 在线入口设计

## 1. 定位

`access` 是 `Enterprise KnowledgeBase` 的 Java/Spring Boot 在线入口，负责把外部 REST / MCP 请求安全、稳定、可观测地翻译成内部 retrieval 请求。

它负责：

- REST API
- MCP SSE API
- `X-API-Key` / `X-Agent-Instance-Id` 认证入口
- 按 `api_key` 查询调用方身份、权限和知识域
- request validation
- query_id / trace_id
- 调用 `services/retrieval`
- 审计日志

它不负责：

- 检索算法
- OpenSearch / Qdrant 直接访问
- 文档治理和索引写入
- 让客户端传 tenant / platform / secret / signature

## 2. 当前最终模型

这部分不是过渡想法，而是当前已经明确的目标模型。

### 2.1 权限边界以 `api_key` 为中心

`api_key` 在创建时由服务端登记，并绑定：

- 调用方是谁
- agent type
- 能调用哪些能力
- 能访问哪些 `knowledge_scopes` / `collection_scope`
- debug 权限
- max context tokens

### 2.2 `agent_instance_id` 只表示实例态

`agent_instance_id` 不是权限来源。

它只用于：

- MCP session 绑定
- 审计日志
- trace
- 区分同一个 `api_key` 下的多个运行实例

### 2.3 不再采用 tenant/platform 模型

当前项目不再把这些作为正式服务面的一部分：

- `tenant_id`
- `platform_id`
- `X-Tenant-Id`
- `X-Platform-Id`

权限和访问域不靠客户端传这类字段，而靠服务端查 `api_key` 绑定信息。

### 2.4 不再采用 HMAC 客户端签名模型

当前项目不再要求客户端提供：

- `api_secret`
- `X-Reality-Timestamp`
- `X-Reality-Nonce`
- `X-Reality-Signature`

## 3. 对外服务面

### 3.1 REST

- `POST /v1/retrieve`
- `GET /health`

### 3.2 MCP

- `GET /sse`
- `POST /mcp/messages?sessionId=...`

当前已用官方 Java MCP client 做过真实调用验证：

- `initialize`
- `listTools`
- `callTool`
- session principal drift 拒绝

REST 与 MCP 共用同一套：

- 认证逻辑
- request translation
- retrieval client
- query_id / trace_id
- 审计日志

## 4. 认证与授权

客户端正式输入只保留：

- `X-API-Key`
- `X-Agent-Instance-Id`

`access` 收到请求后：

1. 校验 `api_key`
2. 查询服务端登记信息
3. 组装 `AccessRequestContext`
4. 校验会话绑定
5. 生成内部 retrieval 请求
6. 把受控的 scope / policy 传给 `retrieval`

当前 `search_enterprise_knowledge` tool 的 arguments 顶层字段名为：

- `query`
- `knowledge_scope`
- `retrieval_profile_id`
- `max_context_tokens`
- `debug`

## 5. retrieval 边界

`retrieval` 现在吃的是受控内部请求，而不是客户端自报的 tenant/platform。

`access` 传给 `retrieval` 的核心是：

- principal
- collection scope
- filters
- retrieval profile id
- max context tokens
- debug level

## 6. 审计

必须可按 `query_id` / `trace_id` 反查：

- `api_key_id`
- `agent_type_id`
- `agent_instance_id`
- client type
- collection scope
- retrieval profile id

## 7. 一句话

`access` 的正式模型已经收敛成“客户端只给 `api_key + agent_instance_id`，服务端根据 `api_key` 决定身份、权限和访问域”。
