# Agent Platform MCP 接入手册

这份文档给接入 `services/access` MCP server 的平台团队和 agent 团队使用。

## 1. 当前支持的 MCP transport

当前 `access` 暴露的是官方 Spring AI WebMVC SSE transport：

- `GET /sse`
- `POST /mcp/messages?sessionId=...`

这意味着：

- 支持 SSE 的 Python / Node / Java MCP client 都可以接
- 只支持 `streamable-http`、不支持 `sse` 的 client 目前不能直接接

## 2. 身份模型

`access` 的 MCP 面向企业内部平台和平台内 agent 服务，不面向终端用户。

身份模型只有两层半：

- `api_key`
  - 代表一个登记好的调用方接入
  - 在服务端绑定“是谁”和“能调用什么”
- `agent_instance_id`
  - 代表同一个接入方下某个运行实例
  - 只用于 session 绑定、审计和追踪
- `sessionId`
  - 代表一次 MCP 会话

必须明确：

- 一个 `api_key` 不是一个 agent
- 一个 `api_key` 下可以同时有很多 `agent_instance_id`
- 权限不是客户端自报的，而是服务端查 `api_key` 后得到的

## 3. 客户端要带什么

现在客户端只需要带：

- `X-API-Key`
- `X-Agent-Instance-Id`

不再需要：

- `X-Tenant-Id`
- `X-Platform-Id`
- `X-Reality-Timestamp`
- `X-Reality-Nonce`
- `X-Reality-Signature`
- `api_secret`

## 4. 服务端怎么做授权

`access` 收到请求后，会根据 `api_key` 查询服务端登记信息，至少得到：

- 调用方身份
- agent type
- 允许访问的 `knowledge_scopes`
- 允许访问的 collection 范围
- debug 权限
- max context tokens

然后由 `access` 把这些受控信息传给 `retrieval`。

所以：

- 客户端不决定 tenant/platform
- 客户端不决定真实权限域
- 客户端不决定可访问 collection

## 5. MCP tool 使用边界

MCP tool 是受治理的 tool，不是泛用数据库查询口。

推荐规则：

- 只有在需要查询企业内部知识、制度、流程、运行手册时才调用
- 不应用于闲聊、公网常识、纯推理、代码生成
- 不应让模型自由指定任意内部 collection
- 平台 runtime 应先做本地 gating
- `access` 服务端再做二次校验

## 6. 最小接入步骤

1. 确认客户端支持 `sse`
2. MCP URL 配成 `http://<access-host>:<access-port>/sse`
3. 配置 `X-API-Key`
4. 在运行时生成或注入稳定的 `X-Agent-Instance-Id`
5. 先验证 `tools/list`
6. 再验证 `tools/call`

### 6.1 真实联调约束

当前已经用官方 Java MCP client 做过真实联调，确认这条链路可跑通。

`tools/call` 的 arguments 目前按这些顶层字段名传：

- `query`
- `knowledge_scope`
- `retrieval_profile_id`
- `max_context_tokens`
- `debug`

## 7. 一句话

现在的正式接入口径是：客户端只提供 `api_key + agent_instance_id`，权限、访问域和 collection 范围都由服务端根据 `api_key` 查表决定。
