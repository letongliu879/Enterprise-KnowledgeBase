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
- `index_projection_idempotency`
  - `IndexProjectionSyncController` 内部维护，用于 projection sync 幂等性控制

说明：

- file projection 类仍然存在，但当前只作为测试替身使用
- 运行时默认 bean 已经固定到 JDBC 主链（`RetrievalDataConfiguration` 中 `@ConditionalOnMissingBean`）
- 所有运行时事实源（profile、index、published document、chunk）均通过显式 projection sync 接收，不做跨服务表直连

## 3. 当前执行链路

`RetrievalService.retrieve(...)` 现在的执行顺序如下：

1. `CollectionRetrievalPlanBuilder` 为每个 collection 构建 `CollectionRetrievalPlan`
2. `QueryPreparationService` 做 query 预处理（含 cross-languages、keyword extraction、metadata filter 解析）
3. `RetrievalService.buildScope(...)` 构建 `RetrievalScope`（合并 allowedDocIds、metadataFilters、permissionFingerprint）
4. `RecallOrchestrator` 做 hybrid recall（OpenSearch + Qdrant → fusion）
5. `RerankService` 做 rerank（live rerank 或 heuristic fallback）
6. `SmartTopKCutoffService` 选 seeds（智能 cutoff + 去重）
7. `NeighborChunkExpander` 与 `BreadcrumbChunkExpander` 做扩展
8. `RagflowTocAggregationService` 做 TOC 聚合与 boost
9. `RagflowChildrenAggregationService` 做子 chunk 聚合（mom_id 归并）
10. `JdbcRetrievalTraceRecorder` 记录 trace
11. `KnowledgeContextPacker` 打包 `KnowledgeContext`

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
| Key 前缀 | `reality-rag:retrieval:qemb:v1:{sha256(...)}` |
| hash 内容 | `query_text` + `embedding_model` + `embedding_client` + `embedding_base_url_fingerprint` |
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
| Key 前缀 | `reality-rag:retrieval:recall:v1:{sha256(...)}` |
| hash 内容 | `CollectionRetrievalPlan` 的完整投影：`query_text` + `principal_id` + `principal_groups` + `collection_ids` + `active_index_versions` + `profile_hashes` + `embedding_models` + `allowed_doc_ids_hash` + `metadata_filters_hash` + `lifecycle_filter_hash` + `include_deprecated` + `candidate_top_k` + `opensearch_index` + `qdrant_collection` |
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
    require-redis: false     # true 时 Redis 不可用时抛异常（默认 false，fail-open）
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

- `services/indexing` 在 chunk revision 变更或 index version 激活后调用此接口清理检索缓存
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

- 缺 profile：直接抛 `ResponseStatusException(400)`
- 缺 active index：直接抛 `ResponseStatusException(400)`
- `allowed_doc_ids` 来自 `published_documents`，按 `published_document_state` 过滤
- `include_deprecated=false` 时只允许 `PUBLISHED`

这意味着：

- "key 有权限"不等于"一定能查到内容"
- 如果 collection 已建索引但还没有发布事实，plan 仍可构建，但 `allowed_doc_ids` 会为空
- 后续 `PermissionPrefilter` 会 fail-closed，结果为空，而不是把全部 chunk 放进结果

这条约束是当前代码明确实现的，不是文档约定。

## 6. 权限与过滤

`retrieval` 自己不做 API key 鉴权，但会执行 request 内部权限边界。

当前 `PermissionPrefilter` 会同时过滤：

- `collection_id`
- `published_document_state`（`allowed_states`）
- `allowed_doc_ids`
- chunk 级 principal / group 可见性
- metadata 里的 `visibility`

关键点：

- `allowed_doc_ids` 为空时，不会默认放行
- 这一点是为了避免"发布事实缺失但检索假成功"

此外，`RecallOrchestrator` 在 fusion 前额外执行 `intersectWithPermitted`，将 OpenSearch/Qdrant 返回的 chunk 与 `PermissionPrefilter` 后的 permitted set 做交集。即使后端过滤不完整，进入 fusion 和 cache 的候选集也经过最终权限裁剪。详见第 4.4 节。

## 7. query 预处理与 RAGFlow 风格能力

`QueryPreparationService` 当前执行顺序：

1. `MetadataFilterService.resolveAllowedDocIds(...)` — 解析 metadata filter 对 allowedDocIds 的进一步约束
2. 基础 queryText = `request.queryText()`
3. 如果 `enableRagflowCrossLanguages=true` 且 `request.crossLanguages()` 非空，调用 prompt backend 做跨语言翻译
4. 如果 `enableRagflowKeywordExtraction=true` 且 `request.keyword()=true`，调用 prompt backend 提取关键词并追加到 queryText

metadata filter 当前实现状态：

- `manual`：完全可用，不依赖 prompt backend。支持操作符 `=`, `!=`, `contains`, `not contains`, `in`, `not in`, `start with`, `end with`
- `auto` / `semi_auto`：依赖 prompt backend 生成过滤条件。若 `enableRagflowMetadataAutoFilter=false` 或 prompt backend 未配置，安全降级为不过滤（返回 baseDocIds）
- `cross_languages` / `keyword`：同样依赖 prompt backend，未配置时安全降级（不做翻译/不追加关键词）

prompt backend 未配置时（`livePromptStrategiesEnabled=false`），所有依赖它的能力都会安全降级，不会虚构条件。

## 8. recall / rerank 的当前实现状态

### 8.1 recall

当前 recall 主线是：

- `OpenSearchRecaller`（BM25）
- `QdrantRecaller`（dense vector）
- `HybridFusionService`（加权融合）

`retrieval.backends.live-recall-enabled=true` 且配置了真实地址时，会调用 OpenSearch / Qdrant 真实后端。

- **Normal mode**：如果真实后端调用抛异常或返回空结果，代码会静默 fallback 到基于 DB chunk 的本地 stub recall（WARN 日志）。stub 使用 query 词元在 `display_text` / `vector_text` 上做词法匹配打分。
- **Strict mode**（`require-live-backends=true`）：fallback 被禁止，任何后端失败或空结果均抛出 `IllegalStateException`。

Qdrant live recall 依赖 `QueryEmbeddingClient` 生成 query vector。embedding 的 strict 行为：

- Normal mode：未配置 live embedding 或 API 失败时，返回空 vector → Qdrant 可能返回空结果 → fallback 到 stub
- Strict mode：未配置 live embedding 或 API 失败时，直接抛 `IllegalStateException`

### 8.2 rerank

rerank 模式：

- `retrieval.search.enable-rerank=false` 或 profile `rerank_enabled=false` 时，跳过 rerank，按 recall score 排序
- `retrieval.backends.live-rerank-enabled=false` 时，走本地 heuristic rerank（`source_stage="rerank_heuristic"`）
- `live-rerank-enabled=true` 且配置了真实地址和 API key 后，走 live rerank（`source_stage="rerank_live"`）
- **Normal mode**: live rerank 异常或空结果时静默 fallback 到 heuristic（WARN 日志）
- **Strict mode**: live rerank 异常或空结果 → `IllegalStateException`

heuristic rerank 包含 RAGFlow 风格能力：token weighting（title / important keyword / question hint）、rank feature boost（pagerank / tag_fea）、RAGFlow rerank window。

### 8.3 strict mode 完整行为矩阵

| 组件 | Normal（未配置/失败） | Strict（未配置/失败） |
|---|---|---|
| OpenSearch recall | fallback 到 stub，WARN | `IllegalStateException` |
| Qdrant recall | fallback 到 stub，WARN | `IllegalStateException` |
| Embedding | 返回 empty list，WARN | `IllegalStateException` |
| Rerank | fallback 到 heuristic，WARN | `IllegalStateException` |
| Prompt strategies | 返回 empty / 跳过，无 WARN | 当前不抛异常（仅跳过） |

## 9. TOC 事实源

当前 TOC 不是单独的 `document_toc` 表。

`JdbcDocumentTocSource` 现在读取的是：

- `indexed_documents.outline`

条件是：

- `collection_id` 命中
- `final_doc_id` 命中
- `UPPER(state) IN ('ACTIVE', 'ACTIVATED')`
- 按 `activated_at DESC, updated_at DESC LIMIT 1`

所以现在的 TOC 聚合依赖的是 indexing 写进 `indexed_documents` 的 outline 字段。

`RagflowTocAggregationService` 的行为：

1. 选择得分最高的 document 作为 anchor
2. 读取该 document 的 TOC
3. 先用 token match 打分；若 `enableRagflowTocLlmSelector=true`，额外调用 prompt backend 做 LLM-based TOC 相关性选择
4. 对命中的 TOC node，boost 或添加其 `linked_chunk_ids` 对应的 chunk
5. 最终按 `ragflowTocTopN` 截断

## 10. 可观测性

当前 retrieval 已经把查询结果写入：

- `run_traces`
- `run_steps`

当前至少会写：

- `run_trace_id = retrieval_<query_id>`
- `step_name = retrieval.response`
- `step_name = retrieval.failure`

`JdbcRetrievalTraceRecorder` 的写入行为：

- `run_traces`：先 UPDATE，若 updated==0 则 INSERT（upsert 语义）
- `run_steps`：纯 INSERT

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
- `source_stages`
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
| `pack_budget` | > 0；> 100000 时 warning |
| `similarity_threshold` | 0.0 ~ 1.0；> 0.9 或 < 0.1 时 warning |
| `rerank_enabled` | 必填，必须是 boolean；true 且 `rerank_model`="none" 时 warning |
| `rerank_model` | 必填，必须在支持列表中 (`default`, `none`, `bge-reranker-v2-m3`, `rerank-v1`, `rerank-multilingual-v1.0`) |
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

当 `valid=false` 时，`canonical_config` 字段不存在，`profile_hash` 为占位值 `sha256:0000000000000000000000000000000000000000000000000000000000000000`。

### 11.4 与 admin 控制面的边界

- admin 负责 RetrievalProfile CRUD、审批流、版本管理
- retrieval 负责校验 profile 在 runtime 是否可执行，并生成 canonical runtime view
- admin 发布 RetrievalProfile 前必须调用此接口；retrieval 不主动调用 admin
- 若 `valid=false`，admin 拒绝发布并写 `ops_audit_log`（`after_state=rejected`）
- 若 `valid=true`，admin 将 `runtime_canonical_config`、`profile_hash`、`validator_version`、`warnings` 写入 profile 记录后发布

## 12. 配置

主配置在 `src/main/resources/application.yaml`。

关键项：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `server.port` | 18082 | 服务端口 |
| `spring.datasource.url` | `jdbc:postgresql://127.0.0.1:5432/reality_rag` | 主数据库 |
| `retrieval.backends.live-recall-enabled` | `false` | 是否启用 OpenSearch/Qdrant live recall |
| `retrieval.backends.live-embedding-enabled` | `false` | 是否启用 live embedding |
| `retrieval.backends.live-rerank-enabled` | `false` | 是否启用 live rerank |
| `retrieval.backends.live-prompt-strategies-enabled` | `false` | 是否启用 prompt backend（auto filter / cross languages / keyword） |
| `retrieval.backends.require-live-backends` | `false` | strict mode：禁止所有 fallback |
| `retrieval.search.fused-top-m` | 60 | recall 后截断进入 rerank 的候选数 |
| `retrieval.search.enable-rerank` | `true` | 全局 rerank 开关 |
| `retrieval.search.rerank-top-n` | 10 | rerank 后保留数量 |
| `retrieval.search.enable-smart-top-k` | `true` | 智能 cutoff 开关 |
| `retrieval.search.smart-min-k` | 2 | cutoff 最少保留 |
| `retrieval.search.smart-max-k` | 8 | cutoff 最多保留 |
| `retrieval.search.enable-neighbor-expansion` | `true` | neighbor 扩展开关 |
| `retrieval.search.neighbor-hops` | 2 | neighbor 扩展跳数 |
| `retrieval.search.enable-breadcrumb-expansion` | `true` | breadcrumb 扩展开关 |
| `retrieval.search.enable-ragflow-toc-aggregation` | `true` | TOC 聚合开关 |
| `retrieval.search.enable-ragflow-children-aggregation` | `true` | children 聚合开关 |
| `retrieval.cache.enabled` | `true` | 缓存总开关 |
| `retrieval.cache.provider` | `noop` | 缓存提供者：noop / redis |
| `retrieval.cache.fail-open` | `true` | Redis 故障时是否 fail-open |
| `retrieval.cache.require-redis` | `false` | true 时 Redis 不可用抛异常 |

## 附录 A. 当前本地验证事实

仓库里已有 DB-backed 验证：

- `DbBackedRuntimeRetrieveControllerTest`
  - 验证 retrieval 运行时可直接使用 DB-backed profile / index / chunk / trace
  - 覆盖：plan build、recall、rerank、smart cutoff、neighbor expansion、breadcrumb expansion、TOC aggregation、children aggregation、trace write、context pack
- 其他场景测试（均使用 file projection 或 DB-backed fixture）：
  - `BreadcrumbExpansionRetrieveControllerTest`
  - `CachePurgeControllerTest`
  - `MetadataFilterRetrieveControllerTest`
  - `NeighborExpansionRetrieveControllerTest`
  - `RagflowChildrenAggregationRetrieveControllerTest`
  - `RagflowRankFeaturesRetrieveControllerTest`
  - `RagflowTocAggregationRetrieveControllerTest`
  - `RagflowTocDisabledRetrieveControllerTest`
  - `RagflowTokenWeightingRetrieveControllerTest`
  - `RerankDisabledRetrieveControllerTest`
  - `RetrievalProfileValidateControllerTest`
  - 缓存测试：`NoOpRetrievalCacheTest`, `RetrievalCacheKeyBuilderTest`, `CachedQueryEmbeddingClientTest`, `RecallOrchestratorCacheTest`
  - Backend 测试：`OpenSearchRecallerTest`, `QdrantRecallerTest`, `RerankServiceTest`

**检索 backend 的真实使用状态**

smoke 测试 profile 配置为 live 模式：

- `live-recall-enabled: true` → OpenSearch + Qdrant
- `live-embedding-enabled: true` → SiliconFlow BAAI/bge-m3
- `live-rerank-enabled: true` → SiliconFlow BAAI/bge-reranker-v2-m3
- `cache.enabled: false`（smoke 测试关闭缓存以避免干扰）

**模式行为**：

| Mode | Backend 不可用 | Embedding 失败 | Rerank 失败 | 日志 |
|---|---|---|---|---|
| Normal | fallback 到 stub，WARN 日志 | 返回 empty，WARN 日志 | fallback 到 heuristic，WARN 日志 | `live recall failed — falling back to stub` |
| Strict (`require-live-backends=true`) | 抛出 `IllegalStateException`，请求失败 | 抛出 `IllegalStateException`，请求失败 | 抛出 `IllegalStateException`，请求失败 | `required but failed` / `required but not configured` |

**运行时必须通过 projection sync 接收事实**

- admin -> retrieval：`/internal/retrieval-profile-projections/sync`
- indexing -> retrieval：`/internal/index-projections/sync`

如果缺少 projection sync，retrieval 会因找不到 profile、index 或 published document 而 fail-closed 返回空结果。这不是服务故障，而是"运行时尚未收到投影"的预期行为。
