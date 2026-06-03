# Enterprise KnowledgeBase 总体架构

## 1. 项目定位

Enterprise KnowledgeBase 是面向企业知识治理、RAG 检索与 MCP 接入的知识平台。

它继承自 Reality-RAG 的核心服务架构与职责分工：

- 文档摄入、治理、发布、索引构建使用 Python
- 在线接入与在线检索使用 Java
- 跨服务契约集中定义
- 审计、可追溯、可回放、可治理是系统一等能力

与 Reality-RAG 的核心差异在于上游能力接入方式：

- 不再以上游能力移植为目标叙事
- 直接使用 RAGFlow 的文档解析、结构恢复、分块等模块作为运行时能力
- retrieval 侧继续借用 RAGFlow 与 ContextWeaver 的成熟检索/上下文工程机制
- RAGFlow 在本项目中是文档理解与分块工作台运行时，不是治理真相源

系统的基本立场不变：

- 文档治理真相属于本平台
- chunk 权限继承自文档治理结果
- 外部工作台对象（如 `dataset_id`、`file_id`）不替代本平台的 `collection_id`、`final_doc_id`

## 2. 目标模块地图

```text
contracts/
  schemas/           # 核心对象契约唯一来源
  events/            # 事件契约唯一来源
  openapi/           # REST / internal API 契约唯一来源

packages/
  contracts/         # Python 运行时契约包
  persistence/       # 持久化模型与仓储
  documents/         # 共享文档域逻辑

services/
  intake-pipeline/   # Python：摄入、治理、审批、发布、生命周期
  indexing/          # Python：基于 RAGFlow 的解析、分块、embedding、索引写入
  access/            # Java：外部查询入口，REST + MCP + 认证限流
  retrieval/         # Java：权限感知混合检索核心
  admin/             # Python：审计、评测、运行轨迹查询与运维控制面（目标，未落地）
  workbench-api/     # Python：面向解析/分块工作台的受控 API（目标，未稳定）

apps/
  admin-console/     # 管理、审核、追踪、工作台前端（目标，未落地）

upstream/
  ragflow/           # 作为解析/分块/工作台运行时基础的源码分叉
```

## 3. 全链路主线

目标全链路如下：

```text
文档进入
  -> 预解析与 ParseSnapshot
  -> 治理与审批
  -> 发布与索引激活
  -> 在线接入
  -> 权限感知检索
  -> 返回 KnowledgeContext
```

按模块拆开后：

| # | 阶段 | 责任模块 | 主要职责 |
|---|---|---|---|
| 1 | 文件进入 | services/intake-pipeline | 上传、去重、扫描、source file 登记 |
| 2 | 预解析 | services/indexing + upstream/ragflow | 文档理解、结构恢复、ParseSnapshot、chunk 预览 |
| 3 | 治理处理 | services/intake-pipeline | 编排处理阶段、风险检查、agent review、审批流 |
| 4 | 发布准备 | services/intake-pipeline | 生成最终文档身份、确认标签、生命周期事实、发布命令 |
| 5 | 正式分块与索引写入 | services/indexing | 复用 ParseSnapshot、chunk 生成、embedding、OpenSearch/Qdrant 写入、索引版本管理 |
| 6 | 外部查询接入 | services/access | REST、MCP、认证、请求翻译、trace 记录 |
| 7 | 检索执行 | services/retrieval | scope 解析、权限过滤、混合召回、融合、精排、上下文包装 |
| 8 | 审计与运维 | services/admin + apps/admin-console | 运行轨迹、评测、bad case、运维与审核界面（目标） |

## 4. 核心边界

### 4.1 contracts

contracts/ 是全系统唯一的跨服务契约源。

它定义：

- 核心对象 schema
- internal API seam
- 事件 schema
- trace / step / artifact 等运行轨迹对象

规则：

- Python 和 Java 不得各自维护漂移的独立契约真相
- 本地 mirrored DTO 只能作为运行时投影或兼容层
- 契约演进必须以 contracts/ 为起点

### 4.2 services/intake-pipeline

intake-pipeline 是企业级摄入控制面，负责：

- 原始文件接收
- source file 生命周期
- 各处理阶段的全局编排
- 风险审核与审批决策流程
- 已发布文档生命周期事实
- 发布命令与状态推进

以下职责**不属于** intake-pipeline：

- 最终的解析/分块运行时细节
- parser backend 所有权
- ParseSnapshot 真相
- embedding 生成
- 在线检索

它是文档治理真相的 owner。

补充约束：

- intake-pipeline 可以消费 ParseSnapshot 做审批、人工校验和工作台展示
- intake-pipeline 不再拥有正式 parser 输入语义
- intake-pipeline 产生的 markdown 或轻量转换文本只能作为治理辅助产物，不能成为 indexing 唯一正式解析入口

### 4.3 services/indexing

indexing 是文档理解与索引构建运行时，负责：

- 原始文件预解析
- ParseSnapshot 生成与版本化
- 面向索引的内容标准化
- 结构感知解析
- chunk 生成
- embedding 生成
- lexical / vector 索引记录生成
- index write / activate / rollback / revision 管理

以下职责**不属于** indexing：

- 审批决策
- 文档最终可见性决策
- 对外查询 API

关键设计立场：

- 直接复用 RAGFlow 的解析与分块模块
- parser/chunker 只有一个正式 owner，即 indexing
- 审批前内容预览来自 ParseSnapshot，而不是来自 intake-pipeline 自己维护的第二套解析产物
- 保留本平台自己的文档身份、治理、生命周期和发布模型

当前已实现：

- POST /internal/parse-previews — 接受 ParsePreview 请求
- POST /internal/index-jobs — 接受索引构建请求
- GET /internal/parse-snapshots/{id} — 查询 ParseSnapshot
- POST /internal/index-versions/{id}/activate — 激活索引版本
- POST /internal/index-versions/{id}/rollback — 回滚索引版本
- POST /internal/index-versions/{id}/cleanup — 清理索引版本

### 4.4 services/workbench-api

workbench-api 是文档处理与审批工作台的受控 API 层，面向文档处理人员、业务人员、审批人员。

核心原则：**在既有规则下处理内容**，不定义规则。

它提供的能力包括：

- 文档上传与生命周期跟踪
- ParseSnapshot 状态展示与 chunk 预览
- 选择已有 parser profile 进行沙盒试跑
- 审批工作台（Pending Ticket 列表、单票详情、Approve/Reject/Return）

它不是治理真相源。它不创建 parser profile，不配置 collection，不管理权限。

最终设计见 services/workbench-api/workbench-api.md。

### 4.5 services/access

access 是 Java 在线入口，负责：

- REST 暴露（POST /v1/retrieve）
- MCP Server 暴露（POST /mcp，Streamable HTTP）
- 入口认证与权限校验（ApiKeyRegistry DB 查询）
- 请求翻译（RetrieveRequestBuilder）
- trace 记录（run_traces、run_steps）

以下职责**不属于** access：

- 检索算法
- 底层索引读取
- 生命周期真相
- 限流（当前仅预留挂点，未实现）

当前已实现：完整的 REST + MCP 双入口、DB 鉴权、请求翻译、trace 落库。

### 4.6 services/retrieval

retrieval 是 Java 在线检索核心，负责：

- principal scope 解析
- published document 与 active index 解析
- 权限与生命周期过滤
- hybrid recall
- fusion、rerank、expansion、context pack
- KnowledgeContext 组装
- retrieval trace
- **read-path 缓存**（query embedding cache + recall candidate cache）

缓存设计要点：
- 两层缓存完全自有，不依赖 upstream RAGFlow Redis
- `CachedQueryEmbeddingClient` 缓存 embedding 结果（TTL 24h），省外部 embedding 调用
- `RecallOrchestrator` 缓存权限裁剪后的 fused candidates（TTL 60s），省 OpenSearch/Qdrant 召回
- 失效靠 `activeIndexVersionId` + `profileHash` + `scope/filter hash`，不扫 Redis
- 默认 `provider: noop`，Redis 故障时 fail-open
- 不缓存最终 `KnowledgeContext`（后面还有 expansion、aggregation、packing）

它绝不能把 RAGFlow 的 dataset/file 身份当成自己的权限模型。

它的权限模型始终围绕：

- tenant_id
- collection_id
- final_doc_id
- 平台生命周期与可见性事实

它的机制来源可以吸收：

- RAGFlow 的 query normalization、hybrid retrieval、fusion、rerank 参数化思路
- ContextWeaver 的 smart cutoff、adjacent expansion、section expansion、token budget context pack

当前已实现：DB-backed 主链，包括 JdbcRetrievalProfileStore、JdbcPublishedDocumentSource、JdbcChunkRegistryKnowledgeStore、JdbcIndexRegistrySource、hybrid recall、rerank、expansion、context pack。

### 4.7 services/admin

admin 是平台管理后台，面向平台管理员和运维人员，面向 admin-console 前端的唯一后端入口。

核心原则：**定义规则、管理资源、维持系统**。

它最终应承载：

- 全局配置管理（parser profile、retrieval profile、collection、API key）
- 审批覆盖（对已决策 ticket 的 override）
- 质量评测闭环（评测集、bad case、趋势看板）
- 运维控制与审计（job 重试/回滚、队列监控、告警规则）
- trace timeline 查询聚合

它不直接拥有业务状态，所有写操作通过下游内部 API 代理执行。

最终设计见 services/admin/admin.md。

### 4.8 apps/admin-console

admin-console 是 services/admin 的前端入口。三个前端入口之一：

| 入口 | 用户 | 后端 |
|------|------|------|
| workbench-ui | 文档处理人员/审批人员 | workbench-api |
| admin-console | 平台管理员/运维 | admin |
| 外部 Agent | AI Agent / 应用 | access |

admin-console 负责承载：

- 全局配置管理界面
- 审批覆盖操作
- 质量评测工作台
- 运维控制面板
- trace timeline 浏览

workbench-ui 负责承载：

- 文档上传与进度跟踪
- ParseSnapshot 预览与 chunk 查看
- parser profile 沙盒试跑
- 审批工作台（普通审批）

## 5. RAGFlow 接入策略

本项目对 RAGFlow 的使用方式，比 Reality-RAG 旧文档里的表述更直接，也更收敛。

核心区别是：

- 架构属于本平台
- 解析与分块运行时可以直接依赖 RAGFlow 模块
- 但正式 parser 输入 owner 属于 indexing，不属于 intake-pipeline

### 5.1 RAGFlow 被用于什么

RAGFlow 用于：

- 文档解析
- OCR / layout-aware 文档理解
- 结构恢复
- ParseSnapshot 支撑
- chunking
- 解析/分块工作台能力

典型范围包括：

- deepdoc/parser/* 和 deepdoc/vision/*
- 分块相关 metadata 与 chunker 模块
- 只服务于解析/分块工作流的 dataset/document/chunk UI 和 API

### 5.2 RAGFlow 不允许拥有什么

RAGFlow 不能成为以下真相源：

- 企业 collection 治理
- 平台文档身份
- 文档 ACL
- 审批结论
- 已发布可见性
- 生命周期迁移
- 检索权限语义

### 5.3 接入规则

- 对已经成熟且正好适合的解析/分块能力，直接复用 RAGFlow 运行时模块
- 不让 intake-pipeline 持有第二套正式 parser 主链
- 审批前内容预览通过 indexing 生成的 ParseSnapshot 提供
- 对 retrieval 侧成熟且高价值的检索/上下文工程机制，吸收 RAGFlow 与 ContextWeaver 的方法链和行为语义
- 在平台拥有的服务边界后面进行隔离
- 不让上游产品语义反向污染本平台治理模型

## 6. 全局不变量

以下不变量定义了系统的基本约束。

### 6.1 每类真相只有一个写 owner

每个主要状态域只有一个写 owner：

- source file 生命周期：document-service / intake 文件域
- intake job state：intake orchestrator
- approval state：approval domain
- publish state：publishing domain
- active index state：indexing registry
- retrieval visibility：published document lifecycle facts

其他模块可以读取、缓存、投影，但不能隐式分叉所有权。

### 6.2 治理真相属于平台

所有检索可见性与生命周期语义，都由平台自己的治理事实决定，而不是由工作台本地对象决定。

### 6.3 chunk 是派生产物

chunk 是文档派生产物。因此：

- chunk 不拥有独立 ACL
- chunk 可见性继承自文档级治理与生命周期
- chunk 必须能够回溯到 source span 与文档身份

### 6.4 契约是跨语言真相

跨语言兼容性必须由共享契约保证，不能靠本地重复假设维持。

### 6.5 事件至少一次投递，消费者必须幂等

系统默认假设：

- 会发生重试
- 会发生重复投递
- 会发生局部失败

因此：

- 事件语义按至少一次投递设计
- 消费者必须幂等
- 审计与生命周期状态必须能承受 replay

### 6.6 纪律与反模式

以下纪律和反模式来自旧项目经验，当前项目必须继续遵守。

**必须遵守的三条纪律**：

1. 不让 workbench 对象升格为平台真相
   - dataset、file、chunk 只能服务于解析工作台和运行时
   - 不得替代 collection 治理、文档生命周期、ACL、发布状态

2. 不让 retrieval 直接依赖上游产品宿主
   - 可以吸收 RAGFlow 和 ContextWeaver 的策略、参数、行为语义
   - 不能把它们的产品边界和宿主模型搬进 Java 主链

3. 不把过渡层误认成最终架构
   - 目录存在不代表已经是稳定主线
   - 应以"谁在承载真实运行时"和"谁拥有最终真相"为判断依据

**应避免的反模式**：

- 不要写"为了以后迁移方便"的抽象层，然后长期无人消费
- 不要把上游整套产品边界搬进来，再试图慢慢删
- 不要让旧文档里的阶段性说法继续充当当前架构真相
- 不要在没有主线闭环前，先花大量精力恢复外壳目录
- 不要把能直接复用的成熟模块改写成一组表面相似的本地实现
- 不要让文档领先代码太多，导致"文档说已实现，代码找不到"

## 7. 当前仓库现状

以当前仓库状态看：

- contracts 已存在，已覆盖摄入、审批、发布、索引、检索、审计、遥测全链路
- packages/contracts、packages/persistence、packages/documents 已存在
- packages/persistence 已包含完整的 ORM 模型、outbox repository、consumer idempotency
- services/intake-pipeline 是当前最完整的服务区域（document-service、approval-service、conversion-worker、agent-review-worker）
- services/indexing 已形成可读主线（ParsePreviewRunner、IndexJobRunner、activation/rollback/cleanup）
- services/access 已形成可读主线（REST + MCP 双入口、DB 鉴权、trace 落库）
- services/retrieval 已形成 DB-backed 主链（profile、chunk、index、recall、rerank、pack）
- upstream/ragflow 已经存在，作为源码分叉基础
- services/workbench-api 最终设计已定（见 services/workbench-api/workbench-api.md），待落地实现
- services/admin 最终设计已定（见 services/admin/admin.md），待落地实现

当前仓库已闭环的链路：

1. 摄入治理链路：source file -> intake job -> stage tasks -> approval -> publish command
2. 解析索引链路：ParsePreview -> ParseSnapshot -> IndexBuild -> chunk registry -> index activate
3. 在线检索链路：REST/MCP -> access -> retrieval -> KnowledgeContext

当前端到端主链状态：

- 摄入治理链路：已闭环（source file -> intake job -> approval -> publish command）
- 解析索引链路：已闭环（ParsePreview -> ParseSnapshot -> IndexBuild -> chunk registry -> index activate）
- 在线检索链路：已闭环（REST/MCP -> access -> retrieval -> KnowledgeContext）
- 发布事实投影链路：已闭环（indexing 通过 `/internal/index-projections/sync` 向 retrieval 同步 published_documents、index_versions、index_registry、chunk_registry；admin 通过 `/internal/retrieval-profile-projections/sync` 向 retrieval 同步 retrieval_profiles）
- 权限投影链路：已闭环（admin 通过 `/internal/api-key-projections/sync` 向 access 同步 api_key_projection）
- real-runtime smoke test：strict 模式 28/28 PASS（2026-05-28），验证真实多进程 HTTP + PostgreSQL + OpenSearch/Qdrant + SiliconFlow embedding/rerank + 契约投影同步全链路

### 真实依赖证据摘要（Real Dependency Evidence Report）

**Baseline audit (normal mode, no strict enforcement):** `py -3.14 scripts/run_real_runtime_smoke.py` — 26/26 PASS.
See initial audit for baseline PARTIAL/NOT PROVEN verdicts before strict mode was implemented.

**Strict mode verification (2026-05-28):** `py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends` — **28/28 PASS**.

| 依赖 | Strict 模式证据 | 判定 |
|---|---|---|
| PostgreSQL | 所有 7 个服务 DATABASE_URL/jdbc 指向 `postgresql://127.0.0.1:5432/rag_flow`；retrieval 日志确认为 `PgConnection` | **TRUE** |
| OpenSearch 写入 + 召回 | smoke 直接 `_search os_default_col_smoke_idxv_col_smoke_active` 命中 `doc_smoke_test`（hits=1）；检索日志 `OpenSearch live recall returned 1 hits` | **TRUE** — strict smoke verified |
| Qdrant 写入 + 召回 | smoke 直接 `scroll qd_default_col_smoke_idxv_col_smoke_active` 命中 `doc_smoke_test`（points=1）；检索日志 `Qdrant live recall returned 1 hits` | **TRUE** — strict smoke verified |
| SiliconFlow embedding (indexing) | `.env` 有 API key + model；Qdrant point 携带真实 1024 维向量 | **TRUE** |
| SiliconFlow embedding (retrieval) | 检索日志 `SiliconFlow embedding succeeded, model=BAAI/bge-m3, dimension=1024` | **TRUE** — strict smoke verified |
| SiliconFlow rerank (retrieval) | 检索日志 `SiliconFlow rerank succeeded...returned 1 results`；`run_steps.source_stages: ["rerank_live"]` | **TRUE** — strict smoke verified |
| 无 SQL fixture | `spring.sql.init.mode=never`；数据全部来自本轮 publish + projection sync | **TRUE** |
| retrieval_profile | `ret_smoke_01` 由 admin 创建，经 HTTP projection sync 同步到 retrieval | **TRUE** |

**仍为 test double（implementation complete, strict proof pending）**：
- JWT auth：`smoke-test-secret` HS256 — **test double**（production JWT issuer/audience verification implemented + tested; OAuth/IdP SSO not done）
- Redis retrieval cache：`provider: noop`（normal mode）— **test double**；`RedisRetrievalCache.java` implementation complete；`--require-redis-cache` strict proof **NOT RUN**（Redis requires auth credentials not available in this environment）

### 认证边界（Auth Boundary）

| Service | 认证方式 | Token 类型 | 说明 |
|---|---|---|---|
| admin | Bearer JWT | HS256 JWT（`ADMIN_JWT_SECRET`） | Login 签发；可配置 issuer/audience；smoke mode 使用 `smoke-test-secret` |
| workbench-api | Bearer JWT | HS256 JWT（`JWT_SECRET`） | 本地验签，不提供 login；可配置 issuer/audience |
| access | API Key | `X-API-Key` + `X-Agent-Instance-Id` header | 查 `api_key_projection` 表验权；不做 end-user JWT — access 是 Agent-facing gateway |
| retrieval | 无（internal-only） | N/A | 全 `/internal/*` endpoint，由 caller（access）保证已认证 |
| indexing | 无（internal-only） | N/A | 全 `/internal/*` endpoint；应用层 `IndexingSecurity` 做 tenant/collection 授权 |
| intake-pipeline | 无（internal-only） | N/A | 全 `/v1/*` + `/internal/*` endpoint |

**Production profile 约束**：
- `AUTH_MODE=production` + `ADMIN_JWT_SECRET`/`JWT_SECRET` 必须显式设置且不得为 `smoke-test-secret` 或 `change-me-in-production`
- `AUTH_MODE=smoke`（默认）允许 smoke/test secret
- access 的 API key 验证不依赖 JWT — production 仅要求 `api_key_projection` 表数据来自 admin 投影同步

**单元测试结果**（2026-05-28 审计运行）：
- packages/contracts: 174 passed
- services/indexing: 53 passed
- services/workbench-api: 57 passed
- services/retrieval: 66 passed
- services/access: 39 passed, 1 skipped
- services/admin: 63 passed, 2 failed（`test_update_published_retrieval_fails`、`test_publish_retrieval_with_validation` — 缺少 `/internal/retrieval-profile-projections/sync` 的 respx mock，属测试待补，非代码缺陷）

### 近期建设顺序

1. 落地 services/workbench-api（文档已设计，待实现）
2. 落地 services/admin（文档已设计，待实现）
3. 补齐完整索引生命周期（update / rollback / cleanup 端到端）

这份文档定义的是本仓库的目标总体架构与服务所有权模型。后续新增或改写服务文档时，应以本文为顶层依据。

## 8. 阅读顺序

建议按这个顺序阅读：

1. 本文：docs/architecture.md
2. services/intake-pipeline/intake-pipeline.md
3. docs/ragflow-source-isolation.md
4. docs/parse-snapshot-architecture.md
5. services/access/access.md
6. services/retrieval/retrieval.md
7. services/admin/admin.md — admin 最终设计
8. services/workbench-api/workbench-api.md — workbench 最终设计

## 9. 一句话

本项目保留 Reality-RAG 的服务架构，但不再以"移植上游能力"为目标叙事；治理真相留在本地，RAGFlow 直接作为文档解析与分块运行时接入到平台边界之后。当前已闭环摄入治理、解析索引、在线检索、发布事实投影、权限投影五条主链。real-runtime smoke 28/28（strict live backends: `--require-live-backends`，2026-05-28），验证真实 PostgreSQL + OpenSearch/Qdrant + SiliconFlow embedding/rerank + 契约投影同步全链路。JWT issuer/audience verification implemented + tested；smoke auth 仍用 smoke-test-secret HS256。Redis cache implementation complete；strict Redis proof NOT RUN（credentials unavailable）。仍未完成：OAuth/IdP SSO、并发/压力测试。
