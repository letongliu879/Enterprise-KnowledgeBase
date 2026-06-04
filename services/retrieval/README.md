# retrieval

`services/retrieval` 是当前知识库的内部检索服务，基于 Spring Boot 3.5.14 + Java 17。

详细设计见 [retrieval.md](./retrieval.md)。

## 核心职责

- 根据 `collection_scope` 构建检索计划
- 从数据库读取 profile、发布事实、活动索引、chunk、TOC
- 执行 query 预处理（含跨语言、关键词提取、metadata filter）
- 执行 hybrid recall、rerank、cutoff、扩展、聚合与 context pack
- 返回 `KnowledgeContext`
- 把检索 trace 写入 `run_traces`、`run_steps`
- **两层 read-path 缓存**：query embedding cache（省外部 embedding 调用）+ recall candidate cache（省 OpenSearch/Qdrant 召回）

以下职责**不属于** retrieval：

- 对外 REST / MCP 接入
- API key 鉴权
- 文档入库、发布审批、索引写入
- 最终大模型回答生成

## 技术栈

- Spring Boot 3.5.14
- Java 17
- Maven（`pom.xml` 定义依赖）
- JDBC（PostgreSQL 生产，SQLite / H2 测试）
- spring-boot-starter-data-redis（缓存可选）

## 构建和测试

```bash
# 在 services/retrieval 目录下
mvn test

# 或运行主应用
mvn spring-boot:run
```

测试分为两类：
- **DB-backed 测试**：使用 H2 内存数据库验证全链路（`DbBackedRuntimeRetrieveControllerTest` 等）
- **File projection 测试**：使用本地 JSON fixture 验证特定场景（`FileProjectionRetrieveControllerTest` 等）

## 当前服务面

对外：

- `GET /health` — 健康检查
- `POST /internal/retrieve` — 主检索接口
- `GET /internal/retrieval-profiles/{profileId}` — 读取指定 profile
- `POST /internal/retrieval-profiles/validate` — RetrievalProfile 运行时校验与 canonicalize
  - 输入：`retrieval_profile_id`, `profile_config`
  - 校验：weight 范围、top_k > 0、pack_budget > 0、rerank_model 支持、expansion_policy 有效、fail_policy 有效、similarity_threshold 范围、rerank_enabled 一致性
  - 输出：`valid`, `canonical_config`, `profile_hash`, `warnings`, `errors`, `runtime_owner` (= "retrieval"), `validator_version`
  - 无副作用：不写 admin 表、不修改 retrieval cache、不改变 active runtime profile
  - 边界：retrieval 只校验 runtime 可执行性，不做 admin 控制面校验；admin 发布前调用此接口
- `POST /internal/cache/purge` — 按前缀清理检索缓存

内部（admin → retrieval projection sync）：

- `POST /internal/retrieval-profile-projections/sync` — 接收 admin 推送的 retrieval profile 投影

内部（indexing → retrieval projection sync）：

- `POST /internal/index-projections/sync` — 接收 indexing 推送的 index version、index registry、published document、chunk 投影

内部（可观测性）：

- `management.endpoints.web.exposure.include=health,info` — Actuator 端点

## 重要约束

`published_documents` 现在是检索可见性的真相源之一。

如果某个 collection 有 chunk、有 active index，但没有对应的 `published_documents` 记录，那么当前实现会返回空结果，而不是"放行全部 chunk"。
