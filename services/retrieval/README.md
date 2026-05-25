# Retrieval

`services/retrieval` 是 `Enterprise KnowledgeBase` 的 Java Spring Boot 内部检索服务。  
详细设计见 `retrieval.md`。

## 职责

`retrieval` 负责：

1. 解析 principal scope
2. 为每个 collection 构建 `CollectionRetrievalPlan`
3. 执行权限过滤与生命周期过滤
4. 执行 query 预处理
5. 执行 hybrid recall
6. 执行 fusion、rerank、smart cutoff
7. 执行 E1 / E2 上下文扩展
8. 执行 RAGFlow 风格的 TOC 聚合与 child 聚合
9. 执行 context pack，输出 `KnowledgeContext`
10. 生成 retrieval trace / debug ref

`retrieval` 不负责：

- 对外 API / MCP 入口
- 文档审批与发布
- chunking / embedding 产出
- 索引写入

## 当前主链

当前链路顺序：

`metadata filter -> cross_languages -> keyword extraction -> hybrid recall -> fusion -> rerank -> smart cutoff -> E1/E2 expand -> ragflow toc aggregate -> ragflow children aggregate -> pack`

其中：

- `ContextWeaver`
  - smart cutoff
  - E1 neighbor expansion
  - E2 breadcrumb expansion
  - context pack

- `RAGFlow`
  - metadata filter
  - cross_languages
  - keyword extraction
  - rerank window
  - token weighting
  - rank feature scoring
  - retrieval_by_toc
  - retrieval_by_children

## 当前实现状态

已经落地的组件：

- `/internal/retrieve`
- `/internal/retrieval-profiles/{id}`
- `/health`
- scope / plan builder
- permission / lifecycle prefilter
- `recall/backends/OpenSearchRecaller`
- `recall/backends/QdrantRecaller`
- `fusion/HybridFusionService`
- `preprocess/QueryPreparationService`
- `preprocess/MetadataFilterService`
- `prompt/PromptModelClient`
- `rerank/RerankService`
- `cutoff/SmartTopKCutoffService`
- `expansion/NeighborChunkExpander`
- `expansion/BreadcrumbChunkExpander`
- `ragflow/RagflowTocAggregationService`
- `ragflow/RagflowChildrenAggregationService`
- `packing/KnowledgeContextPacker`

## 请求契约

`RetrieveRequest` 当前已经支持这些 RAGFlow 风格字段：

- `cross_languages`
- `keyword`
- `meta_data_filter`

说明：

- `meta_data_filter` 名字保持和 RAGFlow 一致，不改成别的写法
- 没配 live prompt model 时，`cross_languages` / `keyword` / `auto|semi_auto` metadata filter 会安全降级
- `manual` metadata filter 不依赖 LLM，当前已经生效

## 数据入口

当前支持两类数据入口：

1. `in-memory`
2. `projection file`

当前 file-backed 输入包括：

- `published_documents`
- `index_registry`
- `retrieval_profiles`
- `indexed_chunks`
- `document_toc`

其中：

- `indexed_chunks` 除了基础字段，还支持 `metadata`
- `metadata` 当前已经承载：
  - `title_tks`
  - `important_kwd`
  - `question_tks`
  - `tag_fea`
  - `pagerank`
  - `mom_id`
  - `doc_metadata`

相关文档：

- `document_toc` 契约见 [toc-contract.md](./toc-contract.md)
- query 预处理策略见 [ragflow-query-strategies.md](./ragflow-query-strategies.md)

## 开关放哪

所有开关统一放在：

- `services/retrieval/src/main/resources/application.yaml`

分三组：

- 后端联调开关：`retrieval.backends.*`
- 数据文件配置：`retrieval.data.*`
- 检索策略开关：`retrieval.search.*`

### 后端联调开关

默认关闭：

- `retrieval.backends.live-recall-enabled=false`
- `retrieval.backends.live-rerank-enabled=false`
- `retrieval.backends.live-prompt-strategies-enabled=false`

相关配置：

- `retrieval.backends.opensearch-base-url`
- `retrieval.backends.qdrant-base-url`
- `retrieval.backends.reranker-base-url`
- `retrieval.backends.reranker-api-key`
- `retrieval.backends.prompt-model-base-url`
- `retrieval.backends.prompt-model-api-key`
- `retrieval.backends.prompt-model-name`

### 数据文件配置

- `retrieval.data.published-documents-file`
- `retrieval.data.index-registry-file`
- `retrieval.data.retrieval-profiles-file`
- `retrieval.data.indexed-chunks-file`
- `retrieval.data.document-toc-file`

### 策略开关

默认开启：

- `retrieval.search.enable-rerank=true`
- `retrieval.search.enable-ragflow-keyword-extraction=true`
- `retrieval.search.enable-ragflow-cross-languages=true`
- `retrieval.search.enable-ragflow-metadata-auto-filter=true`
- `retrieval.search.enable-ragflow-rerank-window=true`
- `retrieval.search.enable-ragflow-token-weighting=true`
- `retrieval.search.enable-ragflow-rank-features=true`
- `retrieval.search.enable-ragflow-toc-aggregation=true`
- `retrieval.search.enable-ragflow-toc-llm-selector=true`
- `retrieval.search.enable-ragflow-children-aggregation=true`
- `retrieval.search.enable-smart-top-k=true`
- `retrieval.search.enable-neighbor-expansion=true`
- `retrieval.search.enable-breadcrumb-expansion=true`

### 当前默认参数

- `retrieval.search.ragflow-keyword-top-n=3`
- `retrieval.search.ragflow-rerank-window-min=30`
- `retrieval.search.ragflow-rerank-window-max=64`
- `retrieval.search.ragflow-title-token-weight=2`
- `retrieval.search.ragflow-important-keyword-weight=5`
- `retrieval.search.ragflow-question-token-weight=6`
- `retrieval.search.ragflow-toc-top-n=6`
- `retrieval.search.ragflow-toc-min-score=0.3`

## 当前边界

已经接上的：

- manual `meta_data_filter`
- `cross_languages` 入口
- `keyword extraction` 入口
- TOC projection 契约
- TOC 主链顺序
- TOC LLM selector 入口

还没完全贴齐原版的地方：

- `cross_languages`
  - 当前需要 live prompt model 才会真的执行翻译
- `keyword extraction`
  - 当前需要 live prompt model 才会真的生成关键词
- `meta_data_filter.auto / semi_auto`
  - 当前需要 live prompt model 才会真的让 LLM 生成条件
- `retrieval_by_toc`
  - 当前已经有 LLM selector 入口
  - 没配 live prompt model 时退回本地 overlap selector

也就是说：

- 顺序、契约、开关已经补了
- 无 LLM 环境下不会乱造假策略
- 配好 prompt model 后，这几项会走真正的 prompt 驱动逻辑

## 验证状态

本地已通过：

- `mvn test`

当前测试覆盖包括：

- 默认 in-memory 模式
- projection-file 模式
- rerank 默认开启链路
- rerank 开关关闭链路
- manual `meta_data_filter`
- `RAGFlow` token weighting
- `RAGFlow` rank feature scoring
- `RAGFlow` TOC aggregation
- `RAGFlow` TOC aggregation 开关关闭
- `RAGFlow` child aggregation
- neighbor expansion
- breadcrumb expansion
- retrieval profile 查询接口
