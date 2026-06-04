# Enterprise KnowledgeBase 架构

## 1. 定位

企业知识治理、RAG 检索与 MCP 接入平台。

核心能力：文档摄入、审批治理、索引构建、权限感知检索、审计追踪。不是问答机器人。

## 2. 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Next.js 16 + React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui |
| 摄入与治理 | Python 3.12+ + FastAPI + SQLAlchemy + Celery |
| 在线接入与检索 | Java 21 + Spring Boot + JDBC |
| 向量/文本检索 | OpenSearch (BM25) + Qdrant (Dense Vector) |
| 嵌入与精排 | SiliconFlow API (BAAI/bge-m3 / bge-reranker-v2-m3) |
| 持久化 | PostgreSQL 16 |
| 缓存 | Redis / Valkey (检索读路径，默认 noop) |

## 3. 服务地图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端入口                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    apps/web                            │  │
│  │  /upload /review /workbench /documents /retrieval      │  │
│  │  /collections /settings                                │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
           │                 │
           ▼                 ▼
┌─────────────────┐ ┌─────────────────────────────────────┐
│  workbench-api  │ │                admin                │
│   (Python)      │ │              (Python)               │
│  Bearer JWT     │ │             Bearer JWT              │
│  port: 18083    │ │            port: 18084              │
└────────┬────────┘ └─────────────────┬───────────────────┘
         │                            │
         ▼                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      内部服务层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   access    │  │  retrieval  │  │      indexing       │  │
│  │   (Java)    │  │   (Java)    │  │     (Python)        │  │
│  │ X-API-Key   │  │ caller-gated│  │ 应用层授权           │  │
│  │ port: 18081 │  │ port: 18082 │  │  port: 18080        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              intake-pipeline (6 子服务)                 │  │
│  │  document-service | ingestion-worker | approval-service │  │
│  │  publishing-worker | conversion-worker | agent-review   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 服务清单

| 服务 | 语言 | 端口 | 认证 | 职责 | 状态 |
|---|---|---|---|---|---|
| **workbench-api** | Python | 18083 | Bearer JWT | 文档上传、审批工作台、生命周期跟踪、检索代理、SQL Projection Store | MVP |
| **admin** | Python | 18084 | Bearer JWT | 集合管理、API 密钥、检索配置、Parser/Retrieval Profile、运维控制面 | MVP |
| **access** | Java | 18081 | X-API-Key | REST + MCP 双入口、认证、请求翻译、trace | MVP |
| **retrieval** | Java | 18082 | 无 (caller-gated) | 权限感知混合检索、精排、上下文包装、两层读路径缓存 | MVP |
| **indexing** | Python | 18080 | 无 (应用层授权) | 解析、分块、embedding、索引写入与版本管理、Chunk Revision | MVP |
| **document-service** | Python | 8006 | 无 (internal) | 源文件元数据、上传、去重、扫描 | MVP |
| **approval-service** | Python | 18087 | 无 (internal) | 审批决策、工单、final_doc_id 生成 | MVP |
| **publishing-worker** | Python | 18086 | 无 (internal) | 发布命令执行、资产写入、索引激活编排 | MVP |
| **conversion-worker** | Python | 18089 | 无 (internal) | 文档转换、质量评分、相似度检测 | MVP |
| **agent-review-worker** | Python | 18090 | 无 (internal) | 智能审核（PII、visibility 风险） | MVP |
| **ingestion-worker** | Python | 18088 | 无 (internal) | 摄入任务编排、阶段调度、事件分发 | MVP |

**注**：intake-pipeline 包含 document-service、ingestion-worker、approval-service、publishing-worker、conversion-worker、agent-review-worker 6 个独立子服务。

**前端开发代理端口**：`apps/web/next.config.ts` 中配置 rewrite，开发时前端通过 `/api/*` 访问，默认映射到 18181(access) / 18182(retrieval) / 18083(workbench) / 18084(admin)。

## 4. 核心链路

```
文件进入
  → 预解析与 ParseSnapshot
  → 治理与审批
  → 发布与索引激活
  → 在线接入 (REST / MCP)
  → 权限感知检索
  → 返回 KnowledgeContext
```

### 4.1 已闭环主链

1. **摄入治理链路**：source file → intake job → stage tasks → approval → publish command
2. **解析索引链路**：ParsePreview → ParseSnapshot → IndexBuild → chunk registry → index activate → projection sync → cache purge
3. **在线检索链路**：REST/MCP → access → retrieval → KnowledgeContext
4. **发布事实投影链路**：indexing → retrieval (HTTP sync)
5. **权限投影链路**：admin → access (HTTP sync)
6. **检索代理链路**：apps/web → workbench-api → access → retrieval
7. **Chunk Revision 链路**：apps/web → workbench-api → indexing → chunk revision materialize → cache purge

## 5. 关键边界

### 5.1 契约（contracts/）

跨语言唯一真相源。Python 和 Java 不得各自维护漂移的独立契约。

### 5.2 服务所有权

| 状态域 | 唯一写 owner |
|---|---|
| source file 生命周期 | document-service |
| intake job state | ingestion-worker (orchestrator) |
| approval state | approval-service |
| publish state | publishing-worker |
| active index state | indexing |
| retrieval visibility | published_documents 生命周期事实 |
| chunk revision | indexing |

### 5.3 RAGFlow 定位

- **用于**：文档解析、OCR、结构恢复、chunking、工作台运行时
- **不用于**：企业 collection 治理、平台文档身份、ACL、审批结论、生命周期
- **接入方式**：services/indexing 直接复用 RAGFlow 模块，不暴露 RAGFlow REST 边界给外部

### 5.4 投影同步（替代共享 DB）

- admin → retrieval：`POST /internal/retrieval-profile-projections/sync`
- indexing → retrieval：`POST /internal/index-projections/sync`
- admin → access：`POST /internal/api-key-projections/sync`

## 6. 认证边界

| 服务 | 认证方式 | 说明 |
|---|---|---|
| admin | Bearer JWT (HS256) | 可配置 issuer/audience；`AUTH_MODE=production` 要求非默认 secret |
| workbench-api | Bearer JWT (HS256) | 同上 |
| access | X-API-Key + X-Agent-Instance-Id | 查 `api_key_projection` 表验权；不做 end-user JWT |
| retrieval | 无 | `/internal/*`，由 caller（access）保证已认证 |
| indexing | 无 | `/internal/*`，应用层 `IndexingSecurity` 做 tenant/collection 授权 |
| intake-pipeline | 无 | `/v1/*` + `/internal/*`，依赖部署边界 |

## 7. 缓存

| 层级 | 说明 |
|---|---|
| Query Embedding Cache | TTL 24h，缓存 SiliconFlow embedding 结果 |
| Recall Candidate Cache | TTL 60s，缓存权限裁剪后的 fused candidates |
| 默认 Provider | `noop`（fail-open）；Redis 故障时不阻断检索 |
| 失效策略 | 基于 `activeIndexVersionId` + `profileHash` + `scope/filter hash`，不扫 Redis |
| Cache Purge | `POST /internal/cache/purge`（按前缀清除）|

## 8. 全局不变量

1. **每类真相只有一个写 owner** — 其他模块可读、缓存、投影，不可隐式分叉所有权
2. **治理真相属于平台** — 检索可见性由本平台 `published_documents` 决定，不由 RAGFlow dataset/file 决定
3. **chunk 是派生产物** — 不拥有独立 ACL，可见性继承自文档级治理
4. **契约是跨语言真相** — 兼容性由共享契约保证
5. **事件至少一次投递，消费者必须幂等**
6. **后端缺口可见** — HTTP 501 时前端显式展示，不静默失败

## 9. 当前状态（2026-06）

### 已验证

- **严格运行时冒烟**：28/28 PASS（`--require-live-backends`）
- **真实后端**：PostgreSQL + OpenSearch/Qdrant + SiliconFlow embedding/rerank
- **单元测试**：contracts / admin / workbench-api / indexing / access / retrieval
- **前端**：Next.js 16，Playwright E2E PASS
- **Chunk Revision**：materialization + cache purge 已实现
- **索引版本生命周期**：activate / rollback / cleanup 已实现
- **Projection Store**：workbench 7 张投影表 + 事件接收 + 后台协调

### 过渡中

- workbench-api 有 4 个下游 API 返回 501（snapshot chunks、chunk revision 查询/物化、retrieval cache purge）
- intake-pipeline 仍双写 `documents` / `document_policies` 兼容表，目标以 `published_documents` 为唯一事实源
- admin GraphQL 审计查询待补齐

### 未完成

- OAuth/IdP SSO
- 容器镜像构建
- 并发/压力测试
- 服务间认证（mTLS / SPIFFE）
- 检索缓存按 collection/doc 级精确 purge

## 10. 项目结构

```
Enterprise KnowledgeBase/
├── apps/web/                    # Next.js 前端（工作台 + 管理合一）
│   └── web.md                   # 前端详细设计
├── contracts/                   # 跨语言契约源
│   ├── schemas/                 # 核心对象 schema
│   ├── events/                  # 事件契约
│   └── openapi/                 # REST API 契约
├── packages/                    # 共享包
│   ├── contracts/               # Python 运行时契约
│   ├── persistence/             # ORM 模型与仓储
│   ├── documents/               # 共享文档域逻辑
│   └── ragflow_runtime/         # RAGFlow 运行时封装
├── services/                    # 服务
│   ├── access/                  # Java：外部查询入口
│   │   └── access.md
│   ├── admin/                   # Python：管理控制面
│   │   └── admin.md
│   ├── indexing/                # Python：解析、分块、索引
│   │   └── indexing.md
│   ├── intake-pipeline/         # Python：摄入治理（6 子服务）
│   ├── retrieval/               # Java：混合检索核心
│   │   └── retrieval.md
│   ├── smoke_tests/             # 运行时冒烟测试
│   └── workbench-api/           # Python：工作台 BFF
│       └── workbench-api.md
├── docs/                        # 架构文档
│   ├── architecture.md          # 本文
│   ├── frontend-workbench.md    # 前端工作台概述
│   └── incident-log.md          # 事故记录
├── deploy/                      # Docker Compose 基础设施编排
├── scripts/                     # 服务管理器、冒烟测试
└── upstream/                    # 上游源码参考（RAGFlow 分叉等）
```

## 11. 阅读顺序

1. 本文（总体架构）
2. `apps/web/web.md`（前端详细设计）
3. `services/access/access.md`（接入层详细设计）
4. `services/retrieval/retrieval.md`（检索层详细设计）
5. `services/indexing/indexing.md`（索引构建详细设计）
6. `services/admin/admin.md`（管理控制面详细设计）
7. `services/workbench-api/workbench-api.md`（工作台 API 详细设计）
