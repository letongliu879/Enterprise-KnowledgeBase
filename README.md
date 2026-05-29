# Enterprise KnowledgeBase

企业知识治理、RAG 检索与 MCP 接入平台。

本项目是一个**治理型知识库系统**，不是问答机器人。核心能力围绕文档摄入、审批治理、索引构建、权限感知检索与审计追踪。

---

## 技术栈概览

| 层级 | 技术 |
|---|---|
| 前端工作台 | Next.js 16 + React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui |
| 摄入与治理服务 | Python 3.14 + FastAPI + SQLAlchemy + Celery |
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
| Python | 3.14 | Python 服务运行时 |
| Node.js | 20+ | 前端构建 |
| Java | 21 | Java 服务运行时 |
| Maven | 3.9+ | Java 构建 |
| PostgreSQL | 16 | 主数据库 |
| OpenSearch | 2.x | 文本检索 |
| Qdrant | latest | 向量检索 |
| Redis / Valkey | 7+ | 检索缓存 |

> **Windows 用户**：使用 `py -3.14` 替代 `python3.14`。

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
| OpenSearch | 9201 | 1201 |
| Qdrant | 6333 / 6334 | 6333 / 6334 |
| Redis | 6379 | 6379 |

---

### 步骤 2：安装 Python 依赖

所有 Python 服务共用项目根目录的 `.venv`（已存在，Python 3.14）。一次性安装所有第三方依赖：

```bash
# 在项目根目录（.venv 已激活）
pip install -r requirements.txt
```

本地包（`packages/*`、`services/*`）通过 `PYTHONPATH` 暴露，无需 editable install。

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
INDEXING_OPENSEARCH_URL=http://127.0.0.1:1201
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
OPENSEARCH_BASE_URL=http://127.0.0.1:1201
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

**推荐：一键启动（自动处理依赖顺序、PYTHONPATH、日志标签）**

```bash
# 在项目根目录执行（.venv 已激活）
py -3.14 scripts/start-services.py
```

- 自动检测基础设施（PostgreSQL、OpenSearch、Qdrant、Redis）是否就绪
- 按依赖顺序启动所有服务，带颜色标签的日志统一输出到当前终端
- `Ctrl+C` 一键停止所有服务
- 支持 `--python`（只启动 Python 服务）、`--java`（只启动 Java 服务）

**手动启动（备选，每个服务一个终端）**

如果你需要单独调试某个服务，可以手动启动。所有 Python 服务共用项目根目录的 `.venv`。

**依赖顺序**：

```
PostgreSQL / OpenSearch / Qdrant / Redis (Docker)
  → admin (18084)
  → indexing (18080)
  → intake-pipeline (18085)
  → publishing-worker (18086)
  → document-service (8006)
  → workbench-api (18083)
  → retrieval (18182)
  → access (18181)
```

**Windows PowerShell**（每个服务一个终端）：

```powershell
$env:PYTHONPATH = "$PWD\packages\contracts\src;$PWD\packages\persistence\src;$PWD\packages\documents\src;$PWD\packages\ragflow_runtime\src;$PWD\services\admin\src;$PWD\services\workbench-api\src;$PWD\services\indexing\src;$PWD\services\intake-pipeline\src;$PWD\services\intake-pipeline\publishing-worker\src;$PWD\services\intake-pipeline\document-service\src"

# Terminal 1 — admin
python -m uvicorn admin_service.main:app --host 0.0.0.0 --port 18084

# Terminal 2 — indexing
python -m uvicorn indexing_service.main:app --host 0.0.0.0 --port 18080

# Terminal 3 — intake-pipeline
python -m uvicorn intake_pipeline.main:app --host 0.0.0.0 --port 18085

# Terminal 4 — publishing-worker
python -m uvicorn publishing_worker.main:app --host 0.0.0.0 --port 18086

# Terminal 5 — document-service
python -m uvicorn document_service.main:app --host 0.0.0.0 --port 8006

# Terminal 6 — workbench-api
python -m uvicorn workbench_api.main:app --host 0.0.0.0 --port 18083
```

**Linux / macOS**（每个服务一个终端）：

```bash
export PYTHONPATH="$PWD/packages/contracts/src:$PWD/packages/persistence/src:$PWD/packages/documents/src:$PWD/packages/ragflow_runtime/src:$PWD/services/admin/src:$PWD/services/workbench-api/src:$PWD/services/indexing/src:$PWD/services/intake-pipeline/src:$PWD/services/intake-pipeline/publishing-worker/src:$PWD/services/intake-pipeline/document-service/src"

python -m uvicorn admin_service.main:app --host 0.0.0.0 --port 18084
python -m uvicorn indexing_service.main:app --host 0.0.0.0 --port 18080
python -m uvicorn intake_pipeline.main:app --host 0.0.0.0 --port 18085
python -m uvicorn publishing_worker.main:app --host 0.0.0.0 --port 18086
python -m uvicorn document_service.main:app --host 0.0.0.0 --port 8006
python -m uvicorn workbench_api.main:app --host 0.0.0.0 --port 18083
```

**Java 服务**（每个一个终端）：

```bash
# Terminal 7 — retrieval
cd services/retrieval
mvn spring-boot:run -Dspring-boot.run.profiles=smoke

# Terminal 8 — access
cd services/access
mvn spring-boot:run -Dspring-boot.run.profiles=smoke
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
curl http://localhost:18080/health       # indexing
curl http://localhost:18085/health       # intake-pipeline
curl http://localhost:18086/health       # publishing-worker
curl http://localhost:18182/health       # retrieval
curl http://localhost:18181/health       # access

# 2. 运行时冒烟测试（验证全链路）
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends
```

---

## 构建与验证

### 单元/集成测试

```bash
# Python 契约包
cd packages/contracts && py -3.14 -m pytest tests/ -v

# Python 服务
cd services/admin         && py -3.14 -m pytest tests/ -v
cd services/workbench-api && py -3.14 -m pytest tests/ -v
cd services/indexing      && py -3.14 -m pytest tests/ -v

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
# 基础模式（允许 stub 回退）
py -3.14 scripts/run_real_runtime_smoke.py

# 严格模式（要求所有真实后端在线）
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends

# 严格模式 + Redis 缓存验证
py -3.14 scripts/run_real_runtime_smoke.py --require-live-backends --require-redis-cache
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
│   ├── MVP_HANDOFF.md          # MVP 交付清单与验证报告
│   └── ...
├── packages/
│   ├── contracts/              # Python 运行时契约包
│   ├── persistence/            # ORM 模型与仓储
│   └── documents/              # 共享文档域逻辑
├── scripts/
│   ├── run_real_runtime_smoke.py   # 真实运行时冒烟测试
│   └── start-services.py           # 一键本地启动所有后端服务
├── services/
│   ├── access/                 # Java：外部查询入口 (REST + MCP)
│   ├── admin/                  # Python：管理控制面
│   ├── indexing/               # Python：解析、分块、索引构建
│   ├── intake-pipeline/        # Python：摄入治理与审批流
│   ├── retrieval/              # Java：混合检索核心
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
2. [MVP 交付清单](docs/MVP_HANDOFF.md)
3. [前端工作台文档](docs/frontend-workbench.md)
4. services/intake-pipeline/intake-pipeline.md
5. services/access/access.md
6. services/retrieval/retrieval.md

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
