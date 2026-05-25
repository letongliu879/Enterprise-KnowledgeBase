# Enterprise KnowledgeBase 总体架构

## 1. 项目定位

`Enterprise KnowledgeBase` 是面向企业知识治理、RAG 检索和 MCP 接入的知识平台。

它是 `Reality-RAG` 的改版项目，保留了 `Reality-RAG` 的核心服务架构与职责分工：

- 文档摄入、治理、发布、索引构建使用 Python
- 在线接入与在线检索使用 Java
- 跨服务契约集中定义
- 审计、可追踪、可回放、可治理是系统一等能力

本项目与 `Reality-RAG` 的主要区别，不在于服务拆分方式，而在于上游能力接入方式：

- 不再以上游能力移植为目标叙事
- 直接使用 RAGFlow 的文档解析、结构恢复、分块等模块作为运行时能力
- retrieval 侧继续借 RAGFlow 与 ContextWeaver 的成熟检索/上下文工程机制
- RAGFlow 在本项目中是文档理解与分块工作台运行时，不是治理真相源

系统的基本立场不变：

- 文档治理真相属于本平台
- chunk 权限继承自文档治理结果
- 外部工作台对象如 `dataset_id`、`file_id` 不替代本平台的 `collection_id`、`final_doc_id`

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
  admin/             # Python：审计、评测、运行轨迹查询与运维控制面
  workbench-api/     # Python：面向解析/分块工作台的受控 API

apps/
  admin-console/     # 管理、审核、追踪、工作台前端

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
| 1 | 文件进入 | `services/intake-pipeline` | 上传、去重、扫描、source file 登记 |
| 2 | 预解析 | `services/indexing` + `upstream/ragflow` | 文档理解、结构恢复、ParseSnapshot、chunk 预览 |
| 3 | 治理处理 | `services/intake-pipeline` | 编排处理阶段、风险检查、agent review、审批流 |
| 4 | 发布准备 | `services/intake-pipeline` | 生成最终文档身份、确认标签、生命周期事实、发布命令 |
| 5 | 正式分块与索引写入 | `services/indexing` | 复用 ParseSnapshot、chunk 生成、embedding、OpenSearch/Qdrant 写入、索引版本管理 |
| 6 | 外部查询接入 | `services/access` | REST、MCP、认证、限流、请求翻译 |
| 7 | 检索执行 | `services/retrieval` | scope 解析、权限过滤、混合召回、融合、精排、上下文包装 |
| 8 | 审计与运维 | `services/admin` + `apps/admin-console` | 运行轨迹、评测、bad case、运维与审核界面 |

## 4. 核心边界

### 4.1 `contracts`

`contracts/` 是全系统唯一的跨服务契约源。

它定义：

- 核心对象 schema
- internal API seam
- event schema
- trace / step / artifact 等运行轨迹对象

规则：

- Python 和 Java 不得各自维护漂移的独立契约真相
- 本地 mirrored DTO 只能作为运行时投影或兼容层
- 契约演进必须以 `contracts/` 为起点

### 4.2 `services/intake-pipeline`

`intake-pipeline` 是企业级摄入控制面。

它拥有：

- 原始文件接收
- source file 生命周期
- 各处理阶段的全局编排
- 风险审核与审批决策流程
- 已发布文档生命周期事实
- 发布命令与状态推进

它不拥有：

- 最终的解析/分块运行时细节
- parser backend owner
- ParseSnapshot 真相
- embedding 生成
- 在线检索

它是文档治理真相的 owner。

补充约束：

- intake 可以消费 ParseSnapshot 做审批、人工校验和工作台展示。
- intake 不再拥有正式 parser 输入语义。
- intake 产生的 markdown 或轻量转换文本只能作为治理辅助产物，不能成为 indexing 唯一正式解析入口。

### 4.3 `services/indexing`

`indexing` 是文档理解与索引构建运行时。

它拥有：

- 原始文件预解析
- ParseSnapshot 生成与版本化
- 面向索引的内容标准化
- 结构感知解析
- chunk 生成
- embedding 生成
- lexical / vector 索引记录生成
- index write / activate / rollback / revision 管理

它不拥有：

- 审批决策
- 文档最终可见性决策
- 对外查询 API

它的关键设计立场是：

- 直接复用 RAGFlow 的解析与分块模块
- parser/chunker 只有一个正式 owner，即 `indexing`
- 审批前预览来自 `ParseSnapshot`，而不是来自 intake 自己维护的第二套解析产物
- 保留本平台自己的文档身份、治理、生命周期和发布模型

### 4.4 `services/workbench-api`

`workbench-api` 是解析与分块工作台的受控 API 层。

它提供的能力包括：

- ParseSnapshot 状态展示
- chunk 预览
- parser/chunker 参数调试
- 人工确认或复核动作

它不是治理真相源。

它不得重新定义：

- collection 归属
- 最终文档身份
- 审批状态
- 已发布可见性

### 4.5 `services/access`

`access` 是 Java 在线入口。

它拥有：

- REST 暴露
- MCP Server 暴露
- 入口认证与权限校验
- 限流与 deadline 控制
- retrieval 请求翻译

它不拥有：

- 检索算法
- 底层索引读取
- 生命周期真相

### 4.6 `services/retrieval`

`retrieval` 是 Java 在线检索核心。

它拥有：

- principal scope 解析
- published document 与 active index 解析
- 权限与生命周期过滤
- hybrid recall
- fusion、rerank、expansion、context pack
- `KnowledgeContext` 组装
- retrieval trace

它绝不能把 RAGFlow 的 `dataset/file` 身份当成自己的权限模型。

它的权限模型始终围绕：

- `tenant_id`
- `collection_id`
- `final_doc_id`
- 平台生命周期与可见性事实

它的机制来源可以吸收：

- RAGFlow 的 query normalization、hybrid retrieval、fusion、rerank 参数化思路
- ContextWeaver 的 smart cutoff、adjacent expansion、section expansion、token budget context pack

### 4.7 `services/admin`

`admin` 是审计与运维控制面。

它最终应承载：

- retrieval profile 管理
- index / chunk profile 管理
- parser backend 开关
- trace 查询
- bad case / eval 工作流

### 4.8 `apps/admin-console`

`admin-console` 是统一前端。

它负责承载：

- 治理审核
- 运维管理
- 运行轨迹浏览
- indexing workbench 观察面

它可以复用 RAGFlow 的工作台交互思路，但呈现的必须是本平台自己的对象模型与生命周期语义。

## 5. RAGFlow 接入策略

本项目对 RAGFlow 的使用方式，比 `Reality-RAG` 旧文档里的表述更直接，也更收敛。

核心区别是：

- 架构属于本平台
- 解析与分块运行时可以直接依赖 RAGFlow 模块
- 但正式 parser 输入 owner 属于 `indexing`，不属于 intake

### 5.1 RAGFlow 被用于什么

RAGFlow 用于：

- 文档解析
- OCR / layout-aware 文档理解
- 结构恢复
- ParseSnapshot 支撑
- chunking
- 解析/分块工作台能力

典型范围包括：

- `deepdoc/parser/*`
- `deepdoc/vision/*`
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

接入规则是：

- 对已经成熟且正好适合的解析/分块能力，直接复用 RAGFlow 运行时模块
- 不让 intake 持有第二套正式 parser 主链
- 审批前内容预览通过 indexing 生成的 ParseSnapshot 提供
- 对 retrieval 侧成熟且高价值的检索/上下文工程机制，吸收 RAGFlow 与 ContextWeaver 的方法链和行为语义
- 在平台拥有的服务边界后面进行隔离
- 不让上游产品语义反向污染本平台治理模型

## 6. 全局不变量

以下不变量定义了系统的基本约束。

### 6.1 每类真相只有一个写 owner

每个主要状态域只有一个写 owner：

- source file 生命周期：`document-service` / intake 文件域
- intake job state：intake orchestrator
- approval state：approval domain
- publish state：publishing domain
- active index state：indexing registry
- retrieval visibility：published document lifecycle facts

其他模块可以读取、缓存、投影，但不能隐式分叉所有权。

### 6.2 治理真相属于平台

所有检索可见性与生命周期语义，都由平台自己的治理事实决定，而不是由工作台本地对象决定。

### 6.3 chunk 是派生产物

chunk 是文档派生产物。

因此：

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

## 7. 当前仓库现状

以当前仓库状态看：

- `contracts` 已存在
- `packages/contracts`、`packages/persistence`、`packages/documents` 已存在
- `services/intake-pipeline` 是当前最完整的服务区域
- `upstream/ragflow` 已经存在，作为源码分叉基础
- `services/workbench-api` 已经出现，作为工作台 API 接缝

当前仓库还没有完整长成上面的目标模块地图，部分服务仍未落地或仍是骨架。

这份文档定义的是本仓库的目标总体架构与服务所有权模型。后续新增或改写服务文档时，应以本文为顶层依据。

## 8. 阅读顺序

建议按这个顺序阅读：

1. 本文：`docs/architecture.md`
2. `services/intake-pipeline/intake-pipeline.md`
3. `docs/ragflow-source-isolation.md`
4. 后续补充的 `indexing`、`access`、`retrieval`、`admin` 服务级文档

## 9. 一句话

本项目保留 `Reality-RAG` 的服务架构，但不再以“移植上游能力”为目标叙事；治理真相留在本地，RAGFlow 直接作为文档解析与分块运行时接入到平台边界之后。
