# smoke_tests 对外接口契约

smoke_tests **不是一个服务**——它不暴露 HTTP 端点，没有入站/出站请求。它是一组可调用的测试工具和 fixture，供开发者、CI 系统和外部脚本使用。

## 暴露的可调用入口

### pytest 测试用例

| 测试 | 模式 | 说明 |
|------|------|------|
| `test_intake_real_chain.py::test_real_chain_upload_content_reaches_published_state` | in-process | 创建 collection → parser profile → upload → drain chain → 验证 published |
| `test_deployment_smoke.py::TestDeploymentSmoke::test_all_services_healthy` | deployment | 验证所有核心服务 health endpoint 响应 |
| `test_deployment_smoke.py::TestDeploymentSmoke::test_upload_and_status_progression` | deployment | 上传文件并验证状态从 uploading 前进到 parsing 或更远 |
| `test_deployment_smoke.py::TestDeploymentSmoke::test_failed_document_shows_failed_not_uploading` | deployment | 回归：失败任务必须显示 failed 而不是 uploading |
| `test_deployment_smoke.py::TestDeploymentSmoke::test_projection_fields_consistent` | deployment | 有 source_file_id 的任务必须有 intake_job_id |
| `test_deployment_smoke.py::TestDeploymentSmoke::test_no_stuck_uploading_with_source_file` | deployment | 有 source_file_id 的任务不能 stuck 在 uploading |

### conftest.py 暴露的工具函数

这些是供测试用例和其他模块调用的可复用函数：

**`drain_real_chain_for_source_files(source_file_ids, *, max_rounds=40)`**
驱动 split-owner intake chain 到 terminal state。内部创建 IngestPipeline（含 fake converter + fake reviewer），轮流 poll 四个 OutboxDispatcher（orchestrator / conversion / review / publishing）。不返回，成功时 silent，超时时 raise AssertionError。

**`reconcile_workbench_tasks(*, limit=100) -> dict[str, Any]`**
运行 workbench ProjectionReconciler，返回 reconcile 结果。需要在 `drain_real_chain_for_source_files` 之后调用。

### conftest.py 暴露的 fixture（scope=module）

| Fixture | 类型 | 说明 |
|---------|------|------|
| `admin_token` | str | admin JWT（roles: knowledge_admin, platform_admin, tenant: tenant_smoke） |
| `uploader_token` | str | uploader JWT（roles: uploader, allowed_collections: [col_smoke]） |
| `client` | TestClient | FastAPI TestClient 绑定到 combined_app |
| `admin_headers` | dict[str,str] | `{"Authorization": "Bearer {admin_token}"}` |
| `uploader_headers` | dict[str,str] | `{"Authorization": "Bearer {uploader_token}"}` |

### 环境变量契约（conftest.py 设置）

smoke_tests 启动时自动设置以下环境变量。外部脚本可以直接读取 `.verify/runtime/smoke-test.db`。

| 变量 | 值 | 说明 |
|------|----|------|
| `DATABASE_URL` | `sqlite:///{ROOT}/.verify/runtime/smoke-test.db` | 共享 SQLite DB |
| `ADMIN_JWT_SECRET` / `JWT_SECRET` | `smoke-test-secret` | HMAC 签名密钥 |
| `ADMIN_JWT_ALGORITHM` / `JWT_ALGORITHM` | `HS256` | 签名算法 |
| `*_BASE_URL` | `http://testserver/{service}` | 跨服务路由基准 URL |
| `*_SERVICE_URL` | `http://testserver/{service}` | 服务间调用的 URL |
| `ALLOW_LOCAL_FALLBACK_FOR_TESTS` | `true` | 允许本地 fallback |

**禁用的环境变量**：所有 LLM/embedding API key、base URL、model 在 conftest.py 中被 pop 掉，确保 in-process 模式不调用真实模型。

### 部署模式的 CORE_SERVICES 契约

`test_deployment_smoke.py` 定义的服务端口、health endpoint、启动命令和 PYTHONPATH。外部部署脚本（如 `ekb-svc.py`）应复用此映射。

| 服务 | 端口 | Health | cwd |
|------|------|--------|-----|
| document-service | 8006 | `/health` | `services/intake-pipeline/document-service` |
| indexing | 18080 | `/health` | `services/indexing` |
| ingestion-worker | 18088 | `/health` | `services/intake-pipeline/ingestion-worker` |
| conversion-worker | 18089 | `/health` | `services/intake-pipeline/conversion-worker` |
| agent-review-worker | 18090 | `/health` | `services/intake-pipeline/agent-review-worker` |
| approval-service | 18087 | `/health` | `services/intake-pipeline/approval-service` |
| publishing-worker | 18086 | `/health` | `services/intake-pipeline/publishing-worker` |
| workbench-api | 18083 | `/workbench/health` | `services/workbench-api` |
| admin | 18084 | `/health` | `services/admin` |

## 数据模型

### IntakeJobState（terminal states）
`PUBLISHED` / `REJECTED` / `FAILED` / `CANCELLED` / `EXPIRED` / `AWAITING_APPROVAL`

### combined_app mount 布局
```
/                         → admin_app（admin routes embed /admin）
/workbench/*              → workbench_app（_PrefixApp 重新添加 /workbench 前缀）
/internal/events/*        → workbench_api.events.router（直接 include）
/indexing/*               → indexing_app
/documents/*              → document_app
/approval/*               → approval_app
/publishing/*             → publishing_app
```

## 运行方式

```bash
# In-process ASGI 模式（无需外部基础设施）
cd services/smoke_tests
uv run pytest test_intake_real_chain.py -v

# Deployment 模式（需要 PostgreSQL/OpenSearch/Qdrant/Redis）
uv run pytest test_deployment_smoke.py -v --timeout=300

# 外部脚本直接调用 drain 工具
uv run python -c "
from conftest import drain_real_chain_for_source_files, reconcile_workbench_tasks
drain_real_chain_for_source_files(['src_file_01'])
reconcile_workbench_tasks()
"
```
