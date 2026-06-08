# Enterprise KnowledgeBase

> 企业知识治理、RAG 检索与 MCP 接入平台。不是问答机器人，而是文档摄入、审批治理、索引构建、权限感知检索与审计追踪的治理型知识库系统。

<!-- BADGES_START -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!-- BADGES_END -->

---

## 简介

**Enterprise KnowledgeBase（EKB）** 是一套面向企业的知识治理与 RAG 检索平台，提供从文档上传、解析、审批、发布、索引，到 REST / MCP 双入口在线检索的完整闭环，并内置细粒度权限、审计与投影同步。

- **治理型设计**：文档 ACL、审批结论、生命周期状态由本平台拥有，不依赖上游 RAGFlow 宿主。
- **契约优先**：所有跨语言、跨服务契约定义在 `contracts/`，Python 与 Java 不得各自维护漂移契约。
- **投影同步**：运行时数据（profile、index、api key）通过幂等投影同步推送，不做跨服务 DB 直连。
- **fail-closed 优先**：认证/权限默认拒绝，安全降级需显式配置。

---

## 演示视频

<!-- DEMO_VIDEO_START -->
<!-- 将下方 src 替换为真实视频地址。推荐：GitHub issue/release 附件、CDN、对象存储直链。 -->
<video src="https://user-images.githubusercontent.com/YOUR_USERNAME/REPO_NAME/demo.mp4" controls width="100%">
  你的浏览器不支持 <video> 标签，请 <a href="#">点击此处观看演示</a>。
</video>

> **如何嵌入视频**：GitHub README 支持 HTML5 `<video>` 标签，不支持 YouTube iframe。把 `.mp4` 上传到 GitHub Issue / Discussion / Release 附件，复制浏览器获得的直链地址替换上方 `src` 即可。
<!-- DEMO_VIDEO_END -->

---

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Next.js 16 + React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui |
| 摄入与治理 | Python 3.12 + FastAPI + SQLAlchemy + Celery |
| 在线接入与检索 | Java 21 + Spring Boot 3.5 + JDBC |
| 向量/文本检索 | OpenSearch 2.19 (BM25) + Qdrant (Dense Vector) |
| 嵌入与精排 | SiliconFlow API (BAAI/bge-m3 / bge-reranker-v2-m3) |
| 持久化 | PostgreSQL 16 |
| 缓存 | Redis / Valkey（检索读路径，默认 noop） |
| 构建 | Maven 3.9.16（已 bundled 到 `tools/`）；uv workspace |

---

## 架构全景

```
                 ┌──────────────────────────────────────┐
                 │            admin (18084)              │
                 │  管理控制面 · FastAPI · Python        │
                 │  collection / profile / api-key / ops │
                 └────┬──────┬──────┬────────┬──────────┘
                      │      │      │        │
              REST    │      │      │        │  REST
           ┌──────────┘      │      │        └──────────┐
           ▼                 │      │                   ▼
   ┌──────────────┐          │      │          ┌──────────────┐
   │ indexing     │◄─────────┘      │          │ workbench-api│
   │ (18080)      │  profile        │          │ (18083)      │
   │ FastAPI/Py   │  validate       │          │ FastAPI/Py   │
   └──────┬───────┘                 │          └──────┬───────┘
          │                         │                 │
          │ projection sync         │ projection sync │
          ▼                         ▼                 │
   ┌──────────────────────────────────────────┐        │
   │           retrieval (18082)              │        │
   │  检索内核 · Spring Boot · Java 21 · Maven│        │
   │  OpenSearch + Qdrant 混合检索            │        │
   └──────────────┬──────────────────────────-┘        │
                  │  POST /internal/retrieve            │
                  ▼                                     │
   ┌──────────────────────────────────────┐             │
   │          access (18081)              │◄────────────┘
   │  对外网关 · Spring Boot · Java 21     │  REST (MCP)
   │  REST + MCP Streamable HTTP          │
   └──────────────────────────────────────┘

                   ┌──────────────────────────┐
                   │  intake-pipeline (18085)  │
                   │ 文档摄入流水线 · FastAPI/Py │
                   │  ┌──────────────────┐     │
                   │  │ document-service │     │
                   │  │ indexing-service │     │
                   │  │ ingestion-worker │     │
                   │  │ publishing-worker│     │
                   │  │ approval-service │     │
                   │  │ agent-review     │     │
                   │  │ conversion-worker│     │
                   │  └──────────────────┘     │
                   └──────────────────────────┘
```

### 基础设施

| 组件 | 用途 | 端口 |
|------|------|------|
| PostgreSQL 16 | 主数据库 | 5432 |
| OpenSearch 2.19 | 全文检索 (BM25) | 19201 |
| Qdrant | 向量检索 | 6333/6334 |
| Valkey (Redis) 8 | 缓存（可选） | 6379 |
| MinIO | 对象存储（暂未使用） | 9000 |

### 服务清单

| 服务 | 语言 | 端口 | 认证 | 职责 |
|---|---|---|---|---|
| **workbench-api** | Python | 18083 | Bearer JWT | 文档上传、审批工作台、生命周期跟踪、检索代理、SQL Projection Store |
| **admin** | Python | 18084 | Bearer JWT | 集合管理、API 密钥、Parser/Retrieval Profile、运维控制面 |
| **access** | Java | 18081 | X-API-Key | REST + MCP 双入口、认证、请求翻译、trace |
| **retrieval** | Java | 18082 | 无 (caller-gated) | 权限感知混合检索、精排、上下文包装、两层读路径缓存 |
| **indexing** | Python | 18080 | 应用层授权 | 解析、分块、embedding、索引写入与版本管理、Chunk Revision |
| **document-service** | Python | 8006 | 内部 | 源文件元数据、上传、去重、扫描 |
| **approval-service** | Python | 18087 | 内部 | 审批决策、工单、final_doc_id 生成 |
| **publishing-worker** | Python | 18086 | 内部 | 发布命令执行、资产写入、索引激活编排 |
| **conversion-worker** | Python | 18089 | 内部 | 文档转换、质量评分、相似度检测 |
| **agent-review-worker** | Python | 18090 | 内部 | 智能审核（PII、visibility 风险） |
| **ingestion-worker** | Python | 18088 | 内部 | 摄入任务编排、阶段调度、事件分发 |
| **indexing-service**（intake facade）| Python | — | 内部 | publishing-worker 调用 indexing 的 facade |

> `intake-pipeline`（端口 18085）当前仅用于兼容/冒烟场景，ekb-svc.py 默认启动 6 个独立子服务而非该 monolith。

---

## 核心数据流

### 1. 文档摄入治理流

```
上传
  │ POST /upload
  ▼
DocumentService — SHA-256 校验 + 恶意扫描
  │ source_file: UPLOADING → UPLOADED → SCANNING → READY
  ▼
FileReady 事件 → ingestion-worker (orchestrator)
  │ claim → 创建 intake_job
  ▼
CONVERSION_QUEUED ──► conversion-worker ──► StageCompleted
  │
REVIEW_QUEUED ─────► agent-review-worker ──► StageCompleted
  │
APPROVAL_REQUESTED ─► approval-service ──► ApprovalDecided
  │
PUBLISH_QUEUED ────► publishing-worker ──► PublishCompleted
  │
  ▼
PUBLISHED
```

**状态机**

- `source_file_state`：UPLOADING → UPLOADED → SCANNING → READY → CLAIMED → CONSUMED → CLEANABLE → CLEANED / FAILED
- `intake_job_state`：CREATED → CONVERSION_* → REVIEW_* → APPROVAL_REQUESTED → APPROVAL_DECIDED → PUBLISH_* → PUBLISHED / REJECTED / FAILED
- `approval_ticket_state`：SYSTEM_DECIDED / PENDING → APPROVED / REJECTED / RETURNED / EXPIRED
- `publish_state`：PUBLISH_CREATED → ASSET_WRITING → ASSET_WRITTEN → PERSISTING → PERSISTED → INDEXING → INDEXED → PUBLISH_SUCCEEDED / PUBLISH_FAILED

### 2. 解析索引流

```
ParsePreviewRequested
  │
  ▼
ParseHintDetector → ParsePolicyResolver → RAGFlowAppRuntime.build_preview()
  │
  ▼
ParseSnapshot（可复用的一等产物）
  │
  ▼
IndexBuildRequested → 加载 ParseSnapshot + governance overlay
  │ 合并 pre-publish chunk edits → chunk materialization
  │ 按 embedding_text_policy 分片 → embedding
  │ HybridIndexBackend.write_bundle (OpenSearch + Qdrant)
  │ activate → projection sync → cache purge (fail-open)
  ▼
可检索的 IndexVersion + chunk_registry
```

### 3. 在线检索流

```
外部系统
  │ POST /v1/retrieve (X-API-Key + X-Agent-Instance-Id)
  ▼
access (18081)
  │ → ApiKeyRegistry 读 api_key_projection
  │ → 校验 collection_scope ⊆ knowledgeScopes
  │ → 生成 queryId / traceId / principal
  │ → 构建 InternalRetrieveRequest
  │ POST /internal/retrieve
  ▼
retrieval (18082)
  │ → CollectionRetrievalPlanBuilder：加载 profile + active index + published docs
  │ → QueryPreparationService：metadata filter + cross-languages + keyword extraction
  │ → PermissionPrefilter：collection + state + docId + principal/group + visibility
  │ → HybridRecaller：OpenSearch (BM25) + Qdrant (vector) → fusion
  │ → RerankService：token weighting + rank features → live rerank / heuristic fallback
  │ → SmartTopKCutoff → ChunkExpander (neighbor + breadcrumb)
  │ → ChunkAggregationService (TOC + children) → KnowledgeContextPacker
  │ ← KnowledgeContext
  ▼
access → 返回给外部系统
```

### 4. 投影同步

| 源 | 目标 | 端点 | 内容 |
|---|---|---|---|
| admin | retrieval | `POST /internal/retrieval-profile-projections/sync` | retrieval profile |
| admin | access | `POST /internal/api-key-projections/sync` | api key 运行时投影 |
| indexing | retrieval | `POST /internal/index-projections/sync` | index version + chunk registry |

所有投影同步均携带 `idempotencyKey`，消费者幂等。

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.12+ | Python 服务运行时 |
| uv | latest | Python 包管理与 workspace |
| Node.js | 20+ | 前端构建 |
| Java | 21 | Java 服务运行时 |
| Maven | 3.9+ | 已 bundled 到 `tools/apache-maven-3.9.16` |
| PostgreSQL | 16 | 主数据库 |
| OpenSearch | 2.19 | 文本检索 |
| Qdrant | latest | 向量检索 |
| Redis / Valkey | 8 | 检索缓存（可选） |

### 1. 启动基础设施

```bash
cd deploy
cp .env.example .env
# 编辑 .env，填入 DATABASE_PASSWORD、REDIS_PASSWORD、SiliconFlow API Key 等
docker compose up -d postgres opensearch qdrant redis
```

### 2. 安装 Python 依赖

项目使用 [uv](https://docs.astral.sh/uv/) 管理 Python workspace，根目录 `pyproject.toml` 统一定义 workspace members。

```bash
uv sync
```

### 3. 配置环境变量

```bash
cp deploy/.env.example deploy/.env
# 编辑 deploy/.env，填入 SiliconFlow API Key 等真实值
```

最小可运行配置要点：

- `AUTH_MODE=smoke`：最小模式，使用测试 JWT Secret，无需真实 IdP
- `INDEXING_EMBEDDING_API_KEY` / `INDEXING_CHAT_API_KEY`：SiliconFlow
- `EMBEDDING_API_KEY` / `RERANKER_API_KEY`：retrieval 用 SiliconFlow
- `DATABASE_URL`：PostgreSQL

### 4. 启动后端服务（推荐）

```bash
uv run python scripts/ekb-svc.py start
```

常用诊断命令：

```bash
uv run python scripts/ekb-svc.py status              # 查看服务状态
uv run python scripts/ekb-svc.py logs retrieval      # 查看 retrieval 日志
uv run python scripts/ekb-svc.py logs retrieval -f   # 实时跟踪日志
uv run python scripts/ekb-svc.py restart retrieval   # 重启单个服务
uv run python scripts/ekb-svc.py stop                # 停止所有服务
uv run python scripts/ekb-svc.py build               # 手动编译 Java 服务
```

<details>
<summary>手动启动（调试用，每个服务一个终端）</summary>

```bash
# Python 服务
uv run python -m uvicorn admin_service.main:app           --host 127.0.0.1 --port 18084
uv run python -m uvicorn indexing_service.main:app        --host 127.0.0.1 --port 18080
uv run python -m uvicorn workbench_api.main:app           --host 127.0.0.1 --port 18083
uv run python -m uvicorn document_service.main:app        --host 127.0.0.1 --port 8006
uv run python -m uvicorn approval_service.main:app        --host 127.0.0.1 --port 18087
uv run python -m uvicorn publishing_worker.main:app       --host 127.0.0.1 --port 18086
uv run python -m uvicorn conversion_worker.main:app       --host 127.0.0.1 --port 18089
uv run python -m uvicorn agent_review_worker.main:app     --host 127.0.0.1 --port 18090
uv run python -m uvicorn ingestion_worker.main:app        --host 127.0.0.1 --port 18088

# Java 服务（先编译）
cd services/retrieval && mvn package -DskipTests
cd services/access    && mvn package -DskipTests

java -Dspring.profiles.active=smoke -Dserver.port=18082 -jar services/retrieval/target/retrieval-*.jar
java -Dspring.profiles.active=smoke -Dserver.port=18081 \
     -Daccess.retrieval.base-url=http://127.0.0.1:18082 \
     -jar services/access/target/access-*.jar
```

</details>

### 5. 启动前端

```bash
cd apps/web
cp .env.local.example .env.local
npm install
npm run dev
```

打开 http://localhost:3000。

前端 `.env.local` 默认代理：

| 变量 | 默认地址 | 对应服务 |
|---|---|---|
| `NEXT_PUBLIC_ADMIN_API_BASE_URL` | http://localhost:18084 | admin |
| `NEXT_PUBLIC_WORKBENCH_API_BASE_URL` | http://localhost:18083 | workbench-api |
| `NEXT_PUBLIC_ACCESS_API_BASE_URL` | http://localhost:18081 | access |
| `NEXT_PUBLIC_RETRIEVAL_API_BASE_URL` | http://localhost:18082 | retrieval |

### 6. 验证

```bash
# 健康检查示例
curl http://localhost:18084/health        # admin
curl http://localhost:18083/workbench/health  # workbench-api
curl http://localhost:18080/health        # indexing
curl http://localhost:18081/health        # access
curl http://localhost:18082/health        # retrieval

# 运行时冒烟测试（要求后端已启动）
uv run python scripts/run_real_runtime_smoke.py --use-existing-services

# 全链路 smoke
uv run python scripts/ekb_smoke_test.py

# E2E
uv run python scripts/ekb_e2e_test.py
```

---

## 构建与验证

### 单元/集成测试

```bash
# 所有 Python workspace members
uv run pytest

# 单个服务
cd services/admin         && uv run pytest tests/ -v
cd services/workbench-api && uv run pytest tests/ -v
cd services/indexing      && uv run pytest tests/ -v

# Java 服务
cd services/access    && mvn test
cd services/retrieval && mvn test -Dtest='!RealSqliteIndexingRegistrySmokeTest'
```

### 前端构建 + E2E

```bash
cd apps/web
npm run build
npx playwright test
```

### 运行时冒烟测试

```bash
# 基础模式（默认验证 split intake chain，使用 stub backend）
uv run python scripts/run_real_runtime_smoke.py

# 严格模式（要求所有真实后端在线）
uv run python scripts/run_real_runtime_smoke.py --use-existing-services

# 严格模式 + Redis 缓存验证
uv run python scripts/run_real_runtime_smoke.py --use-existing-services --require-redis-cache
```

---

## 项目结构

```
Enterprise KnowledgeBase/
├── apps/
│   └── web/                    # Next.js 前端工作台（治理型 UI）
├── contracts/                  # 跨语言契约源
│   ├── schemas/                # 核心对象 schema
│   ├── events/                 # 事件契约
│   └── openapi/                # REST API 契约
├── docs/
│   ├── architecture.md         # 总体架构设计
│   ├── frontend-workbench.md   # 前端工作台文档
│   └── incident-log.md         # 事件记录
├── packages/                   # 共享包
│   ├── contracts/              # Python 运行时契约包
│   ├── persistence/            # ORM 模型与仓储
│   ├── documents/              # 共享文档域逻辑
│   ├── intake_runtime/         # 摄入流水线运行时
│   └── ragflow_runtime/        # RAGFlow 运行时封装
├── scripts/
│   ├── ekb-svc.py              # 本地服务管理器（start/stop/status/logs/restart/build）
│   ├── ekb_smoke_test.py       # 集成 smoke 测试
│   ├── ekb_e2e_test.py         # E2E 测试入口
│   └── run_real_runtime_smoke.py   # 真实运行时冒烟测试
├── services/
│   ├── access/                 # Java：外部查询入口 (REST + MCP)
│   ├── admin/                  # Python：管理控制面
│   ├── indexing/               # Python：解析、分块、索引构建
│   ├── intake-pipeline/        # Python：摄入治理与审批流（含 6 子服务）
│   ├── retrieval/              # Java：混合检索核心
│   ├── smoke_tests/            # 运行时冒烟测试集合
│   └── workbench-api/          # Python：工作台受控 API
├── deploy/
│   ├── docker-compose.yml      # 基础设施编排
│   └── .env.example            # 环境变量模板
└── tools/
    └── apache-maven-3.9.16/    # 已 bundled Maven
```

---

## 关键设计原则

1. **每类真相只有一个写 owner**

| 状态域 | 唯一写 owner |
|---|---|
| source file 生命周期 | document-service |
| intake job state | ingestion-worker (orchestrator) |
| approval state | approval-service |
| publish state | publishing-worker |
| active index state | indexing |
| retrieval visibility | published_documents 生命周期事实 |
| chunk revision | indexing |

2. **契约是跨语言唯一真相源**：所有跨服务契约定义在 `contracts/`，Python 与 Java 不得各自维护漂移的独立契约。

3. **投影同步替代共享 DB**：运行时数据通过显式 projection sync（幂等 + idempotency key）推送，不做跨服务 DB 直连。

4. **规范字段名**：`query`（非 `query_text`）、`token_budget`（非 `max_context_tokens`）、`evidence_items`（非 `result_chunks`）、`doc_id`（非 `final_doc_id`）、`evidence_id`（非 `chunk_id`）、`content`（非 `display_text`）。

5. **profile 不可变性**：published 状态后的 profile 不可修改，只能创建新版本。

6. **chunk 是派生产物**：不拥有独立 ACL，可见性继承自文档级治理。

7. **后端缺口可见**：当后端返回 HTTP 501 时，前端显式展示 `<BackendGap>` 组件，绝不静默失败或模拟成功。

8. **fail-closed 优先**：认证/权限校验默认拒绝，安全降级需显式配置。

---

## 文档索引

1. [总体架构](docs/architecture.md)
2. [前端工作台文档](docs/frontend-workbench.md)
3. [services/intake-pipeline/AGENTS.md](services/intake-pipeline/AGENTS.md) + [api.md](services/intake-pipeline/api.md)
4. [services/indexing/AGENTS.md](services/indexing/AGENTS.md) + [api.md](services/indexing/api.md)
5. [services/retrieval/AGENTS.md](services/retrieval/AGENTS.md) + [api.md](services/retrieval/api.md)
6. [services/access/AGENTS.md](services/access/AGENTS.md) + [api.md](services/access/api.md)
7. [services/admin/AGENTS.md](services/admin/AGENTS.md) + [api.md](services/admin/api.md)
8. [services/workbench-api/AGENTS.md](services/workbench-api/AGENTS.md) + [api.md](services/workbench-api/api.md)

---

## 当前状态

### 已闭环

- 摄入治理链路
- 解析索引链路
- 在线检索链路
- 发布事实投影链路
- 权限投影链路
- 检索代理链路（workbench-api → access → retrieval）
- Chunk Revision 链路（materialization + cache purge）

### 已验证

- 严格运行时冒烟：28/28 PASS（`--require-live-backends`）
- 真实后端：PostgreSQL + OpenSearch/Qdrant + SiliconFlow embedding/rerank
- 单元测试：contracts / admin / workbench-api / indexing / access / retrieval
- 前端：Next.js 16，中文 UI，Playwright E2E PASS
- 索引版本生命周期：activate / rollback / cleanup
- Projection Store：workbench 7 张投影表 + 事件接收 + 后台协调

### 未完成

- OAuth/IdP SSO
- 容器镜像构建
- 并发/压力测试
- 服务间认证（mTLS / SPIFFE）
- 检索缓存按 collection/doc 级精确 purge

---

## 贡献指南

欢迎参与贡献。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## License

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。
