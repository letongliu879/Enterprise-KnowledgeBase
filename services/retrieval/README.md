# retrieval

`services/retrieval` 是当前知识库的内部检索服务，基于 Spring Boot。

详细设计见 [retrieval.md](./retrieval.md)。

## 核心职责

- 根据 `collection_scope` 构建检索计划
- 从数据库读取 profile、发布事实、活动索引、chunk、TOC
- 执行 query 预处理
- 执行 hybrid recall、rerank、cutoff、扩展、聚合与 context pack
- 返回 `KnowledgeContext`
- 把检索 trace 写入 `run_traces`、`run_steps`
- **两层 read-path 缓存**：query embedding cache（省外部 embedding 调用）+ recall candidate cache（省 OpenSearch/Qdrant 召回）

以下职责**不属于** retrieval：

- 对外 REST / MCP 接入
- API key 鉴权
- 文档入库、发布审批、索引写入
- 最终大模型回答生成

## 当前服务面

对外：

- `GET /health`
- `POST /internal/retrieve`
- `GET /internal/retrieval-profiles/{profileId}`
- `POST /internal/retrieval-profiles/validate` — RetrievalProfile 运行时校验与 canonicalize

内部（admin → retrieval projection sync）：

- `POST /internal/retrieval-profile-projections/sync` — 接收 admin 推送的 retrieval profile 投影

内部（indexing → retrieval projection sync）：

- `POST /internal/index-projections/sync` — 接收 indexing 推送的 index version、index registry、published document、chunk 投影
  - 输入：`retrieval_profile_id`, `profile_config`, `tenant_id`, `collection_id` (optional), `version` (optional)
  - 校验：weight 范围、top_k > 0、pack_budget > 0、rerank_model 支持、expansion_policy 有效、fail_policy 有效、similarity_threshold 范围、rerank 一致性
  - 输出：`valid`, `canonical_config`, `profile_hash`, `warnings`, `errors`, `runtime_owner` (= "retrieval"), `validator_version`
  - 无副作用：不写 admin 表、不修改 retrieval cache、不改变 active runtime profile
  - 边界：retrieval 只校验 runtime 可执行性，不做 admin 控制面校验；admin 发布前调用此接口

## 重要约束

`published_documents` 现在是检索可见性的真相源之一。

如果某个 collection 有 chunk、有 active index，但没有对应的 `published_documents` 记录，那么当前实现会返回空结果，而不是"放行全部 chunk"。
