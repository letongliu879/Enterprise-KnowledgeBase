# retrieval 对外接口契约

## Inbound（retrieval 接收的请求）

### POST /internal/retrieve — 执行检索（入口）
`RetrieveRequest`（snake_case JSON）:
```
query_id              string (必填)
trace_id              string (必填)
principal             PrincipalRef (必填) — { user_id, role_ids[], group_ids[], attributes{} }
collection_scope      string[] (必填)
query                 string (必填)
language              string (可选)
cross_languages       string[] (可选)
keyword               bool (可选, 默认 false)
meta_data_filter      object (可选)       — { method: "manual"|"auto"|"semi_auto", manual: [{key,value,op}], logic: "and"|"or", ... }
retrieval_profile_id  string (必填)
filters               object (可选)       — 会并入 metadataFilters，额外含 principal_groups / embedding_model_groups
include_deprecated    bool (默认 false)
token_budget          int (可选, 正数)     — max_context_tokens
debug_level           string (默认 "none")
```
返回 `KnowledgeContext`

### KnowledgeContext（响应体）
```
query_id               string
principal_context      { principal_id, permission_fingerprint }
index_version_used     string[]
collection_plans_used  CollectionRetrievalPlan[]
evidence_items         ResultChunk[]
grouped_sources        [{ collection_id, final_doc_id }]
citations              object[]
token_budget_used      int
retrieval_debug        { debug_level, debug_ref, packing: { max_segments_per_file, max_total_chars } }
```

### ResultChunk
```
collection_id                  string
doc_id                         string (final_doc_id)
evidence_id                    string (chunk_id)
document_index_revision_id     string
content                        string (display_text)
section_path                   string[]
page_spans                     [{ page_from, page_to }]
score                          double (0.0~1.0)
source_stage                   string — hybrid_fusion / rerank_heuristic / rerank_live /
                                       neighbor_expand / breadcrumb_expand /
                                       ragflow_toc_aggregate / ragflow_children_aggregate
why_selected                   string
```

### GET /health — 健康检查
返回 `{ "service": "retrieval", "status": "ok" }`

### GET /internal/retrieval-profiles/{profileId} — 查询 RetrievalProfile
返回 `RetrievalProfile`（profileId、collectionId、profileVersion、profileHash、bm25Weight、vectorWeight、candidateTopK、similarityThreshold、rerankEnabled、rerankModel、failPolicy、expansionPolicy、packBudget、updatedAt、updatedBy）
404 = 不存在

### POST /internal/retrieval-profiles/validate — 校验 RetrievalProfile 配置
`RetrievalProfileValidateRequest`:
```
retrieval_profile_id  string (必填)
profile_config        object (必填)   — 待校验的配置 map
tenant_id             string (必填)
collection_id         string (可选)
version               string (可选)
```
返回 `RetrievalProfileValidateResponse`:
```
valid                 bool
canonical_config      object (valid=true 时有, key 顺序固定)
profile_hash          string          — "sha256:..." 或 valid=false 时占位值
warnings              string[]
errors                ValidationError[]  — [{ code, message }]
runtime_owner         "retrieval"
validator_version     "1.0.0"
```
校验规则见 `RetrievalProfileValidator`（9 项校验）。

### POST /internal/retrieval-profile-projections/sync — 接收 admin 投影同步
`RetrievalProfileProjectionSyncRequest`:
```
command_id            string (必填)
trace_id              string (必填)
idempotency_key       string (必填)
actor                 string (必填)
tenant_id             string (必填)
target_type           string (必填)
target_id             string (必填)
payload               RetrievalProfileProjection (必填)
  profile_id          string (必填)
  collection_id       string (可选)
  profile_version     int (必填)
  profile_hash        string (必填)
  bm25_weight         double (必填)
  vector_weight       double (必填)
  candidate_top_k     int (必填)
  similarity_threshold double (必填)
  rerank_enabled      bool (必填)
  rerank_model        string (必填)
  fail_policy         string (必填)
  expansion_policy    object (可选)
  pack_budget         int (必填)
  enabled             bool (必填)
  updated_at          string (可选, ISO 8601)
  updated_by          string (必填)
```
返回 `{ synced_at: string, accepted: bool }`
- 200: 成功 upsert（profile 写入 retrieval_profiles 表）
- 501: FileProjection 模式不支持
- 400: 其他错误

### POST /internal/index-projections/sync — 接收 indexing 投影同步
`IndexProjectionSyncRequest`:
```
command_id            string (必填)
trace_id              string (必填)
idempotency_key       string (必填)
actor                 string (必填)
tenant_id             string (必填)
target_type           string (必填)
target_id             string (必填)
payload               IndexProjectionPayload (必填)
  collection_id       string (必填)
  index_version_id    string (必填)
  sync_mode           string (必填)     — "full_replace" | "lifecycle_patch"
  doc_id              string (lifecycle_patch 必填)
  lifecycle_state     string (可选)      — lifecycle_patch 时更新 published_document_state
  available_int       int (可选)         — lifecycle_patch 时更新; null 时根据 lifecycleState 推导
  tenant_id           string (可选)
  opensearch_index    string (可选)
  qdrant_collection   string (可选)
  embedding_model     string (可选)
  chunk_profile_id    string (可选)
  index_profile_id    string (可选)
  schema_version      string (可选)
  published_document_state string (可选)
  chunks              object[] (可选)    — full_replace 时全量 chunk 列表
    chunk_id                    string (必填)
    tenant_id                   string
    doc_id                      string (= final_doc_id)
    document_index_revision_id  string
    chunk_type                  string (默认 "text")
    display_text                string
    vector_text                 string
    section_path                string[]
    page_spans                  [{ page_from, page_to }]
    source_block_ids            string[]
    keyword_terms               string[]
    confirmed_tags              string[]
    visibility                  string (默认 "internal")
    published_document_state    string (默认 "PUBLISHED")
    access_control              { allowed_principal_ids[], allowed_groups[] }
    citation_payload            object
    lexical_payload             object
    vector_payload              object
    metadata                    object（含 doc_metadata, title_tks, important_kwd,
                                       question_tks, mom_id, pagerank, tag_fea 等）
    chunk_hash                  string
    available_int               int (默认 1)
```
返回 `{ synced_at: string, chunks_synced: int, chunks_removed: int }`
- 幂等（idempotencyKey → `index_projection_idempotency` 表）
- `full_replace`: DELETE + INSERT chunk_registry，upsert index_versions + index_registry + published_documents
- `lifecycle_patch`: UPDATE chunk_registry.available_int，遍历更新 payload_json.published_document_state
- 400 = BAD_REQUEST（DataAccessException）

### POST /internal/cache/purge — 清理检索缓存（来自 indexing）
`CachePurgeRequest`:
```
tenant_id       string (必填)
collection_id   string (可选)
doc_id          string (可选)
evidence_id     string (可选)
```
返回 `CachePurgeResponse`:
```
purged_count    long           — 实际删除的 key 数（NoOp=0）
scope           object         — { tenant_id, collection_id?, doc_id?, evidence_id? }
```
实现：前缀匹配删除 `{keyPrefix}:*`，scope 仅用于日志。provider=noop 时 purged_count 始终为 0。

## Outbound（retrieval 发出的请求）

| 方向 | 端点 | 说明 |
|------|------|------|
| → OpenSearch | POST `{opensearchBaseUrl}/{index}/_search` | BM25 检索（live recall 启用） |
| → Qdrant | POST `{qdrantBaseUrl}/collections/{collection}/points/search` | Dense vector 检索（live recall + live embedding 启用） |
| → Embedding API | POST `{embeddingBaseUrl}/embeddings` | Query 向量化（live embedding 启用） |
| → Rerank API | POST `{rerankerBaseUrl}` | 精排（live rerank 启用，Bearer token） |
| → Prompt LLM | POST `{promptBaseUrl}/chat/completions` | 跨语言翻译 / 关键词提取 / TOC LLM 选择 / auto metadata filter（Bearer token） |

## 配置一览（application.yaml）

### 服务
| 配置 | 默认值 | 说明 |
|------|--------|------|
| `server.port` | 18082 | |
| `spring.jackson.property-naming-strategy` | SNAKE_CASE | |
| `spring.jackson.default-property-inclusion` | non_null | |

### Backends（retrieval.backends.*）
| 配置 | 默认值 | 说明 |
|------|--------|------|
| `live-recall-enabled` | false | |
| `live-embedding-enabled` | false | |
| `embedding-base-url` | https://api.siliconflow.cn/v1 | |
| `embedding-model` | — | |
| `live-rerank-enabled` | false | |
| `reranker-base-url` | https://api.siliconflow.cn/v1/rerank | |
| `reranker-model` | — | |
| `live-prompt-strategies-enabled` | false | |
| `prompt-model-base-url` | — | |
| `prompt-model-name` | — | |
| `require-live-backends` | false | strict mode |

### Search Strategy（retrieval.search.*）
| 配置 | 默认值 | 说明 |
|------|--------|------|
| `fused-top-m` | 60 | recall 后截断进 rerank 的候选数 |
| `enable-rerank` | true | 全局 rerank 开关 |
| `rerank-top-n` | 10 | rerank 后保留 |
| `max-rerank-chars` | 1000 | rerank 文档最大字符 |
| `max-breadcrumb-chars` | 250 | breadcrumb 截断 |
| `head-ratio` | 0.67 | 文本截断头部占比 |
| `enable-ragflow-rerank-window` | true | |
| `ragflow-rerank-window-min` | 30 | |
| `ragflow-rerank-window-max` | 64 | |
| `enable-ragflow-token-weighting` | true | |
| `ragflow-title-token-weight` | 2 | |
| `ragflow-important-keyword-weight` | 5 | |
| `ragflow-question-token-weight` | 6 | |
| `enable-ragflow-rank-features` | true | pagerank + tag_fea |
| `enable-ragflow-keyword-extraction` | true | |
| `ragflow-keyword-top-n` | 3 | |
| `enable-ragflow-cross-languages` | true | |
| `enable-ragflow-metadata-auto-filter` | true | |
| `enable-ragflow-toc-aggregation` | true | |
| `enable-ragflow-toc-llm-selector` | true | |
| `ragflow-toc-top-n` | 6 | |
| `ragflow-toc-min-score` | 0.3 | |
| `enable-ragflow-children-aggregation` | true | mom_id 归并 |
| `enable-smart-top-k` | true | |
| `smart-top-score-ratio` | 0.5 | |
| `smart-top-score-delta-abs` | 0.25 | |
| `smart-min-score` | 0.25 | |
| `smart-min-k` | 2 | |
| `smart-max-k` | 8 | |
| `enable-neighbor-expansion` | true | |
| `neighbor-hops` | 2 | |
| `decay-neighbor` | 0.8 | |
| `enable-breadcrumb-expansion` | true | |
| `breadcrumb-expand-limit` | 3 | |
| `decay-breadcrumb` | 0.7 | |
| `max-segments-per-file` | 3 | 打包截断 |
| `max-total-chars` | 48000 | 打包截断 |

### Cache（retrieval.cache.*）
| 配置 | 默认值 | 说明 |
|------|--------|------|
| `enabled` | true | 总开关 |
| `provider` | noop | noop / redis |
| `redis-url` | redis://127.0.0.1:6379/0 | |
| `key-prefix` | reality-rag:retrieval | |
| `query-embedding-ttl-seconds` | 86400 | 24h |
| `recall-ttl-seconds` | 60 | 1min |
| `fail-open` | true | Redis 不可用时不阻断 |
| `require-redis` | false | true 时 Redis 不可用抛异常 |

## 数据库表

| 表 | 写入者 | 读取者 | Schema |
|----|--------|--------|--------|
| `retrieval_profiles` | admin (projection sync) | CollectionRetrievalPlanBuilder | profileId, collectionId, bm25Weight, vectorWeight, candidateTopK, ... |
| `published_documents` | indexing (projection sync) | CollectionRetrievalPlanBuilder, MetadataFilterService | finalDocId, collectionId, state, activeIndexVersion, ... |
| `index_registry` | indexing (projection sync) | CollectionRetrievalPlanBuilder | collectionId(PK), indexVersion, status |
| `index_versions` | indexing (projection sync) | CollectionRetrievalPlanBuilder | indexVersionId(PK), tenantId, collectionId, opensearchIndex, qdrantCollection, embeddingModel, chunkCount |
| `chunk_registry` | indexing (projection sync) | JdbcChunkRegistryKnowledgeStore | chunkId(PK), collectionId, finalDocId, indexVersionId, availableInt, visibility, payload_json(jsonb) |
| `indexed_documents` | indexing | JdbcDocumentTocSource（只读 outline） | outline字段用于TOC |
| `run_traces` | retrieval (JdbcRetrievalTraceRecorder) | 运维 | runTraceId(PK)=`retrieval_{queryId}`, traceId, principalId, queryId, indexVersionId, profileId, rootStatus, resultCount, extraJson |
| `run_steps` | retrieval (JdbcRetrievalTraceRecorder) | 运维 | traceId, stepName(`retrieval.response`/`retrieval.failure`), status, summary, detailsJson |
| `index_projection_idempotency` | retrieval（幂等控制，自动创建） | retrieval | idempotencyKey(PK), processedAt |

## 关键数据模型

### RetrievalProfile canoncial_config 输出顺序
```
bm25_weight, vector_weight, candidate_top_k, similarity_threshold,
rerank_enabled, rerank_model, fail_policy, expansion_policy, pack_budget
```

### IndexedChunk 权限控制字段
- `access_control.allowed_principal_ids[]` — 有权限的 principal
- `access_control.allowed_groups[]` — 有权限的 group
- 两者都为空时视为公开（所有 principal 可访问）
- `visibility` — "internal"（默认）、"public" 等

### Payload_json 中 MetadataFilterService 用到的字段
- `metadata.title_tks / important_kwd / question_tks` — rerank token weighting
- `metadata.mom_id` — children aggregation（parent chunk ID）
- `metadata.pagerank / pagerank_fea` — rank feature boost
- `metadata.tag_fea / tag_feas` — rank feature boost（{tag: score} map）
- `metadata.doc_metadata.*` — metadata filter（扁平化索引）

## Prompt Templates（src/main/resources/prompts/）
| 模板 | 用途 |
|------|------|
| `cross_languages_sys_prompt.md` | 跨语言翻译 system prompt |
| `cross_languages_user_prompt.md` | 跨语言翻译 user prompt（含 {{ query }}, {{ languages }}） |
| `keyword_prompt.md` | 关键词提取（含 {{ content }}, {{ topn }}） |
| `meta_filter.md` | 自动 metadata filter 生成（含 {{ current_date }}, {{ metadata_keys }}, {{ user_question }}, {{ constraints }}） |
| `toc_relevance_system.md` | TOC LLM 选择 system prompt |
| `toc_relevance_user.md` | TOC LLM 选择 user prompt（含 {{ query }}, {{ toc_json }}） |

## MetadataFilter 手动模式支持的操作符
`=`, `==`, `!=`, `≠`, `contains`, `not contains`, `in`, `not in`, `start with`, `end with`

## 错误码
| 场景 | HTTP | 说明 |
|------|------|------|
| 缺 profile | 400 | "Missing retrieval profile" |
| 缺 active index | 400 | "Missing active index for collection" |
| Cache purge fail | — | fail-open，仅 WARN |
| strict mode backend 失败 | 500 | IllegalStateException |
| RetrievalProfile 不存在 | 404 | |
| Profile projection UnsupportedOperationException | 501 | FileProjection 测试替身 |
| Index projection DataAccessException | 400 | BAD_REQUEST |
