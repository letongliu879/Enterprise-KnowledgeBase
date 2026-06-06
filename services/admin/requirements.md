# services/admin 功能需求规格 (REQ)

**版本**: 1.0.0
**生效日期**: 2026-06-06
**范围**: 仅包含当前代码中已实现并经过测试验证的功能

---

## 1. 定位

`services/admin` 是 Enterprise KnowledgeBase 平台的管理控制面，面向平台管理员与运维人员。当前实现覆盖：

- 管理员身份认证（JWT 签发与校验）
- Collection 目录与版本化绑定管理
- Parser Profile / Retrieval Profile 的全生命周期管理
- API Key 注册与生命周期管理
- 操作审计日志查询
- 已发布文档的归档、撤回、重新索引

---

## 2. 认证与鉴权

### ADM-001 管理员登录

**路由**: `POST /admin/auth/login`
**源码**: `services/admin/src/admin_service/identity/routes.py:19`

**验收标准**:
1. 使用邮箱与密码登录，密码采用 `pbkdf2_sha256` 哈希校验。
2. 校验通过后签发 HS256 JWT，payload 包含 `sub`（用户ID）、`email`、`roles`、`tenant_id`、`allowed_collections`。
3. 同时创建 `admin_sessions` 记录并写入 token 哈希。
4. 密码错误或用户不存在时返回 `401 Unauthorized`。

---

### ADM-002 当前用户信息

**路由**: `GET /admin/auth/me`
**源码**: `services/admin/src/admin_service/identity/routes.py:37`

**验收标准**:
1. 从 JWT `sub`  claim 定位用户，返回 `user_id`、`email`、`display_name`、`roles`、`tenant_id`、`allowed_tenants`、`allowed_collections`。
2. 缺少或无效的 token 返回 `401 Unauthorized`。

---

### ADM-003 登出

**路由**: `POST /admin/auth/logout`
**源码**: `services/admin/src/admin_service/identity/routes.py:27`

**验收标准**:
1. 接收 Authorization header 中的 Bearer token 并返回 `{"message": "Logged out"}`。
2. 该端点已接入路由，会话失效的完整实现待后续补充。

---

### ADM-004 JWT 校验依赖

**源码**: `services/admin/src/admin_service/deps.py:45`

**验收标准**:
1. 从 `Authorization: Bearer <token>` 解析 JWT。
2. 支持通过环境变量配置 `ADMIN_JWT_SECRET`、`ADMIN_JWT_ISSUER`、`ADMIN_JWT_AUDIENCE`。
3. 过期、错误 secret、错误 issuer/audience 均返回 `401 Unauthorized`。
4. `AUTH_MODE=smoke` 使用默认 secret；`AUTH_MODE=production` 必须显式配置 issuer/audience。

---

### ADM-005 角色检查

**源码**: `services/admin/src/admin_service/deps.py:68`

**验收标准**:
1. 提供 `require_role(role)` 依赖工厂，token 中无指定角色时返回 `403 Forbidden`。
2. 当前使用角色名列表（`knowledge_admin`、`platform_admin`）进行粗粒度校验。

---

## 3. Collection 目录

### ADM-006 Collection 列表

**路由**: `GET /admin/collections`
**源码**: `services/admin/src/admin_service/collection_catalog/routes.py:35`

**验收标准**:
1. 返回 `items` 数组与 `total` 计数。
2. 支持 `tenant_id` 查询参数过滤。
3. 调用 `can_access_tenant` 进行租户权限检查（当前实现返回 `True`，钩子已就位）。

---

### ADM-007 创建 Collection

**路由**: `POST /admin/collections`
**源码**: `services/admin/src/admin_service/collection_catalog/routes.py:47`

**验收标准**:
1. 需要 `knowledge_admin` 或 `platform_admin` 角色，否则返回 `403`。
2. 创建时校验 `tenant_id` 在 `tenants` 表中存在。
3. 初始 `lifecycle_state` 为 `active`。
4. 返回 `200 OK` 与完整 collection 对象。

---

### ADM-008 查看 Collection

**路由**: `GET /admin/collections/{collection_id}`
**源码**: `services/admin/src/admin_service/collection_catalog/routes.py:56`

**验收标准**:
1. 按 `collection_id` 返回详情。
2. 不存在时返回 `404 Not Found`。

---

### ADM-009 更新 Collection

**路由**: `PATCH /admin/collections/{collection_id}`
**源码**: `services/admin/src/admin_service/collection_catalog/routes.py:67`

**验收标准**:
1. 支持部分字段更新：`name`、`description`、`authority_level`、`access_policy`、默认 profile ID。
2. 需要 admin 角色。
3. 返回更新后的 collection。

---

### ADM-010 Collection 生命周期切换

**路由**: `POST /admin/collections/{collection_id}/lifecycle`
**源码**: `services/admin/src/admin_service/collection_catalog/routes.py:80`

**验收标准**:
1. 修改 `lifecycle_state`，支持传入 `reason`。
2. 需要 admin 角色。
3. 返回新的 `lifecycle_state`。

---

### ADM-011 查看 Collection 绑定历史

**路由**: `GET /admin/collections/{collection_id}/bindings`
**源码**: `services/admin/src/admin_service/collection_catalog/routes.py:93`

**验收标准**:
1. 返回该 collection 下所有 `collection_profile_bindings` 记录，按创建时间倒序。

---

### ADM-012 查看当前绑定

**路由**: `GET /admin/collections/{collection_id}/bindings/current`
**源码**: `services/admin/src/admin_service/collection_catalog/routes.py:101`

**验收标准**:
1. 返回最新未关闭的 binding。
2. 无绑定记录时返回 `404`。

---

### ADM-013 创建版本化绑定

**路由**: `POST /admin/collections/{collection_id}/bindings`
**源码**: `services/admin/src/admin_service/collection_catalog/routes.py:112`

**验收标准**:
1. 绑定包含 `parser_profile_id` 与 `retrieval_profile_id`。
2. 首次创建时 `binding_version = 1`。
3. 再次创建时自动递增版本号，关闭旧 binding，并记录 `previous_binding_id`。
4. 基于绑定配置计算 SHA-256 `config_hash`。

---

## 4. Parser Profile 注册表

### ADM-014 列表 Parser Profiles

**路由**: `GET /admin/parser-profiles`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:47`

**验收标准**:
1. 返回 parser profile 列表与 `total`。
2. 支持 `state` 查询参数过滤。

---

### ADM-015 创建 Parser Profile

**路由**: `POST /admin/parser-profiles`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:56`

**验收标准**:
1. 接收 `parser_id`、`parser_config`、`name` 等字段。
2. 初始状态为 `draft`，版本为 `1`。
3. 需要 admin 角色。

---

### ADM-016 查看 Parser Profile

**路由**: `GET /admin/parser-profiles/{parser_profile_id}`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:65`

**验收标准**:
1. 按 ID 返回 profile 详情。
2. 不存在时返回 `404`。

---

### ADM-017 更新 Parser Profile

**路由**: `PATCH /admin/parser-profiles/{parser_profile_id}`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:76`

**验收标准**:
1. 仅允许更新 `draft` 状态的 profile。
2. 对已 `published` 的 profile 调用 `PATCH` 返回 `409 Conflict`。

---

### ADM-018 发布 Parser Profile

**路由**: `POST /admin/parser-profiles/{parser_profile_id}/publish`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:92`

**验收标准**:
1. 发布前调用 `indexing` 下游接口 `POST /internal/parser-profiles/validate` 校验配置。
2. 校验失败或下游不可用时，写入 `ops_audit_log`（`after_state=rejected`）并返回 `409`。
3. 校验成功后存储 `profile_hash`、`validator_version`、`runtime_canonical_config`，状态变为 `published`。
4. 对已发布 profile 再次发布时，自动生成新版本（profile_id 后缀 `_vN`，旧版本 `retired`）。
5. 写入 `ops_audit_log`（`after_state=published`）。

---

### ADM-019 Parser Profile 状态机转换

**路由**: `POST /admin/parser-profiles/{parser_profile_id}/transition`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:157`

**验收标准**:
1. 直接切换 profile 状态（例如切换为 `retired`）。
2. 不触发校验流程。

---

## 5. Retrieval Profile 注册表

### ADM-020 列表 Retrieval Profiles

**路由**: `GET /admin/retrieval-profiles`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:176`

**验收标准**:
1. 返回 retrieval profile 列表与 `total`。
2. 支持 `state` 查询参数过滤。

---

### ADM-021 创建 Retrieval Profile

**路由**: `POST /admin/retrieval-profiles`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:185`

**验收标准**:
1. 接收 `profile_config`（BM25 权重、vector 权重、rerank 配置等）。
2. 初始状态为 `draft`，版本为 `1`。

---

### ADM-022 查看 Retrieval Profile

**路由**: `GET /admin/retrieval-profiles/{retrieval_profile_id}`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:194`

**验收标准**:
1. 按 ID 返回 profile 详情。
2. 不存在时返回 `404`。

---

### ADM-023 更新 Retrieval Profile

**路由**: `PATCH /admin/retrieval-profiles/{retrieval_profile_id}`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:205`

**验收标准**:
1. 仅允许更新 `draft` 状态的 profile。
2. 对已 `published` 的 profile 调用 `PATCH` 返回 `409 Conflict`。

---

### ADM-024 发布 Retrieval Profile

**路由**: `POST /admin/retrieval-profiles/{retrieval_profile_id}/publish`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:221`

**验收标准**:
1. 发布前调用 `retrieval` 下游接口 `POST /internal/retrieval-profiles/validate` 校验。
2. 校验失败时返回 `409`，并在响应体中包含错误码（如 `BM25_VECTOR_WEIGHT_SUM`）。
3. 校验成功后调用 `POST /internal/retrieval-profile-projections/sync` 同步 projection 到 retrieval runtime。
4. sync 失败记录审计日志，但不阻断发布成功返回。
5. 支持版本不可变性：再次发布生成 `_vN` 新版本。
6. 写入 `ops_audit_log`。

---

### ADM-025 Retrieval Profile 状态机转换

**路由**: `POST /admin/retrieval-profiles/{retrieval_profile_id}/transition`
**源码**: `services/admin/src/admin_service/profile_registry/routes.py:327`

**验收标准**:
1. 直接切换 profile 状态。
2. 不触发校验流程。

---

## 6. API Key 注册表

### ADM-026 列表 API Keys

**路由**: `GET /admin/api-keys`
**源码**: `services/admin/src/admin_service/api_key_registry/routes.py:33`

**验收标准**:
1. 返回 API key 元数据列表（不包含明文 key）。
2. 支持 `tenant_id` 与 `state` 过滤。
3. 返回字段中只包含 `key_hash`（64 位十六进制 SHA-256）。

---

### ADM-027 创建 API Key

**路由**: `POST /admin/api-keys`
**源码**: `services/admin/src/admin_service/api_key_registry/routes.py:46`

**验收标准**:
1. 生成前缀为 `rrag_` 的随机明文 key。
2. 仅存储 SHA-256 哈希，明文只在创建响应中返回一次。
3. 初始状态为 `active`。
4. 需要 admin 角色，否则返回 `403`。

---

### ADM-028 查看 API Key

**路由**: `GET /admin/api-keys/{api_key_id}`
**源码**: `services/admin/src/admin_service/api_key_registry/routes.py:56`

**验收标准**:
1. 返回 key 元数据，包含 `key_hash`。
2. 不返回明文 key。

---

### ADM-029 更新 API Key

**路由**: `PATCH /admin/api-keys/{api_key_id}`
**源码**: `services/admin/src/admin_service/api_key_registry/routes.py:67`

**验收标准**:
1. 可更新 `display_name`、`knowledge_scopes`、`roles`、`debug_permission`、`token_budget_limit`、`expires_at`。
2. 返回更新后的 key 元数据。

---

### ADM-030 轮换 API Key

**路由**: `POST /admin/api-keys/{api_key_id}/rotate`
**源码**: `services/admin/src/admin_service/api_key_registry/routes.py:80`

**验收标准**:
1. 生成新的明文 key 并更新 `key_hash`。
2. 更新 `last_rotated_at` 字段。
3. 返回新的 `plaintext_key`。

---

### ADM-031 禁用 API Key

**路由**: `POST /admin/api-keys/{api_key_id}/disable`
**源码**: `services/admin/src/admin_service/api_key_registry/routes.py:93`

**验收标准**:
1. 将 key 状态设置为 `disabled`。
2. 返回更新后的 key 元数据。

---

### ADM-032 吊销 API Key

**路由**: `POST /admin/api-keys/{api_key_id}/revoke`
**源码**: `services/admin/src/admin_service/api_key_registry/routes.py:105`

**验收标准**:
1. 将 key 状态设置为 `revoked`。
2. 返回更新后的 key 元数据。

---

## 7. 操作审计日志

### ADM-033 审计日志查询（POST）

**路由**: `POST /admin/ops/audit-log`
**源码**: `services/admin/src/admin_service/ops_audit/routes.py:18`

**验收标准**:
1. 支持过滤字段：`actor_id`、`target_type`、`target_id`、`tenant_id`、`collection_id`。
2. 支持 `limit`/`offset` 分页。
3. 返回 `items` 与 `total`。

---

### ADM-034 审计日志查询（GET）

**路由**: `GET /admin/ops/audit-log`
**源码**: `services/admin/src/admin_service/ops_audit/routes.py:40`

**验收标准**:
1. 与 POST 版本查询能力相同，过滤条件通过 query string 传递。
2. 支持 `target_type=collection` 等常用过滤。

---

## 8. 文档生命周期操作

### ADM-035 归档文档

**路由**: `POST /admin/documents/{final_doc_id}/archive`
**源码**: `services/admin/src/admin_service/document_ops/routes.py:37`

**验收标准**:
1. 需要 admin 角色，否则返回 `403`。
2. 通过 `PublishingWorkerClient` 调用下游 `POST /internal/published-documents/{id}/archive`。
3. 使用稳定的 `idempotency_key` 写入 `ops_audit_log`。
4. 下游返回 404 时映射为 `404 Not Found`。
5. 下游返回 503 或连接失败时映射为 `503 DOWNSTREAM_UNAVAILABLE`。
6. 成功时返回 `success: true`、`new_state: "ARCHIVED"`。

---

### ADM-036 撤回文档

**路由**: `POST /admin/documents/{final_doc_id}/retract`
**源码**: `services/admin/src/admin_service/document_ops/routes.py:54`

**验收标准**:
1. 代理调用 publishing-worker `POST /internal/published-documents/{id}/retract`。
2. 写入 `ops_audit_log`。
3. 成功时返回 `new_state: "RETRACTED"`。

---

### ADM-037 重新索引文档

**路由**: `POST /admin/documents/{final_doc_id}/reindex`
**源码**: `services/admin/src/admin_service/document_ops/routes.py:71`

**验收标准**:
1. 通过 `IndexingClient.get_parse_snapshot()` 拉取 ParseSnapshot。
2. 构造 `IndexBuildRequestedCommand`（含 `command_id`、`trace_id`、`idempotency_key`、`actor`、`tenant_id`、`collection_id`、`target_type`、`target_id`、`payload`）。
3. 提交到 indexing 下游 `POST /internal/index-jobs`。
4. 快照不存在时返回 `404`。
5. 成功时返回 `new_state: "REINDEXING"` 与下游 `job_id`。
6. 写入 `ops_audit_log`。

---

## 9. 下游客户端

### ADM-038 IndexingClient

**源码**: `services/admin/src/admin_service/downstream_clients/indexing_client.py`

**已实现方法**:
1. `get_parse_snapshot(id)` — `GET /internal/parse-snapshots/{id}`
2. `submit_index_job(payload)` — `POST /internal/index-jobs`
3. `get_index_job(job_id)` — `GET /internal/index-jobs/{job_id}`
4. `validate_parser_profile(payload)` — `POST /internal/parser-profiles/validate`

**错误映射**:
- 连接失败 / 超时 → `DOWNSTREAM_UNAVAILABLE` (503)
- `validate_parser_profile` 返回 404/501 → `DOWNSTREAM_NOT_IMPLEMENTED` (501)
- 409 → `CONFLICT` (409)

---

### ADM-039 RetrievalClient

**源码**: `services/admin/src/admin_service/downstream_clients/retrieval_client.py`

**已实现方法**:
1. `validate_retrieval_profile(payload)` — `POST /internal/retrieval-profiles/validate`
2. `sync_retrieval_profile_projection(payload)` — `POST /internal/retrieval-profile-projections/sync`

**错误映射**: 与 IndexingClient 一致。

---

### ADM-040 PublishingWorkerClient

**源码**: `services/admin/src/admin_service/downstream_clients/publishing_worker_client.py`

**已实现方法**:
1. `archive_document(id, payload)` — `POST /internal/published-documents/{id}/archive`
2. `retract_document(id, payload)` — `POST /internal/published-documents/{id}/retract`

**错误映射**:
- 404 → `NOT_FOUND`
- 其他 4xx/5xx → `DOWNSTREAM_ERROR`

---

### ADM-041 AccessClient

**源码**: `services/admin/src/admin_service/downstream_clients/access_client.py`

**已实现方法**:
1. `sync_api_key_projection(payload)` — `POST /internal/api-key-projections/sync`

**说明**: 客户端实现完整，但当前尚未被 API Key 生命周期路由调用。

---

### ADM-042 统一下游错误模型

**源码**: `services/admin/src/admin_service/downstream_clients/errors.py`

**验收标准**:
1. `DownstreamError` 包含 `code`、`message`、`status_code`。
2. 工厂方法：`not_implemented()` (501)、`unavailable()` (503)、`conflict()` (409)。

---

## 10. 健康检查

### ADM-043 服务健康

**路由**: `GET /health`
**源码**: `services/admin/src/admin_service/main.py:32`

**验收标准**:
1. 返回 `{"service": "admin", "version": "...", "status": "ok"}`。
2. 响应码 `200`。

---

## 11. 非功能需求

### 安全
1. 所有 `/admin/*` 端点（除 `/admin/auth/login` 和 `/health`）均经过 `require_auth` 校验。
2. 控制操作需 `knowledge_admin` 或 `platform_admin` 角色。
3. JWT 支持 issuer/audience 校验，production 模式强制关闭默认 secret。

### 审计
1. Profile 发布、Document archive/retract/reindex 必须写入 `ops_audit_log`。
2. 审计记录包含 `command_id`、`trace_id`、`idempotency_key`、`actor`、`tenant_id`、`collection_id`、`target_type`、`target_id`、`before_state`、`after_state`。

### 错误处理
1. 下游服务不可用统一返回 `downstream_unavailable` 错误码与 503 状态码。
2. 下游 API 不存在统一返回 `downstream_not_implemented` 错误码与 501 状态码。
3. 业务冲突统一返回 `conflict` 错误码与 409 状态码。

---

## 12. 变更日志

| 日期 | 版本 | 变更 |
|-----|------|------|
| 2026-06-06 | 1.0.0 | 基于当前代码实现整理 admin 模块已实现功能清单 |
