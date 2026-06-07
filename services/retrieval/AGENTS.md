# retrieval — 权限感知的混合检索内核

## 定位
retrieval 是平台唯一的检索内核，只接收来自 `access` 的受控 `RetrieveRequest`，不对外承担接入职责。

**不做的事**：API key 鉴权、文档准入/审批、索引构建、文件解析、RAGFlow upstream 调用。

## 边界原则
- 所有运行时事实（profile、index、published document、chunk）均通过显式 projection sync 接收，不做跨服务表直连
- 不读 upstream/ragflow 数据库，不复用上游 RAGFlow Redis key
- retrieval 自身不做 API key 鉴权，但执行 request 内部权限边界
- caching 只插在自有边界（query embedding + recall candidates），不依赖 upstream Redis key
- cache purge 按前缀匹配删除（`key_prefix:*`），fail-open
- `require-live-backends=true` 时禁止任何 fallback，否则静默降级 stub
- 缺 profile 或 active index 直接抛 400，fail-closed
- `allowedDocIds` 为空时不会默认放行（避免发布事实缺失但检索假成功）

## Bean 装配（RetrievalConfiguration）
所有 JDBC 实现均带 `@ConditionalOnMissingBean` → FileProjection 变体是测试替身：
- `PublishedDocumentSource` → `JdbcPublishedDocumentSource`
- `IndexRegistrySource` → `JdbcIndexRegistrySource`
- `RetrievalProfileStore` → `JdbcRetrievalProfileStore`
- `KnowledgeStore` → `JdbcChunkRegistryKnowledgeStore`
- `DocumentTocSource` → `JdbcDocumentTocSource`
- Embedding: `CachedQueryEmbeddingClient` 包装 `OpenAiCompatibleQueryEmbeddingClient`（live）或 `StubQueryEmbeddingClient`
- Prompt: `OpenAiCompatiblePromptModelClient`（live）或 `NoOpPromptModelClient`

## 核心数据流
```
access -> POST /internal/retrieve (RetrieveRequest)
  -> CollectionRetrievalPlanBuilder.build()       # 按 collection 构建计划（profile + index + published docs）
  -> QueryPreparationService.prepare()             # ① MetadataFilterService 解析 metadata filter →
                                                    # ② cross-languages 翻译（prompt）→
                                                    # ③ keyword extraction 追加到 queryText（prompt）
  -> RetrievalService.buildScope()                 # 合并 allowedDocIds、metadataFilters、permissionFingerprint
  -> RecallOrchestrator.recall()                   # per-collection: PermissionPrefilter → HybridRecaller(lexical+vector) → intersectWithPermitted → HybridFusion(max score merge)
  -> RerankService.rerank()                        # RAGFlow token weighting + rank features → live rerank / heuristic fallback
  -> SmartTopKCutoffService.selectSeeds()          # 动态阈值 max(ratio*top, top-delta, minScore) + minK 兜底
  -> ChunkExpander.expandNeighbors()               # 按 chunk_id 序号 ±hops（decay=0.8）
  -> ChunkExpander.expandBreadcrumbs()             # 按 section path prefix 分组（decay=0.7, limit=3）
  -> ChunkAggregationService.aggregateByToc()      # anchor=最高分 doc → TOC 匹配/LLM 选择 → boost/追加 chunk
  -> ChunkAggregationService.aggregateByChildren() # mom_id 归并子 chunk 到父 chunk
  -> JdbcRetrievalTraceRecorder.record()           # upsert run_traces + INSERT run_steps
  -> KnowledgeContextPacker.pack()                 # 按 maxSegmentsPerFile=3, maxTotalChars=48000 截断打包
  -> 返回 KnowledgeContext 给 access
```

## 关键对象
- `RetrieveRequest`：queryId、traceId、principal（{user_id, role_ids[], group_ids[], attributes{} }）、collectionScope、queryText、language、crossLanguages、keyword、metaDataFilter、retrievalProfileId、filters、includeDeprecated、maxContextTokens、debugLevel
- `KnowledgeContext`：queryId、principalContext、indexVersionUsed、collectionPlansUsed、resultChunks[]（含 content/score/sourceStage/whySelected/sectionPath/pageSpans）、groupedSources、citations、tokenBudgetUsed、retrievalDebug（含 debugRef、packing 信息）
- `CollectionRetrievalPlan`：由 CollectionRetrievalPlanBuilder 请求时构建，含 activeIndexVersionId、opensearchIndex、qdrantCollection、embeddingModel、profileSnapshot、allowedDocIds、lifecycleFilter 等
- `IndexedChunk`：chunk_registry 解析出来的 chunk 记录，含 displayText、vectorText、publishedDocumentState、visibility、allowedPrincipalIds、allowedGroups、citationPayload、metadata
- `RetrievalScope`：合并后的检索范围（principalId + collections + allowedDocIds + metadataFilters + permissionFingerprint）

## PermissionPrefilter 过滤链（顺序固定）
```
1. collection_id 匹配
2. published_document_state 在 allowed_states 中（默认 ["PUBLISHED"]）
3. final_doc_id 在 allowedDocIds 中
4. principalId ∈ allowedPrincipalIds || 任意 group ∈ principal_groups ∩ allowedGroups
5. visibility 匹配（如配置 filters.visibility）
```
**额外加固**：`RecallOrchestrator.executeRecall()` 在 fusion 前执行 `intersectWithPermitted`，将 backend hits 与 permitted chunks 做 chunkId 交集。permitted 集为空时 fusion 前直接返回空。

## Cache 分层

| 层 | Key 结构 | TTL | 说明 |
|----|----------|-----|------|
| Query Embedding | `{prefix}:qemb:v1:{sha256(query+model+client+baseUrlFP)}` | 86400s | 空/null 结果不缓存 |
| Recall Candidates | `{prefix}:recall:v1:{sha256(plan fingerprint)}` | 60s | 含 principal/groups/collections/activeIndexVersions/profileHashes/embeddingModels/allowedDocIdsHash/metadataFiltersHash/lifecycleFilterHash/includeDeprecated/topK |

- `provider = noop`（默认）或 `redis`
- `keyPrefix = reality-rag:retrieval`
- `requireRedis=false` → Redis 故障时自动 fail-open
- Cache purge 按 `{prefix}:*` 做前缀匹配删除，非精确按 tenant/collection/doc/evidence
- 不缓存 final KnowledgeContext

## strict mode 行为矩阵（require-live-backends=true）

| 组件 | Normal（未配置/失败） | Strict（未配置/失败） |
|------|----------------------|----------------------|
| OpenSearch recall | fallback 到 stub，WARN | IllegalStateException |
| Qdrant recall | fallback 到 stub，WARN | IllegalStateException |
| Embedding | 返回 empty list，WARN | IllegalStateException |
| Rerank | fallback 到 heuristic，WARN | IllegalStateException |
| Prompt strategies | 返回 empty / 跳过，无 WARN | 跳过（当前不抛） |

## Projection Sync

### Index Projection（来自 indexing）
- `POST /internal/index-projections/sync` — 带 `idempotencyKey`
- `full_replace` 模式：upsert index_versions + index_registry + published_documents → DELETE + INSERT chunk_registry
- `lifecycle_patch` 模式：UPDATE chunk_registry.available_int + payload_json.published_document_state
- 幂等表：`index_projection_idempotency`（自动创建）

### Profile Projection（来自 admin）
- `POST /internal/retrieval-profile-projections/sync` — 带 `idempotencyKey`
- upsert retrieval_profiles 表
- FileProjection 变体返回 `UnsupportedOperationException` → 501

## RetrievalProfile 校验规则（RetrievalProfileValidator）
| 字段 | 规则 |
|------|------|
| bm25_weight + vector_weight | 必须 = 1.0，各在 0.0~1.0 |
| candidate_top_k | > 0 且 ≤ 1000 |
| pack_budget | > 0；> 100000 时 warning |
| similarity_threshold | 0.0~1.0；>0.9 或 <0.1 时 warning |
| rerank_enabled | 必填，必须是 boolean |
| rerank_model | 必填，须在 {default, none, bge-reranker-v2-m3, rerank-v1, rerank-multilingual-v1.0} |
| fail_policy | 必填，须在 {fail_open, fail_closed} |
| expansion_policy | 可选；type 须在 {neighbor, breadcrumb, none} |
| rerank_enabled=true + rerank_model=none | warning |

## RerankService 精排细节（620 行）
- **Rerank document** = breadcrumb（section_path > 拼接） + display text 命中片段
- **Token weighting**: title_tks × 2 / important_kwd × 5 / question_tks × 6
- **Rank feature boost**: pagerank + tag_fea（query 与 chunk 特征余弦）
- **Live rerank**: 调用 SiliconFlow API，model = `rerank-v1` / `bge-reranker-v2-m3`
- **Heuristic fallback**: `tokenWeight × tokenSimilarity + vectorWeight × recallScore + rankFeatureBoost`
- **Rerank window**: 取 min(candidateTopK, ragflowRerankWindowMax(64))，再 cap 到 fusedTopM(60)

## QueryPreparationService 预处理
- **Metadata filter 解析**: manual（8 种操作符）、auto/semi_auto（依赖 prompt → `meta_filter.md` 模板）
- **Cross-languages**: 模板 `cross_languages_sys_prompt.md` + `cross_languages_user_prompt.md`
- **Keyword extraction**: 模板 `keyword_prompt.md` → 提取 topN 关键词追加到 queryText
- 所有 prompt 降级安全：未配置时跳过，不虚构条件

## ChunkExpander 扩展
- **Neighbor**: 按 chunk_id 后缀序号 ± neighborHops(2)，decay=0.8
- **Breadcrumb**: 按 section_path 前缀分组，同一前缀取 limit(3)，decay=0.7

## ChunkAggregationService 聚合
- **TOC**: 选总分最高的 doc 作 anchor → 读取 `indexed_documents.outline` → token 匹配或 LLM 选择（`toc_relevance_system.md` + `toc_relevance_user.md`）→ boost/追加 linked_chunk_ids → tocTopN(6) 截断
- **Children**: 读取 `metadata.mom_id` → 归并子 chunk 到父 chunk，取子平均分

## Trace 落库（JdbcRetrievalTraceRecorder）
- `run_trace_id = "retrieval_" + queryId`，upsert 语义
- `run_steps` 记录 `retrieval.response` 或 `retrieval.failure`
- 记录 query_id、trace_id、principal_id、collection_scope、index_versions、allowed_doc_ids、chunk_ids、source_stages、debug_ref

## 约束
- 所有配置前缀 `retrieval.*`
- 检索端口 18082（`server.port`）
- cache 默认 `provider: noop`（不依赖 Redis）
- 所有 JSON 使用 `SNAKE_CASE` + `non_null`
- prompt 模板位于 `src/main/resources/prompts/`（共 6 个模板）
- 修改接口字段时必须同步更新 `AGENTS.md` 和 `api.md`
- 跨模块新功能（如新增 projection sync 类型、修改 KnowledgeContext）必须先统一接口描述再实现
