# retrieval 权限感知混合检索核心设计

## 1. 定位

`retrieval` 是 `Enterprise KnowledgeBase` 的 Java 在线检索核心，负责全链路中的在线检索阶段：

1. 权限过滤
2. 多路召回
3. 融合排序
4. rerank 精排
5. 上下文包装
6. 返回 `KnowledgeContext`

它不暴露外部 REST/MCP 协议，不处理文件摄入，不写索引。它只接收 `access` 传入的受控检索请求，返回权限感知、可引用、可审计的 `KnowledgeContext`。

在本项目中，`retrieval` 延续 `Reality-RAG` 的服务职责与边界，但上游接入原则已经变化：

- 不再以“移植上游能力”为目标叙事
- `retrieval` 仍然是 Java 主链实现
- RAGFlow 与 ContextWeaver 都可以影响检索参数模型、方法链、调试契约与上下文工程方式
- RAGFlow 不能成为在线检索的权限真相源或产品边界宿主

## 1.1 当前实现状态（截至 2026-05-24）

截至当前仓库状态，`services/retrieval` 已经在本仓库落地为一个可运行的 Java Spring Boot 内部服务。

当前已可见的内容包括：

- controller 与 health endpoint
- scope / plan builder
- file projection 数据源
- OpenSearch / Qdrant recaller
- RAGFlow 风格 query 预处理、TOC 聚合、children 聚合
- rerank、cutoff、expand、pack
- 一组围绕主链行为的测试

这意味着：

- 本文既是 retrieval 目标边界文档，也是当前实现说明文档
- 当前代码还不是最终完态，但已经不是纯设计占位
- access、admin、eval、trace 等后续模块应同时以本文和现有代码为准，而不是再回退到旧仓库文档口径

已存在并可直接作为 retrieval 契约输入的内容包括：

- `contracts/schemas/RetrieveRequest.schema.json`
- `contracts/schemas/CollectionRetrievalPlan.schema.json`
- `contracts/schemas/KnowledgeContext.schema.json`
- `contracts/openapi/retrieval-internal.yaml`

## 2. 核心设计决策

### 2.1 权限先于检索

`retrieval` 必须先生成 `RetrievalScope` 和 `CollectionRetrievalPlan[]`，再执行 OpenSearch / Qdrant 查询。

任何召回、扩展、融合、打包阶段都不得绕过权限范围。

生命周期过滤与权限过滤同级。默认只返回 `PUBLISHED` 文档；`DEPRECATED` 只有在请求显式授权包含时才允许进入最终输出；`ARCHIVED`、`RETRACTED` 和未恢复原状态的 `REINDEXING` 不得进入 recall、fusion、rerank、expansion、pack 的最终结果。

补充约束：

- chunk 是文档派生产物，不拥有独立 ACL
- 检索授权始终围绕 `final_doc_id`、`collection_id` 和发布状态执行
- 检索权限模型绝不能围绕 RAGFlow 的 `dataset/file` 标识执行

### 2.2 hybrid recall 是主线

基础召回固定为：

- OpenSearch BM25 / lexical recall
- Qdrant dense vector recall

其他召回方式只能作为增强，不能替代 hybrid 主线。

### 2.3 Java 主链自有，RAGFlow 只借机制，不借宿主

本项目的 retrieval 依然以 Java 主体实现为准。

RAGFlow 对 retrieval 的价值主要体现在：

- 检索参数模型
- query normalization 思路
- hybrid retrieval 方法链
- fusion / rerank 的调试与观测契约
- 检索工作台的观察与调参方式

但以下内容不进入 retrieval 主链宿主语义：

- RAGFlow 的 Python / Go 检索运行时
- RAGFlow 的 dataset/file 权限模型
- RAGFlow 的 chat/search/agent 产品边界

如果后续引入上游机制，优先顺序应是：

1. 保留本平台契约与服务边界
2. 吸收参数模型、方法链和调试契约
3. 仅在少数高价值且短期无法本地等价承接的模块上考虑 sidecar

### 2.4 ContextWeaver：借上下文工程机制，不借代码仓库语义

本项目的 retrieval 仍然需要吸收 ContextWeaver 的上下文工程能力，重点包括：

- smart cutoff
- adjacent expansion
- section expansion
- token budget context pack

这些能力进入 retrieval 的方式应是：

- 吸收行为语义、触发条件、预算规则和打包思路
- 适配到本平台的 `RetrieveRequest`、`CollectionRetrievalPlan`、`KnowledgeContext` 契约
- 保持 Java 主链实现主导

明确不借的部分包括：

- AST / import graph 代码语义
- 面向代码仓库的 chunk 关系假设
- LanceDB / FTS / SQLite 存储层

### 2.5 RAGFlow 与 ContextWeaver 的组合关系

在 retrieval 侧，两者的作用不同：

- RAGFlow 更偏检索方法链、query normalization、hybrid recall、fusion、rerank 参数化
- ContextWeaver 更偏上下文工程、cutoff、expand、pack

因此 retrieval 的目标不是“选一个上游站队”，而是：

- 用本平台的治理与契约托住边界
- 吸收 RAGFlow 的检索机制
- 吸收 ContextWeaver 的上下文工程机制
- 在 Java 主链里收敛成统一实现

### 2.6 active index 真相必须双源解析

`retrieval` 解析 active index 时必须同时读取两个事实源：

- publishing domain 的 `published_documents` 或其受控只读投影
- indexing registry

各自职责：

- publishing domain 决定文档是否可检索、当前文档绑定的 `active_index_version`、`published_document_state`、visibility、confirmed tags
- indexing registry 决定 `index_version_id` 对应的 OpenSearch index、Qdrant collection、embedding model、schema/chunk profile

规则：

- 文档可见性只信 publishing domain，不从 `IndexReady` 本地缓存推断
- 物理索引位置只信 indexing registry，不从 intake 表或 workbench 元数据硬编码
- `IndexReady` 只能作为缓存刷新信号，不能单独让文档对检索可见
- `DocumentLifecycleChanged` 必须使本地 scope/cache 失效
- 查询时若 publishing state 与 indexing registry 不一致，必须 fail-closed 或跳过该 document，并写 trace

### 2.7 `KnowledgeContext` 是证据上下文，不是最终答案

`retrieval` 的输出是 `KnowledgeContext`，不是最终回答。

因此：

- 它返回 evidence、citation、section path、debug 信息
- 它不拼接聊天回答
- 它不替代上层 LLM answer generation

这一点与现有 `packages/contracts/tests/test_retrieval_constraints.py` 的约束保持一致。

## 3. 边界

只负责：

- `RetrieveRequest` 执行
- principal scope 解析
- active index 与 document lifecycle 联合解析
- collection retrieval plan 生成
- permission prefilter
- OpenSearch recall
- Qdrant recall
- fusion
- rerank
- expansion
- context pack
- `KnowledgeContext`
- retrieval trace

不负责：

- 用户认证
- REST/MCP 对外暴露
- 文档审批
- chunking / embedding
- index write
- 管理 UI

## 4. 全局架构

```text
RetrieveRequest
      |
      v
┌────────────────────────────┐
│ RetrievalOrchestrator      │
└────────────┬───────────────┘
             v
┌────────────────────────────┐
│ ScopeResolver              │
│ - tenant                   │
│ - collection               │
│ - principal                │
│ - active index + lifecycle │
└────────────┬───────────────┘
             v
┌────────────────────────────┐
│ CollectionRetrievalPlan[]  │
│ - per collection profile   │
│ - index registry binding   │
│ - lifecycle filter         │
└────────────┬───────────────┘
             v
┌────────────────────────────┐
│ Permission/LifecycleFilter │
│ - allowed_doc_ids          │
│ - published state          │
│ - metadata filters         │
└────────────┬───────────────┘
             v
┌────────────────────────────┐
│ RecallOrchestrator         │
│ - lexical recall           │
│ - dense recall             │
│ - per model group recall   │
└────────────┬───────────────┘
             v
┌────────────────────────────┐
│ Fusion + Rerank            │
│ - per collection fusion    │
│ - cross collection merge   │
│ - rerank / cutoff          │
└────────────┬───────────────┘
             v
┌────────────────────────────┐
│ Expansion + ContextPacker  │
└────────────┬───────────────┘
             v
      KnowledgeContext
```

## 5. 目标模块分层

下列目录结构表达的是目标模块分层，不代表当前仓库已经具备这些实现。

```text
services/retrieval/
  pom.xml
  README.md
  retrieval.md
  src/main/java/.../contracts/
    RetrieveRequest.java
    RetrievalScope.java
    CollectionRetrievalPlan.java
    RecallCandidate.java
    FusedCandidate.java
    RankedEvidence.java
    KnowledgeContext.java
  src/main/java/.../scope/
    TenantScopeResolver.java
    CollectionScopeResolver.java
    IndexVersionResolver.java
    PublishedDocumentStateResolver.java
    CollectionRetrievalPlanBuilder.java
    PrincipalScopeResolver.java
  src/main/java/.../permission/
    PermissionPrefilter.java
    DocumentAccessPolicy.java
    LifecycleFilter.java
  src/main/java/.../recall/
    OpenSearchRecaller.java
    QdrantRecaller.java
    RecallOrchestrator.java
  src/main/java/.../embedding/
    QueryEmbeddingClient.java
    EmbeddingModelResolver.java
  src/main/java/.../fusion/
    RrfFusion.java
    WeightedFusion.java
    ScoreNormalizer.java
  src/main/java/.../rerank/
    RerankerClient.java
    RerankPolicy.java
  src/main/java/.../expansion/
    AdjacentChunkExpander.java
    SectionPathExpander.java
  src/main/java/.../packing/
    KnowledgeContextPacker.java
    TokenBudgetPolicy.java
  src/main/java/.../trace/
    RetrievalTraceRecorder.java
```

## 6. 核心契约

本节以当前仓库已存在的 `contracts/` 为准。

### 6.1 `RetrieveRequest`

当前 schema 位置：

- `contracts/schemas/RetrieveRequest.schema.json`

关键字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query_id` | string | 是 | 查询 ID |
| `trace_id` | string | 是 | 运行轨迹 ID |
| `tenant_id` | string | 是 | 租户 |
| `principal` | object | 是 | 用户/主体 |
| `collection_scope` | string[] | 是 | 查询 collection 范围 |
| `query_text` | string | 是 | 查询文本 |
| `language` | string | 否 | 查询语言 |
| `retrieval_profile_id` | string | 是 | 检索策略入口 key |
| `filters` | object | 否 | 元数据过滤 |
| `include_deprecated` | boolean | 否 | 默认 false |
| `max_context_tokens` | integer | 否 | 上下文预算 |
| `debug_level` | enum | 是 | `none/basic/full` |

规则：

- `retrieval_profile_id` 是入口 key，不是跨 collection 唯一执行 profile
- `trace_id` 必须跨 `access -> retrieval -> admin` 贯穿
- `debug_level` 决定返回多少 debug 信息，但不能突破权限边界

### 6.2 `CollectionRetrievalPlan`

当前 schema 位置：

- `contracts/schemas/CollectionRetrievalPlan.schema.json`

关键字段：

- `tenant_id`
- `collection_id`
- `active_index_version_id`
- `opensearch_index`
- `qdrant_collection`
- `embedding_model`
- `chunk_profile_id`
- `retrieval_profile_snapshot`
- `profile_id`
- `profile_version`
- `profile_hash`
- `permission_scope`
- `lifecycle_filter`
- `include_deprecated`
- `allowed_doc_ids`
- `metadata_filters`

规则：

- 每个 collection 必须生成独立 plan
- 多 collection 请求必须记录每个 plan 的 `profile_id/profile_version/profile_hash`
- embedding model 不兼容时，按 plan 分组执行 query embedding
- plan 缺少 active index 或 retrieval profile 时，该 collection 必须 fail-closed

### 6.3 `KnowledgeContext`

当前 schema 位置：

- `contracts/schemas/KnowledgeContext.schema.json`

顶层字段：

- `query_id`
- `tenant_id`
- `principal_context`
- `index_version_used`
- `collection_plans_used`
- `result_chunks`
- `grouped_sources`
- `citations`
- `token_budget_used`
- `retrieval_debug`

其中 `result_chunks` 至少包含：

- `collection_id`
- `final_doc_id`
- `chunk_id`
- `document_index_revision_id`
- `display_text`
- `section_path`
- `page_spans`
- `score`
- `source_stage`
- `why_selected`

约束：

- `KnowledgeContext` 只承载证据上下文，不承载最终答案
- 所有返回 chunk 必须可回溯到 `final_doc_id` 和 `document_index_revision_id`
- `retrieval_debug` 可以受控返回，但不得泄露越权中间产物

## 7. 关键流程

### 7.1 请求执行

1. 接收 `RetrieveRequest`
2. 解析 principal scope
3. 读取 collection 范围内的 publishing lifecycle 与 active index
4. 生成每个 collection 的 `CollectionRetrievalPlan`
5. 执行 permission/lifecycle prefilter
6. 按 plan 执行 lexical recall 与 dense recall
7. 执行 per-collection fusion 与 cross-collection merge
8. 视策略执行 rerank、cutoff、expansion
9. 执行 context pack，生成 `KnowledgeContext`
10. 写 retrieval trace 并返回

### 7.2 lifecycle 过滤

默认规则：

- `PUBLISHED`：允许进入检索
- `DEPRECATED`：默认过滤，仅在显式授权请求中允许
- `ARCHIVED`：禁止进入检索
- `RETRACTED`：禁止进入检索
- `REINDEXING`：未恢复原状态前禁止进入最终结果

### 7.3 active index 解析

查询前必须同时解析：

- 文档当前是否可见
- 文档绑定的 `active_index_version`
- `active_index_version` 对应的 OpenSearch/Qdrant 物理位置

这三项缺一不可；任一项不一致时必须 fail-closed 或跳过并写 trace。

## 8. 与其他服务的关系

### 8.1 与 `access`

`access` 负责：

- 对外 REST / MCP
- auth / rate limit / deadline
- 入口参数格式校验
- `retrieval_profile_id` 的选择或透传

`retrieval` 负责：

- 真正展开 per-collection retrieval plan
- 解析 profile snapshot
- 组合权限、召回、融合、精排、pack

### 8.2 与 `indexing`

`indexing` 负责：

- chunk 生成
- embedding 生成
- OpenSearch / Qdrant 写入
- index version 注册与切换

`retrieval` 负责消费它的结果，但不定义其内部 chunking / embedding schema 生成过程。

### 8.3 与 `intake-pipeline`

`intake-pipeline` 负责：

- 文档治理真相
- published document lifecycle
- `DocumentLifecycleChanged` 等事件

`retrieval` 必须以这些治理事实作为检索可见性前提。

### 8.4 与 `admin`

`admin` 负责：

- retrieval profile 管理
- trace 查询
- bad case / eval
- 运维观测

`retrieval` 负责产生可查询的 trace 与 debug_ref，但不承担管理界面职责。

## 9. 明确不做的事

- 不把 retrieval 做成外部 REST/MCP 服务
- 不直接访问工作台对象并把它们当成治理真相
- 不把 RAGFlow 检索运行时当成 Java 主链宿主
- 不把 `KnowledgeContext` 变成最终答案载体
- 不让 retrieval 自己写索引、改 lifecycle、改审批状态

## 10. 与本项目总体架构的关系

本文是 [docs/architecture.md](/E:/AI/My-Project/Enterprise%20KnowledgeBase/docs/architecture.md) 在 retrieval 侧的展开。

若与其他历史文档冲突，以本文和顶层架构文档为准；不再回退到旧仓库“上游能力移植”叙事。

## 11. 一句话

`retrieval` 是本项目的 Java 权限感知混合检索核心：治理真相来自平台，索引事实来自 indexing，RAGFlow 提供检索机制参考，ContextWeaver 提供上下文工程参考，二者都不进入权限真相与服务宿主边界。
