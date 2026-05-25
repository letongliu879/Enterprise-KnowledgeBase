# Access

`services/access` 是 `Enterprise KnowledgeBase` 的 Java Spring Boot 在线入口服务。

它负责：

- 对外 REST 入口
- 对外 MCP 入口
- 识别 `X-API-Key` 和 `X-Agent-Instance-Id`
- 根据 `api_key` 查询服务端登记的调用方身份、权限、知识域和 collection 访问范围
- 把外部请求翻译成内部 retrieval 请求
- 调用 `services/retrieval`
- 记录 `query_id` / `trace_id` / `api_key_id` / `agent_instance_id` 审计日志

它不负责：

- 检索算法
- OpenSearch / Qdrant 直接访问
- `KnowledgeContext` 内部组装
- 文档治理、发布、索引写入
- 让客户端自己传 tenant / platform / 签名信息

当前服务面：

- REST：`POST /v1/retrieve`
- Health：`GET /health`
- MCP SSE：`GET /sse`
- MCP messages：`POST /mcp/messages?sessionId=...`

当前认证模型：

- 客户端只需要：`X-API-Key`、`X-Agent-Instance-Id`
- `api_key` 在服务端数据库或注册表中绑定：
  - 调用方是谁
  - 能调用哪些能力
  - 能访问哪些 `knowledge_scopes` / `collection_scope`
  - debug 权限
  - max context tokens
- 不再使用：
  - `X-Tenant-Id`
  - `X-Platform-Id`
  - `X-Reality-Timestamp`
  - `X-Reality-Nonce`
  - `X-Reality-Signature`
  - `api_secret`

相关文档：

- [../../docs/architecture.md](../../docs/architecture.md)
- [../../docs/project-overview.md](../../docs/project-overview.md)
- [../retrieval/retrieval.md](../retrieval/retrieval.md)
- [./access.md](./access.md)
- [./agent-platform-mcp-integration.md](./agent-platform-mcp-integration.md)
- [./mcp-service-surface-refactor.md](./mcp-service-surface-refactor.md)
- [../../contracts/openapi/access.yaml](../../contracts/openapi/access.yaml)
- [../../contracts/openapi/retrieval-internal.yaml](../../contracts/openapi/retrieval-internal.yaml)
