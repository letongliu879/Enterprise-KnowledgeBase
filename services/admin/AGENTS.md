# admin — 平台管理控制面

## 定位

admin 是 Enterprise KnowledgeBase 平台的管理后台，admin-console 前端**唯一的后端入口**。负责全局配置（collection、profile、api key）、运维操作（archive/retract/reindex）、身份认证与审计。

**不做的事**：
- 文档上传、分块预览、审批决策 → `workbench-api`
- 检索查询 → `services/access`
- 解析与索引构建 → `services/indexing`
- 审批 ticket 创建与流转 → `approval-service`
- 文档发布流水线 → `intake-pipeline` / `publishing-worker`

## 边界原则

- admin **不直接操作**任何下游 owner 的表、Redis、或运行时数据
- 所有跨服务操作通过 `downstream_clients/` 中的 client gate 代理，返回统一错误码
- ParserProfile / RetrievalProfile 的控制面 owner 是 admin，运行时 owner 分别是 indexing/retrieval
- 发布 profile 前必须先调下游 validate 接口（`validate-before-publish`）
- 发布后的 profile **不可变**（只能新版本，旧版本 retired）
- Collection 绑定必须版本化，历史任务可回放到当时生效的绑定
- 所有控制操作三步走：鉴权 → 审计 → 执行

## 核心数据流

```
身份认证:
POST /admin/auth/login -> IdentityService.login -> verify pbkdf2_sha256 -> sign HS256 JWT -> create admin_sessions

Collection 管理:
POST /admin/collections -> CollectionCatalogService.create_collection -> write collections table
POST /admin/collections/{id}/bindings -> CollectionCatalogService.create_binding -> close old binding -> create new binding (versioned)

Parser Profile 发布:
POST /admin/parser-profiles/{id}/publish
  -> IndexingClient.validate_parser_profile (POST /internal/parser-profiles/validate)
  -> 失败 -> 写 ops_audit_log (after_state=rejected) -> 409
  -> 成功 -> 写 runtime_canonical_config / profile_hash -> state=published -> 写 ops_audit_log

Retrieval Profile 发布:
POST /admin/retrieval-profiles/{id}/publish
  -> RetrievalClient.validate_retrieval_profile (POST /internal/retrieval-profiles/validate)
  -> 失败 -> 写 ops_audit_log (after_state=rejected) -> 409
  -> 成功 -> state=published -> RetrievalClient.sync_retrieval_profile_projection (fail-open) -> 写 ops_audit_log

API Key 生命周期:
POST /admin/api-keys -> 生成 rrag_ 前缀随机 key -> 存 SHA-256 hash -> 返回 plaintext (仅一次)
POST /admin/api-keys/{id}/rotate -> 新 key -> 新 hash -> 写 last_rotated_at
POST /admin/api-keys/{id}/disable -> state=disabled
POST /admin/api-keys/{id}/revoke -> state=revoked
TODO: 生命周期变更时调 AccessClient.sync_api_key_projection

文档运维操作:
POST /admin/documents/{final_doc_id}/archive   -> PublishingWorkerClient.archive_document -> 写 ops_audit_log
POST /admin/documents/{final_doc_id}/retract   -> PublishingWorkerClient.retract_document -> 写 ops_audit_log
POST /admin/documents/{final_doc_id}/reindex   -> IndexingClient.get_parse_snapshot -> IndexingClient.submit_index_job -> 写 ops_audit_log
```

## 关键数据模型

### Profile 状态机
`draft -> published -> retired`
`draft -> retired`

### Collection 生命周期
`active -> archived`
`active -> inactive`

### API Key 状态
`active -> disabled`
`active -> revoked`

### Profile 版本不可变性
- published profile 不能 PATCH（返回 409）
- 再次 publish 自动创建 `{id}_v{version+1}`，旧版本标记 retired

## 约束与规则

### 权限
- `knowledge_admin` 或 `platform_admin` 角色才能执行所有写操作
- 只读查询（GET collections, api-keys, profiles, audit-log）通过 `require_auth` 即可
- `AUTH_MODE=production` 时必须配置 `ADMIN_JWT_ISSUER` + `ADMIN_JWT_AUDIENCE`

### 统一下游错误码
| 错误码 | HTTP | 触发条件 |
|--------|------|----------|
| `DOWNSTREAM_NOT_IMPLEMENTED` | 501 | 下游返回 404/501 |
| `DOWNSTREAM_UNAVAILABLE` | 503 | 连接失败 / 超时 |
| `CONFLICT` | 409 | 下游返回 409 / 校验失败 |
| `NOT_FOUND` | 404 | 下游返回 404 |
| `FORBIDDEN` | 403 | 角色不足 |
| `UNAUTHORIZED` | 401 | 无效/缺失 token |

### Canonical Wire（禁止旧字段名出现在对外 API）
| 概念 | Canonical | 禁止 |
|------|-----------|------|
| 检索查询文本 | `query` | `query_text` |
| token budget | `token_budget` | `max_context_tokens` |
| 检索结果 | `evidence_items` | `result_chunks` |
| 文档 ID | `doc_id` | `final_doc_id` |
| evidence ID | `evidence_id` | `chunk_id` |
| 展示内容 | `content` | `display_text` |

### 已知坑
1. `ApiKeyRegistryModel` 同时有 `max_context_tokens`（兼容旧 Java 服务）和 `token_budget_limit`（admin canonical wire），对外只暴露 `token_budget_limit`
2. `retrieval_clients.py` 数据库表名是 `retrieval_profiles_admin`，不是 `retrieval_profiles`（后者是 retrieval 运行时）
3. `AccessClient.sync_api_key_projection` 客户端代码已存在但**尚未在 API Key 生命周期路由中调用**
4. `IdentityService.logout` 的 session 失效逻辑尚未实现（`pass`）
5. log_action 中 `command_id`/`trace_id` 默认为随机值，生产环境应传入实际值
6. `profile_registry/routes.py` 中 publish 路由是 **async**（因为调下游 HTTP），但 transition 路由是 sync
7. 跨模块工作前先读 `services/admin/api.md` 和上下游模块的 api.md

## 待实现功能清单

| 功能 | 需要的下游 API | 状态 |
|------|---------------|------|
| Approval override | `approval-service POST /internal/tickets/{id}/override` | 待补齐 |
| Chunk 隐藏/显示 | `indexing PATCH /internal/chunks/{id}/visibility` | 待补齐 |
| Index 激活/回滚 | `indexing POST /internal/index-versions/{id}/activate` | 待补齐 |
| API Key projection sync | `access POST /internal/api-key-projections/sync` | client 就绪，未接入 |
| Cache purge | `retrieval POST /internal/cache/purge` | 待补齐 |
| GraphQL trace timeline | 各服务只读视图 | 待补齐 |
| Eval datasets & bad cases | admin 本地表 | 待补齐 |
| Alert rules | admin 本地表 | 待补齐 |
| Service health aggregation | 各服务 /health | 待补齐 |

## 测试策略

- 所有路由使用 `fastapi.testclient.TestClient` + 内存 SQLite
- 鉴权测试用 `test_auth.py` + `test_auth_jwt.py`（覆盖 issuer/audience/过期/错误secret）
- 下游 mock 用 `respx` (test_profiles, test_downstream_clients) 或 `monkeypatch` (test_document_ops)
- `test_audit.py` 验证审计日志条目存在性
- 角色测试：`admin_token`（platform_admin）/ `knowledge_admin_token` / `viewer_token`（无 mutation 权限）
