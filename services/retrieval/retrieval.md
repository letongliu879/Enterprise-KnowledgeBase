# retrieval 运行时设计

## 1. 定位

`retrieval` 是内部检索内核，不对外承担接入职责。

它只接收来自 `access` 的受控 `RetrieveRequest`，然后完成：

1. collection 级检索计划构建
2. 权限与发布态过滤
3. 召回、排序、扩展与上下文打包
4. `KnowledgeContext` 返回
5. 检索 trace 落库

## 2. 当前运行时事实源

当前运行时默认全部走 JDBC，不再依赖生产内存实现。

代码里实际读取的表如下：

- `retrieval_profiles`
  - `JdbcRetrievalProfileStore`
  - 通过 `POST /internal/retrieval-profile-projections/sync` 接收 admin 投影同步
- `published_documents`
  - `JdbcPublishedDocumentSource`
  - 通过 `POST /internal/index-projections/sync` 接收 indexing 投影同步
- `index_registry` + `index_versions`
  - `JdbcIndexRegistrySource`
  - 通过 `POST /internal/index-projections/sync` 接收 indexing 投影同步
- `chunk_registry`
  - `JdbcChunkRegistryKnowledgeStore`
  - 通过 `POST /internal/index-projections/sync` 接收 indexing 投影同步
- `indexed_documents.outline`
  - `JdbcDocumentTocSource`
- `run_traces` + `run_steps`
  - `JdbcRetrievalTraceRecorder`

说明：

- file projection 类仍然存在，但当前只作为测试替身使用
- 运行时默认 bean 已经固定到 JDBC 主链
- 所有运行时事实源（profile、index、published document、chunk）均通过显式 projection sync 接收，不做跨服务表直连

## 3. 当前执行链路

`RetrievalService` 现在的执行顺序如下：

1. `CollectionRetrievalPlanBuilder` 为每个 collection 构建 `CollectionRetrievalPlan`
2. `QueryPreparationService` 做 query 预处理
3. `RecallOrchestrator` 做 hybrid recall
4. `RerankService` 做 rerank
5. `SmartTopKCutoffService` 选 seeds
6. `NeighborChunkExpander` 与 `BreadcrumbChunkExpander` 做扩展
7. `RagflowTocAggregationService` 与 `RagflowChildrenAggregationService` 做聚合
8. `JdbcRetrievalTraceRecorder` 记录 trace
9. `KnowledgeContextPacker` 打包 `KnowledgeContext`

## 4. 缓存层

retrieval 服务自带两层 read-path 缓存，完全独立于上游 RAGFlow，不依赖 upstream Redis key。

### 4.1 设计原则

- 缓存只插在自有边界：`QueryEmbeddingClient` decorator 和 `RecallOrchestrator` 内部
- 不缓存最终 `KnowledgeContext`（后面还有 expansion、TOC aggregation、packing、trace）
- 失效靠 `activeIndexVersionId` + `profileHash` + `scope/filter hash`，不扫 Redis，不依赖 upstream epoch
- 默认 `provider: noop`，不启用时不影响任何行为
- Redis 故障时 fail-open，不阻塞检索主链

### 4.2 第一层：Query Embedding Cache

`CachedQueryEmbeddingClient` 装饰真实 `QueryEmbeddingClient`（如 `OpenAiCompatibleQueryEmbeddingClient`）。

| 项 | 值 |
|---|---|
| Key 前缀 | `retrieval:qemb:v1:{sha256(...)}` |
| hash 内容 | `query` + `embedding_model` + `embedding_client` + `embedding_base_url_fingerprint` |
| TTL | 默认 24h (`retrieval.cache.query-embedding-ttl-seconds`) |
| 无关因子 | collection、权限、index version（query embedding 只取决于 query 和模型） |

行为：
- cache hit → 直接返回 embedding，不走外部 embedding 服务
- cache miss → 调用 delegate → 非空结果写入 Redis → 返回
- 空结果或 null 不写入缓存

### 4.3 第二层：Recall Candidate Cache

位于 `RecallOrchestrator.recall(...)` 内部，缓存融合后的候选 `RetrievedChunk` 列表。

| 项 | 值 |
|---|---|
| Key 前缀 | `retrieval:recall:v1:{sha256(...)}` |
| hash 内容 | `CollectionRetrievalPlan` 的完整投影：`query` + `principal_id` + `principal_groups` + `collection_ids` + `active_index_versions` + `profile_hashes` + `embedding_models` + `allowed_doc_ids_hash` + `metadata_filters_hash` + `lifecycle_filter_hash` + `include_deprecated` + `candidate_top_k` + `opensearch_index` + `qdrant_collection` |
| TTL | 默认 60s (`retrieval.cache.recall-ttl-seconds`) |
| 失效因子 | `activeIndexVersionId`、`profileHash`、filter hash 任一变化即 key miss |

行为：
- cache hit → 直接返回 fused candidates，不走 OpenSearch/Qdrant
- cache miss → 执行 hybrid recall → 权限裁剪 → fusion → 写入缓存 → 返回

### 4.4 权限边界加固

`RecallOrchestrator` 在 fusion 前强制执行：

```
live backend hits -> intersect permitted chunk ids -> fusion -> cache
```

`intersectWithPermitted` 将 OpenSearch/Qdrant 返回的 chunk 与 `PermissionPrefilter.filter(...)` 后的 `filteredChunks` 做 `chunkId` 交集。即使后端召回过滤不完整，最终进入 fusion 和 cache 的候选集都经过权限裁剪。

### 4.5 配置

```yaml
retrieval:
  cache:
    enabled: true
    provider: noop           # noop (默认) | redis
    redis-url: redis://127.0.0.1:6379/0
    key-prefix: reality-rag:retrieval
    query-embedding-ttl-seconds: 86400
    recall-ttl-seconds: 60
    fail-open: true
```

Maven 依赖：`spring-boot-starter-data-redis`（已加入 pom.xml）。

### 4.6 Cache Purge

`POST /internal/cache/purge` 提供按 scope 清理检索缓存的能力。

**请求体**（snake_case）：

```json
{
  "tenant_id": "tenant_acme",
  "collection_id": "col_default",
  "doc_id": "doc_001",
  "evidence_id": "chunk_001"
}
```

- `tenant_id`：必填
- `collection_id`、`doc_id`、`evidence_id`：可选，用于记录 purge scope

**响应**（snake_case）：

```json
{
  "purged_count": 0,
  "scope": {
    "tenant_id": "tenant_acme",
    "collection_id": "col_default",
    "doc_id": "doc_001",
    "evidence_id": "chunk_001"
  }
}
```

**实现说明**：

- 当前 cache key 使用 SHA-256 hash，无法按 tenant/collection/doc/evidence 精确匹配
- 实际执行的是前缀匹配删除（`key_prefix:*`），删除所有以 `retrieval.cache.key-prefix` 为前缀的 key
- `purged_count` 返回实际删除的 key 数量
- NoOp 模式下 `purged_count` 始终为 0

**调用方**：

- `services/indexing` 在 `materialize_chunk_revision` 成功后调用此接口清理检索缓存
- `services/indexing` 在 `IndexJobRunner.accept()` 成功激活 index version（`request_type="publish"` 或 `"reindex"`）后调用此接口清理检索缓存
- purge 失败记录 warning，不回滚 revision 或索引物化结果

### 4.7 不做的事

- 不改 `upstream/ragflow/`
- 不复用 upstream Redis key
- 不复用 GraphRAG cache
- 不缓存最终 answer
- 第一版不缓存最终 `KnowledgeContext`

## 5. 计划构建与 fail-closed

每个 collection 的 plan 当前由三类事实拼出来：

1. `retrieval_profiles`（通过 `/internal/retrieval-profile-projections/sync` 接收 admin 投影）
2. `index_registry` / `index_versions`（通过 `/internal/index-projections/sync` 接收 indexing 投影）
3. `published_documents`（通过 `/internal/index-projections/sync` 接收 indexing 投影）

`CollectionRetrievalPlanBuilder` 的当前规则：

- 缺 profile：直接报错
- 缺 active index：直接报错
- `allowed_doc_ids` 来自 `published_documents`
- `include_deprecated=false` 时只允许 `PUBLISHED`

这意味着：

- "key 有权限"不等于"一定能查到内容"
- 如果 collection 已建索引但还没有发布事实，plan 仍可构建，但 `allowed_doc_ids` 会为空
- 后续 recall 会 fail-closed，结果为空，而不是把全部 chunk 放进结果

这条约束是当前代码明确实现的，不是文档约定。

## 6. 权限与过滤

`retrieval` 自己不做 API key 鉴权，但会执行 request 内部权限边界。

当前 `PermissionPrefilter` 会同时过滤：

- `collection_id`
- `published_document_state`
- `allowed_doc_ids`
- chunk 级 principal / group 可见性
- metadata 里的 `visibility`

关键点：

- `allowed_doc_ids` 为空时，不会默认放行
- 这一点是为了避免"发布事实缺失但检索假成功"

此外，`RecallOrchestrator` 在 fusion 前额外执行 `intersectWithPermitted`，将 OpenSearch/Qdrant 返回的 chunk 与 `PermissionPrefilter` 后的 permitted set 做交集。即使后端过滤不完整，进入 fusion 和 cache 的候选集也经过最终权限裁剪。详见第 4.4 节。

## 7. query 预处理与 RAGFlow 风格能力

当前请求契约里已经接入这些字段：

- `cross_languages`
- `keyword`
- `meta_data_filter`

当前实现状态要分开看：

- `manual` `meta_data_filter` 已经可用
- `cross_languages`、`keyword`、`auto/semi_auto meta_data_filter` 依赖 prompt backend
- 没配 live prompt backend 时，会安全降级，不会虚构条件

## 8. recall / rerank 的当前实现状态

当前 recall 主线是：

- `OpenSearchRecaller`
- `QdrantRecaller`
- `HybridFusionService`

`retrieval.backends.live-recall-enabled=true` 且配置了真实地址时，会调用 OpenSearch / Qdrant 真实后端。**Normal mode**：如果真实后端调用抛异常或返回空结果，代码会静默 fallback 到基于 DB chunk 的本地 stub recall（WARN 日志）。**Strict mode**（`require-live-backends=true`）：fallback 被禁止，任何后端失败或空结果均抛出 `IllegalStateException`。

rerank 模式：

- `retrieval.backends.live-rerank-enabled=false` 时，走本地 heuristic rerank（`source_stage="rerank_heuristic"`）
- `live-rerank-enabled=true` 且配置了真实地址和 API key 后，走 live rerank（`source_stage="rerank_live"`）
- **Normal mode**: live rerank 异常时静默 fallback 到 heuristic（WARN 日志）
- **Strict mode**: live rerank 异常或空结果 → `IllegalStateException`

**Strict smoke 已验证的真实后端证据（2026-05-28, 28/28 PASS）**：

- retrieval smoke profile：`live-recall-enabled=true`、`live-rerank-enabled=true`
- OpenSearch 索引 `os_default_col_smoke_idxv_col_smoke_active` 含 smoke 测试文档
- Qdrant collection `qd_default_col_smoke_idxv_col_smoke_active` 含 smoke 测试 point（vector size=1024）
- PostgreSQL `run_steps` 记录到 `source_stages: ["rerank_live"]`，证明 live rerank 被实际调用
- Qdrant point 携带真实 1024 维向量，证明 SiliconFlow embedding（BAAI/bge-m3）被实际调用

## 9. TOC 事实源

当前 TOC 不是单独的 `document_toc` 表。

`JdbcDocumentTocSource` 现在读取的是：

- `indexed_documents.outline`

条件是：

- `collection_id` 命中
- `final_doc_id` 命中
- `state in ('ACTIVE', 'ACTIVATED')`

所以现在的 TOC 聚合依赖的是 indexing 写进 `indexed_documents` 的 outline 字段。

## 10. 可观测性

当前 retrieval 已经把查询结果写入：

- `run_traces`
- `run_steps`

当前至少会写：

- `run_trace_id = retrieval_<query_id>`
- `step_name = retrieval.response`
- `step_name = retrieval.failure`

当前记录内容包括：

- `query_id`
- `trace_id`
- `principal_id`
- `collection_scope`
- `retrieval_profile_id`
- `index_versions`
- `allowed_doc_ids`
- `chunk_ids`
- `final_doc_ids`
- `debug_ref`

排查一条查询时，应把 access 与 retrieval 的 `trace_id` 串起来一起看。

## 11. RetrievalProfile 运行时校验

`POST /internal/retrieval-profiles/validate` 是 retrieval 作为 runtime owner 提供的校验接口。

### 11.1 设计原则

- retrieval 只校验 runtime 可执行性，不做 admin 控制面校验
- 不修改 `retrieval_profiles` 表、不修改 retrieval cache、不改变 active profile
- 输出 `canonical_config` 和 `profile_hash`，供 admin 控制面参考

### 11.2 校验项

| 字段 | 规则 |
|---|---|
| `bm25_weight` | 0.0 ~ 1.0，且 + `vector_weight` = 1.0 |
| `vector_weight` | 0.0 ~ 1.0，且 + `bm25_weight` = 1.0 |
| `candidate_top_k` | > 0，且 <= 1000 |
| `pack_budget` | > 0 |
| `similarity_threshold` | 0.0 ~ 1.0 |
| `rerank_enabled` | boolean |
| `rerank_model` | 必须在支持列表中 (`default`, `none`, `bge-reranker-v2-m3`, `rerank-v1`, `rerank-multilingual-v1.0`) |
| `fail_policy` | `fail_open` 或 `fail_closed` |
| `expansion_policy` | 可选；如有 `type`，必须是 `neighbor` / `breadcrumb` / `none` |

### 11.3 输出格式

```json
{
  "valid": true,
  "canonical_config": {
    "bm25_weight": 0.3,
    "vector_weight": 0.7,
    "candidate_top_k": 20,
    "similarity_threshold": 0.75,
    "rerank_enabled": true,
    "rerank_model": "bge-reranker-v2-m3",
    "fail_policy": "fail_closed",
    "expansion_policy": {},
    "pack_budget": 1200
  },
  "profile_hash": "sha256:...",
  "warnings": [],
  "errors": [],
  "runtime_owner": "retrieval",
  "validator_version": "1.0.0"
}
```

当 `valid=false` 时，`canonical_config` 字段不存在，`profile_hash` 为占位值 `sha256:0000...`。

### 11.4 与 admin 控制面的边界

- admin 负责 RetrievalProfile CRUD、审批流、版本管理
- retrieval 负责校验 profile 在 runtime 是否可执行，并生成 canonical runtime view
- admin 发布 RetrievalProfile 前必须调用此接口；retrieval 不主动调用 admin
- 若 `valid=false`，admin 拒绝发布并写 `ops_audit_log`（`after_state=rejected`）
- 若 `valid=true`，admin 将 `runtime_canonical_config`、`profile_hash`、`validator_version`、`warnings` 写入 profile 记录后发布

## 12. 配置

主配置在 `src/main/resources/application.yaml`。

关键项：

- `server.port=18082`
- `spring.datasource.*`
- `retrieval.backends.*`
- `retrieval.search.*`
- `retrieval.cache.*`

## 附录 A. 当前本地验证事实

仓库里已有 DB-backed 验证：

- `DbBackedRuntimeRetrieveControllerTest`
  - 验证 retrieval 运行时可直接使用 DB-backed profile / index / chunk / trace
- `RealSqliteIndexingRegistrySmokeTest`
  - 验证本地 `.verify/runtime/indexing-real.db` 能读到 `col_default` 的 active index、chunk、`ret_default`
- `scripts/run_real_runtime_smoke.py`
  - 端到端 real-runtime smoke test，28/28 通过（已验证 strict mode，2026-05-28）
  - 验证真实多进程 HTTP + 真实 PostgreSQL + 契约投影同步全链路
  - 验证 profile projection sync、index projection sync、published document projection、hybrid recall、rerank、context pack 全链路
  - **Live dependency strict proof (28/28 PASS with `--require-live-backends`)**:
    - OpenSearch direct verification: `os_default_col_smoke_idxv_col_smoke_active` hits=1, `doc_smoke_test` confirmed
    - Qdrant direct verification: `qd_default_col_smoke_idxv_col_smoke_active` points=1, `doc_smoke_test` confirmed
    - OpenSearch live recall: `OpenSearch live recall returned 1 hits for collection=col_smoke`
    - SiliconFlow embedding: `SiliconFlow embedding succeeded, model=BAAI/bge-m3, dimension=1024`
    - Qdrant live recall: `Qdrant live recall returned 1 hits for collection=col_smoke`
    - SiliconFlow rerank: `SiliconFlow rerank succeeded, model=BAAI/bge-reranker-v2-m3, returned 1 results`
    - Trace `source_stages: ["rerank_live"]` recorded in PostgreSQL `run_steps`
    - Access query returns same doc_id/chunk through live retrieval path
  - JWT auth 使用 smoke-test-secret（test double）；production JWT 配置（issuer/audience）已实现，见 admin 测试
  - **Redis cache**: implementation complete（`RedisRetrievalCache.java`）；strict Redis smoke **NOT RUN**（credentials unavailable）。Normal mode uses noop provider。
  - **Strict mode 完整选项**: `py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends`
    - 禁止所有静默 fallback：recall stub、rerank heuristic、embedding empty/stub 均抛出 `IllegalStateException`
    - OpenSearch/Qdrant/SiliconFlow 任一不可达 → FAIL

**检索 backend 的真实使用状态**

retrieval recall/rerank 已配置为 live 模式（smoke profile）：

- `live-recall-enabled: true` → OpenSearch + Qdrant
- `live-embedding-enabled: true` → SiliconFlow BAAI/bge-m3
- `live-rerank-enabled: true` → SiliconFlow BAAI/bge-reranker-v2-m3
- `cache.enabled: false`

**模式行为**：

| Mode | Backend 不可用 | Embedding 失败 | Rerank 失败 | 日志 |
|---|---|---|---|---|
| Normal | 静默 fallback 到 stub，WARN 日志 | 静默 fallback 到 stub/empty，WARN 日志 | 静默 fallback 到 heuristic，WARN 日志 | `live recall failed — falling back to stub` |
| Strict (`--require-live-backends`) | 抛出 `IllegalStateException`，请求失败 | 抛出 `IllegalStateException`，请求失败 | 抛出 `IllegalStateException`，请求失败 | `required but failed` / `required but not configured` |

**Strict smoke 已验证的证据 (2026-05-28, 28/28 PASS)**：

- OpenSearch 索引 `os_default_col_smoke_idxv_col_smoke_active` 含 `doc_smoke_test`（direct `_search` hits=1）
- Qdrant collection `qd_default_col_smoke_idxv_col_smoke_active` 含 `doc_smoke_test`（direct `scroll` points=1）
- 日志：`OpenSearch live recall returned 1 hits`、`Qdrant live recall returned 1 hits`
- 日志：`SiliconFlow embedding succeeded, model=BAAI/bge-m3, dimension=1024`
- 日志：`SiliconFlow rerank succeeded, model=BAAI/bge-reranker-v2-m3, returned 1 results`
- Trace：`run_steps.details_json.source_stages: ["rerank_live"]`

**运行时必须通过 projection sync 接收事实**

- admin -> retrieval：`/internal/retrieval-profile-projections/sync`
- indexing -> retrieval：`/internal/index-projections/sync`

如果缺少 projection sync，retrieval 会因找不到 profile、index 或 published document 而 fail-closed 返回空结果。这不是服务故障，而是"运行时尚未收到投影"的预期行为。
