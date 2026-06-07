# admin 对外接口契约

## Inbound（admin 对外暴露的 REST API）

### Health
- `GET /health` → `{"status": "ok", "service": "admin", "version": "0.1.0"}`

### Auth
| 端点 | 方法 | 鉴权 | 说明 |
|------|------|------|------|
| `/admin/auth/login` | POST | 无 | `LoginRequest(email, password)` → `LoginResponse(access_token, token_type)` |
| `/admin/auth/logout` | POST | Bearer | 作废 session（TODO: 完整 session 失效） |
| `/admin/auth/me` | GET | Bearer | `AdminUserResponse(user_id, email, display_name, roles, tenant_id, allowed_tenants, allowed_collections)` |

### Collections

| 端点 | 方法 | 角色 | 说明 |
|------|------|------|------|
| `/admin/collections` | GET | require_auth | `?tenant_id=` → `CollectionListResponse(items, total)` |
| `/admin/collections` | POST | knowledge_admin | `CollectionCreateRequest` → `AdminCollection` |
| `/admin/collections/{collection_id}` | GET | require_auth | → `AdminCollection` / 404 |
| `/admin/collections/{collection_id}` | PATCH | knowledge_admin | `CollectionUpdateRequest` → `AdminCollection` / 404 |
| `/admin/collections/{collection_id}/lifecycle` | POST | knowledge_admin | `CollectionLifecycleTransitionRequest(target_state, reason)` → `AdminCollection` / 404 |
| `/admin/collections/{collection_id}/bindings` | GET | require_auth | → `list[CollectionProfileBinding]` |
| `/admin/collections/{collection_id}/bindings/current` | GET | require_auth | → `CollectionProfileBinding` / 404 |
| `/admin/collections/{collection_id}/bindings` | POST | knowledge_admin | `ProfileBindingCreateRequest(parser_profile_id, retrieval_profile_id, approval_policy_id)` → `ProfileBindingResponse(binding, previous_binding_id)` / 404 |

### Parser Profiles

| 端点 | 方法 | 角色 | 说明 |
|------|------|------|------|
| `/admin/parser-profiles` | GET | require_auth | `?state=` → `ParserProfileListResponse(items, total)` |
| `/admin/parser-profiles` | POST | knowledge_admin | `ParserProfileCreateRequest` → `ParserProfile(state=draft, version=1)` |
| `/admin/parser-profiles/{parser_profile_id}` | GET | require_auth | → `ParserProfile` / 404 |
| `/admin/parser-profiles/{parser_profile_id}` | PATCH | knowledge_admin | `ParserProfileUpdateRequest` → 仅 draft 可改 / 409 published → 404 |
| `/admin/parser-profiles/{parser_profile_id}/publish` | POST **async** | knowledge_admin | → 调 indexing validate → 失败 409 + ops_audit_log → 成功 state=published + 存储 canonical_config |
| `/admin/parser-profiles/{parser_profile_id}/transition` | POST | knowledge_admin | `ProfileStateTransitionRequest(target_state)` → 直接切换状态，不调 validate |

### Retrieval Profiles

| 端点 | 方法 | 角色 | 说明 |
|------|------|------|------|
| `/admin/retrieval-profiles` | GET | require_auth | `?state=` → `RetrievalProfileListResponse(items, total)` |
| `/admin/retrieval-profiles` | POST | knowledge_admin | `RetrievalProfileCreateRequest` → `RetrievalProfileAdmin(state=draft, version=1)` |
| `/admin/retrieval-profiles/{retrieval_profile_id}` | GET | require_auth | → `RetrievalProfileAdmin` / 404 |
| `/admin/retrieval-profiles/{retrieval_profile_id}` | PATCH | knowledge_admin | `RetrievalProfileUpdateRequest` → 仅 draft 可改 / 409 published → 404 |
| `/admin/retrieval-profiles/{retrieval_profile_id}/publish` | POST **async** | knowledge_admin | → 调 retrieval validate → 失败 409 → 成功 state=published + sync projection (fail-open) |
| `/admin/retrieval-profiles/{retrieval_profile_id}/transition` | POST | knowledge_admin | `ProfileStateTransitionRequest(target_state)` → 直接切换状态 |

### API Keys

| 端点 | 方法 | 角色 | 说明 |
|------|------|------|------|
| `/admin/api-keys` | GET | require_auth | `?tenant_id=&state=` → `ApiKeyListResponse(items, total)` |
| `/admin/api-keys` | POST | knowledge_admin | `ApiKeyCreateRequest` → `ApiKeyCreateResponse(entry, plaintext_key)` — plaintext 仅返回一次 |
| `/admin/api-keys/{api_key_id}` | GET | require_auth | → `ApiKeyRegistryEntryAdmin`（含 key_hash，不含 plaintext）/ 404 |
| `/admin/api-keys/{api_key_id}` | PATCH | knowledge_admin | `ApiKeyUpdateRequest` → / 404 |
| `/admin/api-keys/{api_key_id}/rotate` | POST | knowledge_admin | → `ApiKeyRotateResponse(entry, plaintext_key)` / 404 |
| `/admin/api-keys/{api_key_id}/disable` | POST | knowledge_admin | → `ApiKeyRegistryEntryAdmin(state=disabled)` / 404 |
| `/admin/api-keys/{api_key_id}/revoke` | POST | knowledge_admin | → `ApiKeyRegistryEntryAdmin(state=revoked)` / 404 |

### Ops Audit

| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin/ops/audit-log` | POST | `AuditLogQueryRequest(actor_id, target_type, target_id, tenant_id, collection_id, limit, offset)` → `AuditLogListResponse(items, total, limit, offset)` |
| `/admin/ops/audit-log` | GET | 同 POST，参数通过 query string |

### Document Lifecycle Ops

| 端点 | 方法 | 角色 | 说明 |
|------|------|------|------|
| `/admin/documents/{final_doc_id}/archive` | POST **async** | knowledge_admin | `DocumentLifecycleRequest` → `DocumentLifecycleResponse(new_state=ARCHIVED)` / 404 / 503 |
| `/admin/documents/{final_doc_id}/retract` | POST **async** | knowledge_admin | `DocumentLifecycleRequest` → `DocumentLifecycleResponse(new_state=RETRACTED)` / 404 / 503 |
| `/admin/documents/{final_doc_id}/reindex` | POST **async** | knowledge_admin | `DocumentReindexRequest(collection_id, tenant_id, parse_snapshot_id, ...)` → `DocumentLifecycleResponse(new_state=REINDEXING, job_id)` / 404 / 503 |

## Outbound（admin 发出的下游请求）

| 方向 | 端点 | Client 类 | 说明 |
|------|------|-----------|------|
| → indexing | `GET /internal/parse-snapshots/{id}` | `IndexingClient.get_parse_snapshot` | 获取解析快照 |
| → indexing | `POST /internal/index-jobs` | `IndexingClient.submit_index_job` | 提交索引构建任务 |
| → indexing | `GET /internal/index-jobs/{job_id}` | `IndexingClient.get_index_job` | 查询索引任务状态 |
| → indexing | `POST /internal/parser-profiles/validate` | `IndexingClient.validate_parser_profile` | 校验 parser 配置 |
| → retrieval | `POST /internal/retrieval-profiles/validate` | `RetrievalClient.validate_retrieval_profile` | 校验 retrieval 配置 |
| → retrieval | `POST /internal/retrieval-profile-projections/sync` | `RetrievalClient.sync_retrieval_profile_projection` | 同步 profile 投影到 retrieval 运行时 |
| → publishing-worker | `POST /internal/published-documents/{id}/archive` | `PublishingWorkerClient.archive_document` | 归档已发布文档 |
| → publishing-worker | `POST /internal/published-documents/{id}/retract` | `PublishingWorkerClient.retract_document` | 撤回已发布文档 |
| → access | `POST /internal/api-key-projections/sync` | `AccessClient.sync_api_key_projection` | 同步 API Key 投影（client 已就绪，未接入） |

## 关键 DTO 定义

### AdminCollection (from contracts)
```
collection_id, tenant_id, name, description, lifecycle_state (active|archived|inactive),
authority_level (0-10), access_policy (dict), default_parser_profile_id,
default_retrieval_profile_id, default_approval_policy_id, created_by, created_at,
updated_by, updated_at
```

### CollectionProfileBinding (from contracts)
```
binding_id, tenant_id, collection_id, parser_profile_id, retrieval_profile_id,
approval_policy_id, effective_from, effective_to (nullable), binding_version,
config_hash (SHA-256), created_by, created_at
```

### ParserProfile (from contracts)
```
parser_profile_id, name, description, parser_id (naive|presentation|paper|qa|...),
parser_config (dict), runtime_canonical_config (nullable), profile_hash,
validator_version, warnings (list), version (int), state (draft|published|retired),
created_by, created_at, updated_by, updated_at
```

### RetrievalProfileAdmin (from contracts)
```
retrieval_profile_id, name, description, profile_config (dict),
runtime_canonical_config (nullable), profile_hash, validator_version,
warnings (list), version (int), state (draft|published|retired),
created_by, created_at, updated_by, updated_at
```

### ApiKeyRegistryEntryAdmin (from contracts)
```
api_key_id, tenant_id, display_name, agent_type_id, key_hash (SHA-256 hex),
knowledge_scopes, roles, debug_permission, token_budget_limit,
state (active|disabled|revoked), expires_at (nullable), created_by, created_at,
updated_by, updated_at, last_rotated_at (nullable)
```

### OpsAuditLogEntry (from contracts)
```
audit_id, command_id, trace_id, idempotency_key, actor_id, tenant_id,
collection_id (nullable), action, target_type, target_id, before_state (nullable),
after_state (nullable), reason (nullable), payload_hash, created_at
```

### DocumentLifecycleResponse
```
success (bool), final_doc_id, previous_state (nullable), new_state (nullable),
job_id (nullable — 仅 reindex)
```

## 配置环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADMIN_JWT_SECRET` | `change-me-in-production` | JWT 签名密钥 |
| `ADMIN_JWT_EXPIRATION_HOURS` | `24` | JWT 有效时间 |
| `ADMIN_SESSION_EXPIRATION_HOURS` | `168` | 会话窗口 |
| `ADMIN_JWT_ISSUER` | `""` | production 模式必填 |
| `ADMIN_JWT_AUDIENCE` | `""` | production 模式必填 |
| `AUTH_MODE` | `smoke` | `smoke` 或 `production` |
| `DATABASE_URL` | `sqlite:///admin.db` | 数据库连接 |
| `INDEXING_BASE_URL` | `http://localhost:18082` | — |
| `RETRIEVAL_BASE_URL` | `http://localhost:18083` | — |
| `ACCESS_BASE_URL` | `http://localhost:18081` | — |
| `PUBLISHING_WORKER_BASE_URL` | `http://localhost:18085` | — |

## 错误与幂等

- 所有控制操作写入 `ops_audit_log`，含 `command_id`, `trace_id`, `idempotency_key`
- `idempotency_key` 来自稳定业务对象（如 `archive:{final_doc_id}`），不使用随机 ID
- 下游 404 → admin 404 `NOT_FOUND`
- 下游 4xx/5xx → admin 统一错误码（501/503/409），不暴露下游内部细节
- 下游失败时 **不写本地 success 状态**，审计记录 `after_state=failed`

## 数据表名（避免混淆）

| 概念 | 表名 | 说明 |
|------|------|------|
| Retrieval profile | `retrieval_profiles_admin` | admin 控制面（不是 retrieval 运行时的 `retrieval_profiles`） |
| Collection | `collections` | — |
| Profile binding | `collection_profile_bindings` | — |
| API Key | `api_key_registry` | — |
| Ops audit log | `ops_audit_log` | — |
| Admin user | `admin_users` | — |
| Admin session | `admin_sessions` | — |
