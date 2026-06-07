# Agent 操作规范

本文档是项目级入口。各模块有独立的 `AGENTS.md`（深度指南）和 `api.md`（接口契约），详见下方模块索引。

## 架构总览

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
   │  检索内核 · Spring Boot · Java 17 · Maven│        │
   │  OpenSearch + Qdrant 混合检索            │        │
   └──────────────┬──────────────────────────-┘        │
                  │  POST /internal/retrieve            │
                  ▼                                     │
   ┌──────────────────────────────────────┐             │
   │          access (18081)              │◄────────────┘
   │  对外网关 · Spring Boot · Java 17     │  REST (MCP)
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
| Valkey (Redis) 8 | 缓存 (可选) | 6379 |
| MinIO | 对象存储 (暂未使用) | 9000 |

### 外部依赖
- SiliconFlow API — Embedding + Rerank 模型推理

## 技术栈

| 语言 | 框架 | 构建 | 项目 |
|------|------|------|------|
| Java 17 | Spring Boot 3.5.14 | Maven (tools/apache-maven-3.9.16) | access, retrieval |
| Python 3.12 | FastAPI | uv (workspace) | admin, indexing, intake-pipeline, workbench-api |
| TypeScript | Next.js 16 | pnpm / npm | apps/web |

## 语言环境

### Python (所有 `services/*` 中 Python 服务 + `packages/*`)
- **包管理器**：uv
- **工作区模式**：uv workspace，根目录 `pyproject.toml` 统一定义所有 workspace members（`packages/*` 和 `services/*`）
- **虚拟环境**：根目录 `.venv`，Python 3.12
- **安装依赖**：在项目根目录执行 `uv sync`
- **运行命令**：所有 Python 命令通过 `uv run` 执行（如 `uv run python`、`uv run pytest`、`uv run uvicorn`）
- **不要**：手动 pip install、编辑 PYTHONPATH、创建额外的 .venv

### Java (access, retrieval)
- **构建工具**：`tools/apache-maven-3.9.16/bin/mvn`
- **JDK**：Java 17
- **命令**：在对应 `services/<name>/` 目录执行 `mvn clean package -DskipTests` 或 `mvn spring-boot:run`

### 前端 (apps/web)
- **包管理器**：`npm`（项目锁文件 `package-lock.json`）
- **注意**：Next.js 16 与标准版有 API 差异，写代码前先读 `node_modules/next/dist/docs/`

## 开发工作流

### 运行测试
```bash
# 所有 Python 模块
uv run pytest                    # 根目录执行，覆盖所有 workspace members

# 单个 Python 模块
uv run pytest services/admin/tests/

# Java 模块（在模块目录内）
mvn test
```

### Smoke 测试
```bash
uv run python scripts/ekb_smoke_test.py
uv run python scripts/run_real_runtime_smoke.py --use-existing-services
```

### E2E 测试
```bash
uv run python scripts/ekb_e2e_test.py
```

### 本地启动服务
```bash
# 基础设施（docker-compose）
docker compose -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis

# Python 服务（uv run）
uv run uvicorn services.admin.src.main:app --port 18084

# Java 服务（在模块目录内）
cd services/retrieval && mvn spring-boot:run
```

## 服务间通信模式

| 模式 | 说明 | 示例 |
|------|------|------|
| REST (内部) | 服务间 `/internal/*` 端点，127.0.0.1 白名单 | access → retrieval |
| REST (外部) | 带 `X-API-Key` 认证 | 外部 → access |
| Projection Sync | 幂等推送运行时数据，fail-open | indexing → retrieval (index), admin → retrieval (profile), admin → access (api key) |
| MCP Streamable HTTP | 外部 AI Agent 接入 | 外部 → access `/mcp` |

## 全局纪律

- **契约优先**：所有跨服务 API、DTO、事件变更必须先落到 `contracts/`
- **后端缺口可见**：HTTP 501 时前端显式展示 `<BackendGap>`，不静默失败
- **真相单一 owner**: source_file → document-service, intake_job → ingestion-worker, approval → approval-service, publish → publishing-worker, index → indexing
- **chunk 是派生产物**：不拥有独立 ACL，可见性继承自文档级治理
- **投影同步**：运行时数据通过显式 projection sync（幂等 + idempotency key）推送，不做跨服务 DB 直连
- **规范字段名**：所有服务强制使用 canonical wire 名 — `query`（非 `query_text`），`token_budget`（非 `max_context_tokens`），`evidence_items`（非 `result_chunks`），`doc_id`（非 `final_doc_id`），`evidence_id`（非 `chunk_id`），`content`（非 `display_text`）
- **profile 不可变性**：published 状态后的 profile 不可修改，只能创建新版本
- **fail-closed 优先**：认证/权限校验默认拒绝，安全降级需显式配置

## 模块索引

### services/ (运行时服务)

| 模块 | 语言 | 端口 | 一句话定位 |
|------|------|------|-----------|
| **access** | Java | 18081 | 知识库对外入口网关，REST + MCP Streamable HTTP，API Key 认证 |
| **retrieval** | Java | 18082 | 检索内核，OpenSearch + Qdrant 混合召回 + rerank |
| **admin** | Python | 18084 | 管理控制面，collection/profile/api-key 生命周期 + 审计 |
| **indexing** | Python | 18080 | 索引构建，文档解析 → chunk 化 → 写入 OpenSearch/Qdrant |
| **intake-pipeline** | Python | 18085 | 文档摄入流水线编排，含 document-service / indexing-service / ingestion-worker / publishing-worker / approval-service / agent-review-worker / conversion-worker |
| **workbench-api** | Python | 18083 | 工作台后端，文档上传/审批/预览 |
| **smoke_tests** | Python | — | 集成 smoke 测试集合 |

每个服务目录下有 `AGENTS.md`（定位/边界/数据流/关键对象/约束）和 `api.md`（完整接口契约）。

### packages/ (共享库)

| 模块 | 一句话定位 |
|------|-----------|
| **contracts** | 跨服务 pydantic 模型、枚举、状态机 — 所有服务从这里导入共享类型 |
| **persistence** | 数据库抽象层 — SQLAlchemy models / repository 模式 / migration |
| **documents** | 文档处理逻辑 — 文件解析 / 分块 / metadata 提取 |
| **intake_runtime** | 摄入流水线运行时 — 任务队列 / worker 框架 |
| **ragflow_runtime** | RAGFlow 上游运行时包装 — embedding / prompt / 工具调用 |

每个包目录下有 `AGENTS.md`（定位/边界/数据流/关键对象/约束）和 `api.md`（对外接口）。

### apps/ (前端)

| 模块 | 一句话定位 |
|------|-----------|
| **web** | Next.js 16 前端，admin-console + workbench 入口 |

## 关键路径示例：一次检索请求

```
外部系统
  │ POST /v1/retrieve (X-API-Key)
  ▼
access (18081)
  │ → 验证 API Key（查 api_key_projection 表）
  │ → 校验 collection_scope ⊆ knowledgeScopes
  │ → 构建 InternalRetrieveRequest（含 principal/traceId/queryId）
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
