# Enterprise KnowledgeBase

企业知识治理、RAG 检索与 MCP 接入平台。

本项目是一个**治理型知识库系统**，不是问答机器人。核心能力围绕文档摄入、审批治理、索引构建、权限感知检索与审计追踪。

---

## 技术栈概览

| 层级 | 技术 |
|---|---|
| 前端工作台 | Next.js 16 + React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui |
| 摄入与治理服务 | Python 3.12+ + FastAPI + SQLAlchemy + Celery |
| 在线接入与检索 | Java 21 + Spring Boot + JDBC |
| 向量与文本检索 | OpenSearch (BM25) + Qdrant (Dense Vector) |
| 嵌入与精排 | SiliconFlow API (BAAI/bge-m3) |
| 持久化 | PostgreSQL 16 |
| 缓存 | Redis / Valkey (检索读路径缓存) |

---

## 服务地图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端入口                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ workbench-ui │  │ admin-console│  │   外部 Agent      │  │
│  │ (文档/审批)   │  │ (管理/运维)   │  │  (REST / MCP)    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼────────────┘
          │                 │                   │
          ▼                 ▼                   ▼
┌─────────────────┐ ┌───────────────┐ ┌─────────────────────┐
│  workbench-api  │ │     admin     │ │       access        │
│   (Python)      │ │   (Python)    │ │      (Java)         │
│  Bearer JWT     │ │  Bearer JWT   │ │    X-API-Key        │
└────────┬────────┘ └───────┬───────┘ └──────────┬──────────┘
         │                  │                    │
         ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      内部服务层                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │ intake-pipeline │  │    indexing     │  │  retrieval  │  │
│  │  (摄入/审批/发布) │  │ (解析/分块/索引) │  │ (混合检索核心) │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                      基础设施                                 │
│  PostgreSQL 16  │  OpenSearch 2.x  │  Qdrant  │  Redis      │
└─────────────────────────────────────────────────────────────┘
```

| 服务 | 语言 | 端口 | 认证 | 职责 |
|---|---|---|---|---|
| **workbench-api** | Python | 18083 | Bearer JWT | 文档上传、审批工作台、生命周期跟踪 |
| **admin** | Python | 18084 | Bearer JWT | 集合管理、API 密钥、检索配置、运维控制面 |
| **access** | Java | 18181 | X-API-Key | REST + MCP 双入口、认证、请求翻译、trace |
| **retrieval** | Java | 18182 | 无 (caller-gated) | 权限感知混合检索、精排、上下文包装 |
| **intake-pipeline** | Python | 18085 | 无 (internal) | 文档摄入、治理、审批流、发布命令 |
| **indexing** | Python | 18080 | 无 (internal) | 解析、分块、embedding、索引写入与版本管理 |
| **publishing-worker** | Python | 18086 | 无 (internal) | 发布命令执行、索引激活 |
| **document-service** | Python | 8006 | 无 (internal) | 源文件元数据与存储管理（intake-pipeline 子服务） |
| **approval-service** | Python | 18087 | 无 (internal) | 审批决策服务（intake-pipeline 子服务） |
| **agent-review-worker** | Python | 18090 | 无 (internal) | 智能审核 Worker（intake-pipeline 子服务） |
| **conversion-worker** | Python | 18089 | 无 (internal) | 文档转换 Worker（intake-pipeline 子服务） |
| **ingestion-worker** | Python | 18088 | 无 (internal) | 摄入任务 Worker（intake-pipeline 子服务） |

---

## 核心链路

```
文件进入
  → 预解析与 ParseSnapshot
  → 治理与审批
  → 发布与索引激活
  → 在线接入 (REST / MCP)
  → 权限感知检索
  → 返回 KnowledgeContext
```

### 已闭环主链

1. **摄入治理链路**：source file → intake job → stage tasks → approval → publish command
2. **解析索引链路**：ParsePreview → ParseSnapshot → IndexBuild → chunk registry → index activate
3. **在线检索链路**：REST/MCP → access → retrieval → KnowledgeContext
4. **发布事实投影链路**：indexing → retrieval (HTTP sync)
5. **权限投影链路**：admin → access (HTTP sync)

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.12+ | Python 服务运行时 |
| uv | latest | Python 包管理与 workspace |
| Node.js | 20+ | 前端构建 |
| Java | 21 | Java 服务运行时 |
| Maven | 3.9+ | Java 构建 |
| PostgreSQL | 16 | 主数据库 |
| OpenSearch | 2.x | 文本检索 |
| Qdrant | latest | 向量检索 |
| Redis / Valkey | 7+ | 检索缓存 |

---

### 步骤 1：启动基础设施

```bash
cd deploy

# 复制环境变量模板并填写真实值
cp .env.example .env
# 编辑 .env，填入 DATABASE_PASSWORD、REDIS_PASSWORD、SiliconFlow API Key 等

docker compose up -d postgres opensearch qdrant redis
```

基础设施端口映射：

| 服务 | 容器内端口 | 宿主机端口 |
|---|---|---|
| PostgreSQL | 5432 | 5432 |
| OpenSearch | 9201 | 19201 |
| Qdrant | 6333 / 6334 | 6333 / 6334 |
| Redis | 6379 | 6379 |

---

### 步骤 2：安装 Python 依赖

项目使用 [uv](https://docs.astral.sh/uv/) 管理 Python workspace。根目录 `pyproject.toml` 定义了 workspace members，依赖锁定在 `uv.lock`。

```bash
# 在项目根目录
uv sync
```

uv 会自动创建/管理虚拟环境，workspace 内的本地包（`packages/*`、`services/*`）通过 `tool.uv.workspace` 自动链接，无需手动 PYTHONPATH。

---

### 步骤 3：配置环境变量

本地开发环境变量统一放在 `deploy/.env`（已存在，gitignored）。首次设置时复制模板并填入真实值：

```bash
cp deploy/.env.example deploy/.env
# 编辑 deploy/.env，填入 SiliconFlow API Key 等真实值
```

`deploy/.env` 已预配置 localhost 地址，开箱即用。最小可运行配置如下：

```bash
# ========== 数据库 ==========
DATABASE_URL=postgresql+psycopg2://rag_flow:infini_rag_flow@127.0.0.1:5432/rag_flow

# ========== admin 服务 (端口 18084) ==========
ADMIN_JWT_SECRET=smoke-test-secret
ADMIN_JWT_ISSUER=ekb-admin
ADMIN_JWT_AUDIENCE=ekb
AUTH_MODE=smoke

# ========== workbench-api 服务 (端口 18083) ==========
JWT_SECRET=smoke-test-secret
JWT_ISSUER=ekb-workbench
JWT_AUDIENCE=ekb
AUTH_MODE=smoke
ADMIN_BASE_URL=http://localhost:18084
INDEXING_BASE_URL=http://localhost:18080
INTAKE_BASE_URL=http://localhost:18085
DOCUMENT_SERVICE_BASE_URL=http://localhost:8006

# ========== indexing 服务 (端口 18080) ==========
INDEXING_BACKEND_MODE=hybrid
INDEXING_OPENSEARCH_URL=http://127.0.0.1:19201
INDEXING_QDRANT_URL=http://127.0.0.1:6333
INDEXING_EMBEDDING_API_KEY=<your-siliconflow-key>
INDEXING_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
INDEXING_EMBEDDING_MODEL=BAAI/bge-m3
INDEXING_CHAT_API_KEY=<your-siliconflow-key>
INDEXING_CHAT_BASE_URL=https://api.siliconflow.cn/v1
INDEXING_CHAT_MODEL=deepseek-chat

# ========== retrieval 服务 (端口 18182) ==========
DATABASE_URL=jdbc:postgresql://127.0.0.1:5432/rag_flow
DATABASE_USERNAME=rag_flow
DATABASE_PASSWORD=infini_rag_flow
OPENSEARCH_BASE_URL=http://127.0.0.1:19201
QDRANT_BASE_URL=http://127.0.0.1:6333
EMBEDDING_API_KEY=<your-siliconflow-key>
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_API_KEY=<your-siliconflow-key>
RERANKER_BASE_URL=https://api.siliconflow.cn/v1/rerank
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
REDIS_URL=redis://127.0.0.1:6379/0
SPRING_PROFILES_ACTIVE=smoke

# ========== access 服务 (端口 18181) ==========
DATABASE_URL=jdbc:postgresql://127.0.0.1:5432/rag_flow
DATABASE_USERNAME=rag_flow
DATABASE_PASSWORD=infini_rag_flow
RETRIEVAL_BASE_URL=http://localhost:18182
SPRING_PROFILES_ACTIVE=smoke
```

> **生产环境**：`AUTH_MODE=production` + 非默认 JWT Secret + 显式 issuer/audience。
> **最小可运行**：`AUTH_MODE=smoke` 允许使用测试 Secret，后端无需真实 IdP。

---

### 步骤 4：启动后端服务

**推荐：EKB Service Manager（一键启动，自动处理依赖、编译、健康检查）**

```bash
# 在项目根目录执行
uv run python scripts/ekb-svc.py start

# 只启动 Java 服务
uv run python scripts/ekb-svc.py start --java

# 只启动 Python 服务
uv run python scripts/ekb-svc.py start --python

# 跳过基础设施检查
uv run python scripts/ekb-svc.py start --no-infra-check
```

功能：
- 自动检测基础设施（PostgreSQL、OpenSearch、Qdrant、Redis）是否就绪
- Java 服务先自动编译（`mvn package -DskipTests`），再 `java -jar` 启动，杜绝 PIPE 阻塞和超时
- 按依赖拓扑分层并行启动，同层服务同时启动
- 三阶段健康检查（port → HTTP → 200），失败自动打印日志最后 30 行
- 服务崩溃后自动重启（指数退避，最多 5 次）
- 每个服务日志独立写到 `tmp/services/<name>.out.log` / `.err.log`
- `Ctrl+C` 一键停止所有服务

```

**诊断命令**：
```bash
uv run python scripts/ekb-svc.py status              # 查看所有服务状态
uv run python scripts/ekb-svc.py logs retrieval      # 查看 retrieval 日志
uv run python scripts/ekb-svc.py logs retrieval -f   # 实时跟踪日志
uv run python scripts/ekb-svc.py restart retrieval   # 重启单个服务
uv run python scripts/ekb-svc.py stop                # 停止所有服务
uv run python scripts/ekb-svc.py build               # 手动编译 Java 服务
```

**手动启动（备选，每个服务一个终端）**

如果你需要单独调试某个服务，可以手动启动。uv workspace 自动处理包路径。

**依赖顺序（默认真实链路）**：

```
PostgreSQL / OpenSearch / Qdrant / Redis (Docker)
  → admin (18084)
  → indexing (18080)
  → document-service (8006)
  → approval-service (18087)
  → conversion-worker (18089)
  → agent-review-worker (18090)
  → publishing-worker (18086)
  → ingestion-worker (18088)
  → intake-pipeline (18085, compat/smoke only)
  → workbench-api (18083)
  → retrieval (18182)
  → access (18181)
```

```bash
# 环境变量（各服务共用）
export DOCUMENT_SERVICE_URL="http://127.0.0.1:8006"
export APPROVAL_SERVICE_URL="http://127.0.0.1:18087"
export PUBLISHING_WORKER_URL="http://127.0.0.1:18086"
export INDEXING_SERVICE_URL="http://127.0.0.1:18080"
export ALLOW_LOCAL_FALLBACK_FOR_TESTS="false"

# 各服务（每个一个终端）
uv run python -m uvicorn admin_service.main:app --host 0.0.0.0 --port 18084
uv run python -m uvicorn indexing_service.main:app --host 0.0.0.0 --port 18080
uv run python -m uvicorn document_service.main:app --host 0.0.0.0 --port 8006
uv run python -m uvicorn approval_service.main:app --host 0.0.0.0 --port 18087
uv run python -m uvicorn conversion_worker.main:app --host 0.0.0.0 --port 18089
uv run python -m uvicorn agent_review_worker.main:app --host 0.0.0.0 --port 18090
uv run python -m uvicorn publishing_worker.main:app --host 0.0.0.0 --port 18086
uv run python -m uvicorn ingestion_worker.main:app --host 0.0.0.0 --port 18088
uv run python -m uvicorn intake_pipeline.main:app --host 0.0.0.0 --port 18085  # compat/smoke only
uv run python -m uvicorn workbench_api.main:app --host 0.0.0.0 --port 18083
```

**Java 服务**（每个一个终端）：

```bash
# 先编译（首次或代码变更后需要）
cd services/retrieval && mvn package -DskipTests
cd services/access    && mvn package -DskipTests

# Terminal 7 — retrieval
cd services/retrieval
java -Dspring.profiles.active=smoke -Dserver.port=18182 -jar target/retrieval-*.jar

# Terminal 8 — access
cd services/access
java -Dspring.profiles.active=smoke -Dserver.port=18181 -Daccess.retrieval.base-url=http://127.0.0.1:18182 -jar target/access-*.jar
```

---

### 步骤 5：启动前端

```bash
cd apps/web

# 复制环境变量
cp .env.local.example .env.local

npm install
npm run dev
```

打开 http://localhost:3000，应用将 `/` 重定向至 `/upload`。

前端连接的后端地址（在 `.env.local` 中配置）：

| 前端变量 | 默认地址 | 对应服务 |
|---|---|---|
| `NEXT_PUBLIC_ADMIN_API_BASE_URL` | http://localhost:18084 | admin |
| `NEXT_PUBLIC_WORKBENCH_API_BASE_URL` | http://localhost:18083 | workbench-api |
| `NEXT_PUBLIC_ACCESS_API_BASE_URL` | http://localhost:18181 | access |
| `NEXT_PUBLIC_RETRIEVAL_API_BASE_URL` | http://localhost:18182 | retrieval |

---

### 步骤 6：验证启动

```bash
# 1. 健康检查
curl http://localhost:18084/health        # admin
curl http://localhost:18083/workbench/health  # workbench-api
curl http://localhost:18080/health        # indexing
curl http://localhost:8006/health         # document-service
curl http://localhost:18087/health        # approval-service
curl http://localhost:18089/health        # conversion-worker
curl http://localhost:18090/health        # agent-review-worker
curl http://localhost:18086/health        # publishing-worker
curl http://localhost:18088/health        # ingestion-worker
curl http://localhost:18085/health        # intake-pipeline (compat/smoke only)
curl http://localhost:18182/health        # retrieval
curl http://localhost:18181/health        # access

# 2. 运行时冒烟测试（默认验证 split intake chain，不依赖 /v1/documents）
uv run python scripts/run_real_runtime_smoke.py --require-live-backends
```

---

## 构建与验证

### 单元/集成测试

```bash
# Python 契约包
cd packages/contracts && uv run pytest tests/ -v

# Python 服务
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
# 基础模式（默认验证 document-service -> ingestion-worker -> conversion/agent-review -> approval -> publishing -> indexing）
uv run python scripts/run_real_runtime_smoke.py

# 严格模式（要求所有真实后端在线）
uv run python scripts/run_real_runtime_smoke.py --require-live-backends

# 严格模式 + Redis 缓存验证
uv run python scripts/run_real_runtime_smoke.py --require-live-backends --require-redis-cache
```

---

## 项目结构

```
Enterprise KnowledgeBase/
├── apps/
│   └── web/                    # Next.js 前端工作台 (治理型 UI)
├── contracts/
│   ├── schemas/                # 核心对象契约
│   ├── events/                 # 事件契约
│   └── openapi/                # REST API 契约
├── docs/
│   ├── architecture.md         # 总体架构设计
│   └── frontend-workbench.md   # 前端工作台文档
├── packages/
│   ├── contracts/              # Python 运行时契约包
│   ├── persistence/            # ORM 模型与仓储
│   ├── documents/              # 共享文档域逻辑
│   └── ragflow_runtime/        # RAGFlow 运行时封装
├── scripts/
│   ├── run_real_runtime_smoke.py   # 真实运行时冒烟测试
│   └── ekb-svc.py                  # 生产级服务管理器（start/stop/status/logs/restart/build）
├── services/
│   ├── access/                 # Java：外部查询入口 (REST + MCP)
│   ├── admin/                  # Python：管理控制面
│   ├── indexing/               # Python：解析、分块、索引构建
│   ├── intake-pipeline/        # Python：摄入治理与审批流
│   ├── retrieval/              # Java：混合检索核心
│   ├── smoke_tests/            # 运行时冒烟测试
│   └── workbench-api/          # Python：工作台受控 API
├── deploy/
│   └── docker-compose.yml      # 基础设施编排
└── upstream/
    └── ragflow/                # RAGFlow 源码分叉 (解析/分块运行时)
```

---

## 关键设计原则

- **治理真相留在本地**：文档 ACL、审批结论、生命周期状态由本平台拥有，不由上游 RAGFlow 宿主
- **契约是跨语言真相**：所有跨服务契约定义在 `contracts/`，Python 与 Java 不得各自维护漂移的独立契约
- **后端缺口可见**：当后端返回 HTTP 501 时，前端显式展示 `<BackendGap>` 组件，绝不静默失败或模拟成功
- **chunk 是派生产物**：chunk 不拥有独立 ACL，可见性继承自文档级治理

---

## 文档阅读顺序

1. [总体架构](docs/architecture.md)
2. [前端工作台文档](docs/frontend-workbench.md)
3. services/intake-pipeline/intake-pipeline.md
4. services/indexing/indexing.md
5. services/access/access.md
6. services/retrieval/retrieval.md
7. services/admin/admin.md
8. services/workbench-api/workbench-api.md

---

## 状态

- **摄入治理链路**：已闭环
- **解析索引链路**：已闭环
- **在线检索链路**：已闭环
- **发布事实投影链路**：已闭环
- **权限投影链路**：已闭环
- **前端工作台**：已产品化 (Next.js 16, 中文 UI, Playwright E2E)
- **严格运行时冒烟**：28/28 PASS (2026-05-28)

未完成：OAuth/IdP SSO、并发/压力测试、容器镜像构建。
