# Agent 操作规范

## Python 环境

- **包管理器**：uv
- **工作区模式**：uv workspace，根目录 `pyproject.toml` 统一定义所有 workspace members（`packages/*` 和 `services/*`）
- **虚拟环境**：根目录 `.venv`，Python 3.12
- **安装依赖**：在项目根目录执行 `uv sync`
- **运行命令**：所有 Python 命令通过 `uv run` 执行（如 `uv run python`、`uv run pytest`、`uv run uvicorn`）
- **不要**：手动 pip install、编辑 PYTHONPATH、创建额外的 .venv

## 项目结构速查

- **前端**：`apps/web/`（Next.js 16，唯一前端入口）
- **契约**：`contracts/`（跨语言 schema、events、openapi）
- **共享包**：`packages/`（contracts、persistence、documents、ragflow_runtime）
- **服务**：`services/`（access、admin、indexing、intake-pipeline、retrieval、workbench-api）
- **基础设施**：`deploy/`（Docker Compose）
- **上游源码**：`upstream/ragflow/`（RAGFlow 源码分叉，运行时资源依赖）

## 关键纪律

- 契约优先：所有跨服务 API、DTO、事件变更必须先落到 `contracts/`
- 后端缺口可见：HTTP 501 时前端显式展示 `<BackendGap>`，不静默失败
- 真相单一 owner：source_file → document-service，intake_job → ingestion-worker，approval → approval-service，publish → publishing-worker，index → indexing
- chunk 是派生产物：不拥有独立 ACL，可见性继承自文档级治理
