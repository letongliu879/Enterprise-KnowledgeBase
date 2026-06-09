# scripts — 开发运维脚本

## 概述

| 脚本 | 用途 |
|------|------|
| `ekb-svc.py` | 服务管理器：启动/停止/重启/状态/日志 所有微服务 |
| `ekb_smoke_test.py` | 独立全链路 smoke 测试 |
| `ekb_e2e_test.py` | 完整 E2E 测试 |
| `ekb_e2e_full.py` | 完整数据集 E2E 测试 |
| `run_real_runtime_smoke.py` | 真实运行时 smoke 测试 |
| `ekb_svc_utils.py` | 工具函数（JDBC URL 转换等），被 `ekb-svc.py` 导入 |

## ekb-svc.py — 服务管理器

### 职责

本地开发时一次性启动所有微服务并保活。**不是生产级进程管理器**，不做跨机器管理。

### 用法

```bash
uv run python scripts/ekb-svc.py start          # 启动全部
uv run python scripts/ekb-svc.py start --python # 仅 Python 服务
uv run python scripts/ekb-svc.py start --java   # 仅 Java 服务
uv run python scripts/ekb-svc.py start --watch  # 带 --reload（Python 热重载）
uv run python scripts/ekb-svc.py stop           # 停止全部
uv run python scripts/ekb-svc.py status         # 查看全部状态
uv run python scripts/ekb-svc.py logs <name>    # 查看某服务日志
uv run python scripts/ekb-svc.py restart <name> # 重启某服务
uv run python scripts/ekb-svc.py build          # 构建 Java 服务
```

### 启动顺序

`_topo_sort()` 按 `depends_on` 拓扑排序，同一层的服务**并行**启动：

| 层 | 服务 |
|----|------|
| 0 | admin, indexing, document-service, retrieval |
| 1 | publishing-worker, approval-service, agent-review-worker, conversion-worker, access |
| 2 | ingestion-worker |
| 3 | workbench-api |

### 健康检查机制

`_health_check()` 分两阶段：
1. **端口可达** — TCP connect 到 `127.0.0.1:{port}`，超时 `health_timeout`（默认 60s）
2. **HTTP 200** — `GET {health_path}` 返回 200

健康检查失败 → 进程被 kill + 输出最后 30 行日志 → 后续由 `_check_services` 重试。

### 保活 (Supervisor 循环)

`Supervisor._check_services()` 每秒扫描一次：

- **进程退出** (`handle.proc.poll() != None`) → 记录到 supervisor.log → 指数退避重试（最多 5 次，1s/2s/4s/8s/16s）
- **句柄丢失但 PID 存在** → 对其做 health check，不健康则 kill + 重启
- **句柄丢失且 PID 不存在** → 视为静默退出，同上重启
- **超出最大重试次数** → 放弃，不阻塞其他服务

### Windows 特有行为

- 使用 `_WinJobObject`（`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`）管理子进程生命周期
- Supervisor 退出时（Ctrl+C / 异常）→ Job Object 关闭 → **所有子进程被 OS 立即杀死**
- `_kill_process_on_port()` 通过 `netstat -ano` 查找端口占用进程

### 日志

| 位置 | 内容 |
|------|------|
| `tmp/services/{name}.out.log` | 服务 stdout |
| `tmp/services/{name}.err.log` | 服务 stderr |
| `tmp/services/{name}.build.out.log` | Maven 构建 stdout |
| `tmp/services/{name}.build.err.log` | Maven 构建 stderr |
| `tmp/services/supervisor.log` | Supervisor 关键事件（crash/restart/giveup） |

日志自动轮转：10MB → .log.1 → .log.2 → .log.3。

### 环境变量注入

`_service_env_overrides()` 为各服务注入运行时环境变量：

| 服务 | 注入的变量 |
|------|-----------|
| ingestion-worker | `DOCUMENT_SERVICE_URL`, `APPROVAL_SERVICE_URL`, `PUBLISHING_WORKER_URL`, `INDEXING_SERVICE_URL` |
| indexing | `RETRIEVAL_SERVICE_URL` |
| conversion-worker | `INDEXING_SERVICE_URL` |
| agent-review-worker / publishing-worker | `REALITY_RAG_SIDECAR_DIR` |
| workbench-api | `INTAKE_BASE_URL`, `DOCUMENT_SERVICE_BASE_URL` |

Java 服务自动从 `.env` 读取 `DATABASE_URL` 并通过 `_convert_to_jdbc_url()` 转为 JDBC 格式。

### 已知约束 / 常见问题

1. **端口冲突** — 如果 18080-18090 或 8006 已被占用，启动会重试 3 次后放弃。先 `stop` 或手动释放端口。
2. **内存压力** — Java 服务限制 `-Xmx512m`，Python 服务每个约 100-200MB。全部启动约需 3-4GB 可用内存。内存不足时 OS 可能随机杀进程。
3. **第一次启动慢** — Java 服务需要 Maven 构建（下载依赖），Python 服务需要 `uv sync`。`start` 命令会自动检测并构建。
4. **supervisor.log 是唯一 crash 记录** — 如果服务在健康检查**之后**崩溃，crash 事件写入 supervisor.log。其他日志只记录 stdout/stderr。
5. **Windows Job Object** — Supervisor 如果被 `taskkill /F` 暴力杀掉，子进程也会立即全部死亡。建议用 `ekb-svc.py stop` 正常关闭。

### 稳定性保障（当前修复列表）

| 修复 | 说明 |
|------|------|
| Java 内存限制 | retrieval/access 加 `-Xmx512m`，防止 OOM 杀进程 |
| 健康检查后清理 | 失败时立即 kill 进程并清理，不留孤儿 |
| Supervisor 日志 | 所有 crash/restart/giveup 事件写入 `tmp/services/supervisor.log` |
| 端口重试 | 端口占用时最多重试 3 次（`_kill_process_on_port` + sleep 2s） |
| 孤儿进程检测 | handle=None 但 PID 存活时做 health check，不健康则重启 |
| 异常兜底 | `_check_services` 和 `run()` 循环有 try/except，不因未捕获异常崩溃 |

## Smoke / E2E 测试

```bash
uv run python scripts/ekb_smoke_test.py                # 独立全链路 smoke
uv run python scripts/run_real_runtime_smoke.py         # 真实运行时 smoke
uv run python scripts/ekb_e2e_test.py                   # E2E 测试
uv run python scripts/ekb_e2e_full.py                   # 完整数据集 E2E
```

所有测试脚本要求基础设施（PostgreSQL / OpenSearch / Qdrant / Redis）已启动。Smoke 测试会自动启动所需服务，E2E 测试假设所有服务已运行。
