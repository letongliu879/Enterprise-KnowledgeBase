# MCP 服务面对外重构方案

这份文档记录 `services/access` 当前确认下来的正式方向。

## 1. 结论

当前正确方向不是：

- 客户端自己理解私有签名规则
- 客户端自己上报 tenant / platform
- 客户端自己拼权限上下文

而是：

- 服务端提供标准、低摩擦的 REST / MCP 服务面
- 客户端只提供最少身份输入
- 授权、访问域、collection 范围由服务端根据 `api_key` 查询

## 2. 正式客户端输入

当前客户端正式输入收敛为：

- `X-API-Key`
- `X-Agent-Instance-Id`

不再要求：

- `X-Tenant-Id`
- `X-Platform-Id`
- HMAC 签名
- nonce / timestamp
- `api_secret`

## 3. 服务端固定承担的职责

`access` 必须负责：

- 校验 `api_key` 是否存在、是否启用
- 解析 `agent_instance_id`
- 为 MCP session 绑定 `api_key + agent_instance_id`
- 根据 `api_key` 查询调用方身份
- 根据 `api_key` 查询可访问的 knowledge scope / collection scope
- 根据 `api_key` 查询 debug 权限和 token 上限
- 生成 `query_id` / `trace_id`
- 审计日志

## 4. 为什么这样更合理

因为你们的真实业务模型是：

- 多租户边界不是通用 `tenant_id`
- 平台隔离也不是核心抽象
- 真正的隔离和权限边界在 `api_key` 出厂绑定的信息里

所以内部模型应以：

- `api_key`
- `agent_instance_id`
- `knowledge_scopes`
- `collection_scope`

为主，而不是继续围绕 `tenant/platform` 设计。

## 5. 对 retrieval 的要求

`retrieval` 不再依赖客户端上报的 tenant/platform。

它只吃 `access` 传来的受控检索请求，其中关键的是：

- principal
- collection scope
- allowed doc ids
- metadata filters
- retrieval profile id

## 6. SDK 的定位

SDK 可以做，但定位应是：

- 推荐接入层
- 标准 headers / SSE / tools/list / tools/call 的便捷封装
- 错误处理和日志封装

SDK 不是：

- HMAC 补丁
- tenant/platform 透传层
- 私有协议解释器

## 7. 一句话

最终模型是“`api_key` 定义调用方身份和访问边界，`agent_instance_id` 只定义实例态”，而不是“客户端上传 tenant/platform 后由服务端被动相信”。
