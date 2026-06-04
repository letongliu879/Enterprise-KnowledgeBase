# Intake Pipeline Remediation Plan (Rewrite)

**状态**：执行中  
**目标架构**：只保留 Event-Driven Split Workers；删除 Compat Root 和 Sync In-Process Pipeline。  
**约束**：
- 禁止新增功能；只收敛、删除、显式化。
- 禁止为了通过测试而保留 bypass。
- 每改完一个 Phase 必须跑 targeted tests；禁止直接跑 intake-pipeline 全量测试作为默认验收。

---

## 0. 当前真实状态（已校准）

### 0.1 三套并行系统（必须收敛为一套）

| 系统 | 位置 | 作用 | 处置 |
|---|---|---|---|
| **Compat Root** | `services/intake-pipeline/src/intake_pipeline/main.py` (1105 行) | 初代单体替身，内存字典 + 本地文件系统跑 upload → approval → publish → indexing | **删除业务逻辑，最终只保留 health 或整文件删除** |
| **Sync In-Process Pipeline** | `services/intake-pipeline/ingestion-worker/src/ingestion_worker/pipeline.py:_drain_outbox_until_source_files_terminal()` | ingestion-worker 进程内串行执行 conversion / review / publishing，绕过真实 worker | **删除** |
| **Event-Driven Split Workers** | document-service → FileReady → ingestion-worker → conversion-worker → agent-review-worker → approval-service → publishing-worker → indexing-service | 架构规范和数据模型支持的正式链路 | **保留并强制为唯一路径** |

### 0.2 约定断裂点

| 约定 | 现状 | 断裂后果 |
|---|---|---|
| source_file owner = document-service | document-service 无 `GET /internal/source-files/{id}`；workbench 的 `IntakeClient` 默认读 compat root | workbench 查询 source file 时读的可能是影子系统的数据 |
| intake_job owner = ingestion-worker | ingestion-worker 无 `GET /internal/intake-jobs/{id}`；workbench 读 compat root | 同一 intake job 在正式表和 compat 内存中可能不一致 |
| published_document owner = publishing-worker | publishing-worker 无 `GET /internal/published-documents/{id}`；workbench 读 compat root | 发布状态查询绕过 publishing domain |
| workbench 投影为主读模型 | `task_projection/service.py` 实时 fallback 查询下游；`ProjectionReconciler` 每 5 分钟修复 | projection 不被信任，双保险增加复杂度 |

### 0.3 代码冗余

- **9 个 shim 文件**在 `services/intake-pipeline/ingestion-worker/src/ingestion_worker/` 里用 `sys.modules[__name__] = intake_runtime.xxx` 或纯 re-export 伪装成本地模块。
- `intake_runtime` 已承载核心逻辑（3300+ 行）但未正式工程化为 workspace package。
- `approval-service/review_artifacts.py` 在 `result_ref` 缺失时 fallback 从 `summary_json` 拼装 artifact。
- `packages/persistence` 的 `EventPublisher` 与 `OutboxDispatcher` 已覆盖完整事件模型，但 sync pipeline 让 outbox 事件只在同进程内被消费。

### 0.4 打包与测试断裂

- 子服务 `pyproject.toml` 不在根 workspace members 中。
- 子服务 `requires-python = "==3.14.*"` 与根 `>=3.12` 冲突。
- `ingestion-worker` 依赖不存在的 `reality-rag-ai-clients`。
- 从仓库根 `uv run pytest services/intake-pipeline/document-service/tests` 会 `ModuleNotFoundError: No module named 'document_service'`。

---

## 1. 最终架构目标

只保留一套链路：

```text
[前端 / CLI / Webhook]
    -> workbench-api (只负责 JWT 校验、collection scope、projection 只读)
    -> document-service /upload or /internal/source-files
    -> document-service emits FileReady outbox event
    -> ingestion-worker outbox poller consumes FILE_READY
       -> creates intake_job via OrchestratorService
       -> claims source file via document-service API
       -> emits StageTaskRequested(CONVERSION)
    -> conversion-worker outbox poller consumes StageTaskRequested(CONVERSION)
       -> executes conversion
       -> emits StageCompleted(CONVERSION)
    -> ingestion-worker consumes StageCompleted(CONVERSION)
       -> marks source file CONSUMED
       -> emits StageTaskRequested(AGENT_REVIEW)
    -> agent-review-worker consumes StageTaskRequested(AGENT_REVIEW)
       -> executes review
       -> writes artifact to stable result_ref
       -> emits StageCompleted(AGENT_REVIEW)
    -> ingestion-worker consumes StageCompleted(AGENT_REVIEW)
       -> emits ApprovalRequested
    -> approval-service consumes ApprovalRequested
       -> creates ticket (SYSTEM_DECIDED or PENDING)
       -> emits ApprovalDecided (or ApprovalPending then ApprovalDecided)
    -> ingestion-worker consumes ApprovalDecided
       -> if approve: emits StageTaskRequested(PUBLISHING)
    -> publishing-worker consumes StageTaskRequested(PUBLISHING)
       -> persists document / policy / published_document
       -> submits IndexBuildRequested to indexing-service
       -> emits PublishCompleted
    -> ingestion-worker consumes PublishCompleted
       -> intake_job state = PUBLISHED
       -> emits SourceFileCleanable
    -> document-service cleans source file / object blob
```

关键边界：
- **document-service**：唯一 source file owner；提供读写接口。
- **ingestion-worker / orchestrator**：唯一 intake_job owner；只调度，不执行具体 stage。
- **conversion-worker**：唯一 conversion stage executor。
- **agent-review-worker**：唯一 review artifact 写入方。
- **approval-service**：只读 artifact；唯一 ticket / audit / final_doc_id owner。
- **publishing-worker**：唯一 publish + published_document owner。
- **indexing-service (`services/indexing`)**：唯一 parse snapshot / chunk / index owner。
- **workbench-api**：projection / read-model / UI integration；不得成为任何 owner。

---

## 2. 必须删除的代码清单

### 2.1 Compat Root 业务层（`src/intake_pipeline/`）

删除以下文件或其中全部业务代码：

- `services/intake-pipeline/src/intake_pipeline/main.py`
  - 删除 `EnterDocumentRequest`
  - 删除 `EnterBinaryDocumentRequest`
  - 删除 `ApproveAndPublishRequest`
  - 删除 `SubmitApprovalRequest`
  - 删除 `ApproveTicketRequest`
  - 删除 `IntakeDocumentRecord`
  - 删除 `ApprovalTicketRecord`
  - 删除 `IntakeService`
  - 删除 `EnterBinaryDocumentRequest` 等所有 `/v1/*` 端点
  - 删除 `GET /internal/source-files/{id}`、`GET /internal/intake-jobs/{id}`、`GET /internal/published-documents/{id}`（这些视图要迁移到各自 owner）
  - 保留 `/health` 或整文件删除
- `services/intake-pipeline/src/intake_pipeline/publishing_facade.py`
- `services/intake-pipeline/src/intake_pipeline/lineage.py`
- `services/intake-pipeline/src/intake_pipeline/state_models.py`
- `services/intake-pipeline/src/intake_pipeline/indexing_command_gateway.py`
- `services/intake-pipeline/src/intake_pipeline/_compat.py`

### 2.2 Sync In-Process Pipeline（`ingestion-worker`）

- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/pipeline.py`
  - 删除 `_drain_outbox_until_source_files_terminal()`
  - 删除 `_source_file_jobs_are_terminal()`
  - 删除 `_build_report_for_source_files()` 中基于 stage_result 的二次拼装（该由调用方从数据库读）
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/app_factory.py`
  - 删除 `POST /internal/ingestion/convert`（或保留为仅enqueue入口）
  - 删除 `POST /internal/ingestion/monitor/runs`（或保留为仅enqueue入口）
  - 删除 `MonitoredIngestionService` 在 app_factory 中的绑定（如果 monitor 入口被保留，它只能enqueue，不能 drain）
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/monitor_service.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/monitor_processor.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/monitor_context.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/monitor_models.py`

### 2.3 Ingestion-Worker Shim 文件

以下文件应直接删除，调用方改为 `from intake_runtime.xxx import ...`：

- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/agent_review_cache.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/agent_reviewer.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/orchestrator.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/index_assets.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/pipeline_utils.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/quality_utils.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/stage_task_worker.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/stage_runtime.py` 中除 `run_publishing`/`execute_publishing_task` 外的透传（最终也删除）
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/domains/publishing_domain.py`（ publishing-worker 已有该职责 ）

### 2.4 Smoke Tests 中的 Compat 路径

- `services/smoke_tests/test_mvp_python_chain.py` 中所有调用 `/intake/v1/documents` 和 `/intake/v1/documents/{id}/approve-and-publish` 的测试用例应删除或改写为 real-chain。
- `services/smoke_tests/conftest.py` 中：
  - 删除 `combined_app.mount("/intake", intake_app)`
  - 删除 `httpx` patch 中针对 `intake_pipeline.main` 的特殊处理
  - 删除 `REALITY_RAG_ENABLE_COMPAT_WRITES = "true"` 和 `ALLOW_LOCAL_FALLBACK_FOR_TESTS = "true"`
  - 删除 `drain_real_chain_for_source_files()` 中手工构造的 4 个 `OutboxDispatcher`（改为启动真实 worker apps）

### 2.5 Workbench 中对 Compat Root 的依赖

- `services/workbench-api/src/workbench_api/downstream_clients/intake_client.py`
  - 删除 `create_source_file()`（无调用方且指向错误）
  - 删除 `get_source_file()` / `get_intake_job()` / `get_published_document()`，或改为指向正确服务
- `services/workbench-api/src/workbench_api/config.py`
  - 如果 `intake_base_url` 仍指向 compat root，应删除或重命名。

---

## 3. 分阶段执行计划

### Phase S：工程化基础与测试止血

**目标**：让代码从仓库根可以被正确导入、测试可以安全运行。不解决此阶段，后续验收全部失真。

#### S1 修复子服务打包

**文件**：
- `E:/AI/My-Project/Enterprise KnowledgeBase/pyproject.toml`
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/intake-pipeline/agent-review-worker/pyproject.toml`
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/intake-pipeline/approval-service/pyproject.toml`
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/intake-pipeline/conversion-worker/pyproject.toml`
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/intake-pipeline/document-service/pyproject.toml`
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/intake-pipeline/indexing-service/pyproject.toml`
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/intake-pipeline/ingestion-worker/pyproject.toml`
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/intake-pipeline/publishing-worker/pyproject.toml`

**动作**：
1. 在根 `pyproject.toml` 的 `[tool.uv.workspace].members` 中追加 7 个子服务路径：
   ```toml
   "services/intake-pipeline/agent-review-worker",
   "services/intake-pipeline/approval-service",
   "services/intake-pipeline/conversion-worker",
   "services/intake-pipeline/document-service",
   "services/intake-pipeline/indexing-service",
   "services/intake-pipeline/ingestion-worker",
   "/services/intake-pipeline/publishing-worker",
   ```
2. 在每个子服务 `pyproject.toml` 中追加 package discovery：
   ```toml
   [tool.setuptools.packages.find]
   where = ["src"]
   ```
3. 把所有子服务 `requires-python = "==3.14.*"` 改为 `requires-python = ">=3.12"`。
4. 在 `ingestion-worker/pyproject.toml` 中删除或替换 `reality-rag-ai-clients` 依赖。当前 `packages/` 和 `services/` 下均无此包，应直接移除（代码中亦无可靠引用）。

**验收**：
```bash
uv sync
uv run pytest services/intake-pipeline/document-service/tests -x -q
uv run pytest services/intake-pipeline/approval-service/tests -x -q
uv run pytest services/intake-pipeline/ingestion-worker/tests -x -q
# 以上不再出现 ModuleNotFoundError
```

#### S2 清理 `sys.path.insert` hack

**文件**：
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/smoke_tests/conftest.py:26-36`
- `E:/AI/My-Project/Enterprise KnowledgeBase/services/workbench-api/tests/conftest.py:8`

**动作**：
1. 删除 `smoke_tests/conftest.py` 中所有 `sys.path.insert(0, ...)`。
2. 删除 `workbench-api/tests/conftest.py` 中 `sys.path.insert(0, str(_project_root / "services" / "indexing" / "src"))`。

**验收**：完成 S1 后，测试不再依赖这些 hack 也能 import 通过。

#### S3 修复 TestClient / Lifespan 剩余问题

**文件**：
- `services/admin/tests/conftest.py`（已改，验证）
- `services/admin/tests/test_auth_jwt.py`（已改，验证）
- `services/workbench-api/src/workbench_api/main.py`（已加 `create_app(start_reconciler=...)`，验证 smoke tests 中禁用）
- `services/workbench-api/tests/conftest.py`（已改用 `create_app(start_reconciler=False)`，验证）
- `services/intake-pipeline/ingestion-worker/tests/test_repo_guardrails.py`（已扩展，验证）

**动作**：
1. 确认 smoke tests 启动 combined_app 时 workbench reconciler 被禁用：
   - 在 `smoke_tests/conftest.py` 的 env 设置区（line 59 附近）添加：
     ```python
     os.environ["WORKBENCH_RECONCILE_ENABLED"] = "false"
     ```
2. 确认 guardrail test 覆盖 ingestion-worker 自身。

**验收**：
```bash
uv run pytest services/admin/tests/test_auth.py -x -q
uv run pytest services/workbench-api/tests -x -q
uv run pytest services/intake-pipeline/ingestion-worker/tests/test_repo_guardrails.py -x -q
```

---

### Phase 1：强制 Split Workers，删除 Sync Pipeline

**目标**：让 ingestion-worker 不再在同进程内执行 conversion / review / publishing；所有 stage 必须通过 outbox 派发到对应 worker。

#### 1.1 删除 IngestionPipeline 的 sync drain

**文件**：`services/intake-pipeline/ingestion-worker/src/ingestion_worker/pipeline.py`

**动作**：
1. 删除 `_drain_outbox_until_source_files_terminal()` 方法（lines 248-320 区域）。
2. 删除 `_source_file_jobs_are_terminal()` 方法（lines 322-339 区域）。
3. 简化 `IngestionPipeline.run()`：
   - 保留：创建 upload session / object_blob / source_file（通过 DocumentServiceClient）
   - 删除：对 `_drain_outbox_until_source_files_terminal()` 的调用
   - 返回的 `IngestionJob` 中 `status` 应改为 `"queued"` 或 `"submitted"`，而不是基于已完成 stage 推导的终端状态。
4. 删除 `_build_report_for_source_files()` 中基于 `StageResultModel` 二次拼装 conversion detail 的逻辑。如果调用方需要完整报告，应从数据库查询或由 orchestrator 事件驱动更新 projection。

#### 1.2 删除或禁用 monitor 入口

**文件**：`services/intake-pipeline/ingestion-worker/src/ingestion_worker/app_factory.py`

**动作**：
1. 删除 `include_monitor_routes=True` 参数和相关 `if include_monitor_routes:` 分支。
2. 删除 `POST /internal/ingestion/monitor/runs` 端点。
3. 保留 `POST /internal/ingestion/convert` 但**仅作为创建 source file 并返回的入口**，不得 drain。
4. 删除 `monitored_ingestion_service_factory` 相关 state 绑定。

**相关删除文件**：
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/monitor_service.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/monitor_processor.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/monitor_context.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/monitor_models.py`

#### 1.3 确保 outbox 事件能驱动真实 worker

**文件**：
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/outbox_deliver.py`
- `services/intake-pipeline/conversion-worker/src/conversion_worker/main.py`
- `services/intake-pipeline/agent-review-worker/src/agent_review_worker/main.py`
- `services/intake-pipeline/publishing-worker/src/publishing_worker/main.py`

**动作**：
1. 检查 ingestion-worker 的 outbox deliver 是否在消费 `StageTaskRequested` 事件时转发给 workbench。当前代码过滤掉了 `StageTaskRequested`：
   ```python
   should_process=lambda event: event.event_type != "StageTaskRequested"
   ```
   这是对的（worker 自己消费 StageTaskRequested）。但需要确认生产部署时各 worker 的后台 poller 确实能收到这些事件。
2. 每个 worker 的 `create_app(start_background_poller=True)` 在 lifespan 中启动 outbox poller，只消费自己 stage 的 `StageTaskRequested`。
3. 验证 worker 的 `execute_conversion_task`、`execute_review_task`、`execute_publishing_task` 不被 ingestion-worker 调用。

#### 1.4 改写 real-chain smoke

**文件**：`services/smoke_tests/conftest.py`

**动作**：
1. `drain_real_chain_for_source_files()` 当前手工构造 4 个 `OutboxDispatcher` 并直接调用 `execute_*_task()`。这**测的是函数而不是 worker HTTP 边界**。
2. 新实现应：
   - 启动 `document_app`、`ingestion_app`、`conversion_app`、`review_app`、`approval_app`、`publishing_app` 的 `TestClient(create_app(start_background_poller=False))`
   - 或者，更简单地：通过 `httpx` 直接 POST 到各 worker 的 `/internal/conversion/run`、`/internal/review/run`、`/internal/publishing/persist` 来驱动
   - 但推荐**让 outbox 自己驱动**：在测试中显式调用 `OutboxDispatcher` 推动事件，并验证每个 worker 的 poller 正确处理
3. 关键是：测试必须证明 conversion-worker / agent-review-worker / publishing-worker **被实际调用**，而不是 ingestion-worker 内部执行。

**验收标准**：
- 完成 1.1-1.3 后，`
  - `test_intake_real_chain.py` 仍能通过，且 `conversion_worker`、`agent_review_worker`、`publishing_worker` 的日志/数据库记录中有真实处理痕迹。
  - 在 `drain_real_chain_for_source_files()` 执行期间，禁止直接调用 `execute_conversion_task` / `execute_review_task` / `execute_publishing_task`。

---

### Phase 2：修复 Workbench-API 与 Owner 约定

**目标**：workbench 不再依赖 compat root 读取 source file / intake job / published document。

#### 2.1 在 document-service 增加 source file 只读接口

**文件**：`services/intake-pipeline/document-service/src/document_service/main.py`

**动作**：
1. 新增端点：
   ```python
   @app.get("/internal/source-files/{source_file_id}")
   async def get_source_file(source_file_id: str) -> dict:
       # 返回 source_file + 关联 intake_job_id（只读查询）
   ```
2. 实现应查询 `SourceFileRepository`、`IntakeJobRepository`，返回与 compat root 当前视图兼容的字段：
   ```json
   {
     "source_file_id": "src_...",
     "upload_id": "upl_...",
     "tenant_id": "...",
     "collection_id": "...",
     "filename": "...",
     "mime_type": "...",
     "size_bytes": 0,
     "state": "READY",
     "intake_job_id": "job_..." | null,
     "scan_verdict": "clean" | null,
     "created_at": "...",
     "updated_at": "..."
   }
   ```
3. `tenant_id` 通过 `collection_id` 关联 `CollectionRepository` 获取。

#### 2.2 在 ingestion-worker 增加 intake job 只读接口

**文件**：`services/intake-pipeline/ingestion-worker/src/ingestion_worker/app_factory.py`

**动作**：
1. 新增端点：
   ```python
   @app.get("/internal/intake-jobs/{intake_job_id}")
   async def get_intake_job(intake_job_id: str) -> dict:
   ```
2. 查询 `IntakeJobRepository`、`StageResultModel`（获取 parse_snapshot_id）、`PublishedDocumentRepository`（获取 published_document_id）。
3. 返回字段：
   ```json
   {
     "intake_job_id": "job_...",
     "source_file_id": "src_...",
     "tenant_id": "...",
     "collection_id": "...",
     "state": "PUBLISHED",
     "current_stage": "...",
     "parse_snapshot_id": "pss_..." | null,
     "ticket_id": "apv_..." | null,
     "published_document_id": "pub_..." | null,
     "final_doc_id": "doc_..." | null,
     "error_message": null,
     "created_at": "...",
     "updated_at": "..."
   }
   ```

#### 2.3 在 publishing-worker 增加 published document 只读接口

**文件**：`services/intake-pipeline/publishing-worker/src/publishing_worker/main.py`

**动作**：
1. 新增端点：
   ```python
   @app.get("/internal/published-documents/{published_document_id}")
   async def get_published_document(published_document_id: str) -> dict:
   ```
2. 查询 `PublishedDocumentRepository`，返回：
   ```json
   {
     "published_document_id": "pub_...",
     "final_doc_id": "doc_...",
     "source_file_id": "src_...",
     "intake_job_id": "job_...",
     "tenant_id": "...",
     "collection_id": "...",
     "state": "PUBLISHED",
     "version": 1,
     "created_at": "...",
     "updated_at": "..."
   }
   ```
   `source_file_id` 和 `intake_job_id` 通过 `final_doc_id` 关联 `IntakeJobRepository` 获取。

#### 2.4 重构 workbench 的 downstream clients

**文件**：
- `services/workbench-api/src/workbench_api/config.py`
- `services/workbench-api/src/workbench_api/downstream_clients/intake_client.py`
- 新增：`services/workbench-api/src/workbench_api/downstream_clients/document_service_client.py`（如果当前只有 upload）
- 新增：`services/workbench-api/src/workbench_api/downstream_clients/ingestion_client.py`
- 新增：`services/workbench-api/src/workbench_api/downstream_clients/publishing_client.py`

**动作**：
1. `config.py`：
   - 删除 `intake_base_url`（它指向 compat root）。
   - 保留并明确：
     - `document_service_base_url`
     - `ingestion_base_url`
     - `approval_base_url`
     - `publishing_base_url`
     - `indexing_base_url`
2. `intake_client.py`：
   - 删除 `create_source_file()`（无调用方且端点已不存在）。
   - 删除 `get_source_file()` / `get_intake_job()` / `get_published_document()`，或者保留为 orchestrator/compat 专用（但不允许默认路径使用）。
3. 新建/扩展：
   - `DocumentServiceClient`：增加 `get_source_file(source_file_id)` 调用 `GET /internal/source-files/{id}`。
   - 新建 `IngestionClient`：提供 `get_intake_job(intake_job_id)` 调用 `GET /internal/intake-jobs/{id}`。
   - 新建 `PublishingClient`：提供 `get_published_document(published_document_id)` 调用 `GET /internal/published-documents/{id}`。
4. `__init__.py` 暴露新的 clients。

#### 2.5 修改 workbench 查询代码使用新 clients

**文件**：
- `services/workbench-api/src/workbench_api/task_projection/service.py`
- `services/workbench-api/src/workbench_api/source_files/routes.py`
- `services/workbench-api/src/workbench_api/workspace/service.py`（如果用到相关接口）

**动作**：
1. `task_projection/service.py`：
   - 注入 `DocumentServiceClient`、`IngestionClient`、`PublishingClient`。
   - `_derive_task_view()` 中：
     - `self._intake_client.get_source_file(...)` → `self._document_client.get_source_file(...)`
     - `self._intake_client.get_intake_job(...)` → `self._ingestion_client.get_intake_job(...)`
     - `self._intake_client.get_published_document(...)` → `self._publishing_client.get_published_document(...)`
2. `source_files/routes.py`：把 `IntakeClient` 替换为 `DocumentServiceClient`。

#### 2.6 修复 workbench tests

**文件**：`services/workbench-api/tests/conftest.py`

**动作**：
1. 修改下游 URL monkeypatch：
   - `config.document_service_base_url = "http://localhost:8006"` 等保持不变，但要确保测试中有 document-service / ingestion / publishing 的 mock 或真实挂载。
2. 如果 workbench tests 不启动真实 intake-pipeline 服务，则需要 mock 新的 clients。

**验收标准**：
- 完成 Phase 2 后，workbench-api 代码中**不再 import IntakeClient 来读取 source file / intake job / published document**。
- `grep -n "intake_base_url\|INTAKE_BASE_URL" services/workbench-api/src/` 无结果（或明确标记为 legacy-only）。
- `test_intake_real_chain.py` 仍能通过。

---

### Phase 3：退役并删除 Compat Root

**目标**：`src/intake_pipeline/` 下的业务代码全部删除；任何对 `/intake/v1/*` 和 `/intake/internal/source-files` 的调用消失。

#### 3.1 删除 `intake_pipeline/main.py` 业务代码

**文件**：`services/intake-pipeline/src/intake_pipeline/main.py`

**动作**：
1. 删除所有 Pydantic request/record 模型。
2. 删除 `IntakeService` 及其方法。
3. 删除所有 `/v1/*` 端点：
   - `POST /v1/documents`
   - `GET /v1/documents/{source_file_id}`
   - `POST /v1/documents/{source_file_id}/approval-tickets`
   - `GET /v1/approval-tickets/{ticket_id}`
   - `POST /v1/approval-tickets/{ticket_id}/approve`
   - `POST /v1/documents/{source_file_id}/approve-and-publish`
4. 删除所有 `/internal/*` 只读端点（已迁移到各自 owner）：
   - `GET /internal/source-files/{source_file_id}`
   - `GET /internal/intake-jobs/{intake_job_id}`
   - `GET /internal/published-documents/{published_document_id}`
   - `GET /internal/lineage/source-files/{source_file_id}`
   - `GET /internal/lineage/traces/{trace_id}`
5. 保留 `/health` 端点；或如果整服务不再挂载，直接删除文件。

#### 3.2 删除辅助模块

**文件**：
- `services/intake-pipeline/src/intake_pipeline/publishing_facade.py` — 整文件删除
- `services/intake-pipeline/src/intake_pipeline/lineage.py` — 整文件删除
- `services/intake-pipeline/src/intake_pipeline/state_models.py` — 整文件删除
- `services/intake-pipeline/src/intake_pipeline/indexing_command_gateway.py` — 整文件删除
- `services/intake-pipeline/src/intake_pipeline/_compat.py` — 整文件删除

#### 3.3 清理 smoke tests 中的 compat 挂载

**文件**：`services/smoke_tests/conftest.py`

**动作**：
1. 删除 `import intake_pipeline.main as _intake_main` 及相关 `httpx` patch。
2. 删除 `combined_app.mount("/intake", intake_app)`。
3. 删除环境变量：
   - `REALITY_RAG_ENABLE_COMPAT_WRITES = "true"`
   - `ALLOW_LOCAL_FALLBACK_FOR_TESTS = "true"`
   - `REALITY_RAG_INTAKE_RUNTIME_DIR`
4. 更新 `test_mvp_python_chain.py` 中依赖 `/intake/v1/documents` 的测试；如果无法快速改写，直接删除该文件或标记为 skip（因为它测的是将被删除的 compat root）。

#### 3.4 清理 workbench config 中的 legacy URL

**文件**：`services/workbench-api/src/workbench_api/config.py`

**动作**：
1. 删除 `intake_base_url` 字段（如果完成 Phase 2 后已无引用）。

**验收标准**：
- `grep -rn "/v1/documents\|/v1/approval-tickets\|approve-and-publish" services/ packages/ apps/web/src/` 无结果。
- `grep -rn "intake_pipeline.main\|from intake_pipeline import" services/ packages/` 无业务引用（仅可能 tests 中残留，一并清理）。
- `src/intake_pipeline/main.py` 行数 < 50（仅 health）或文件不存在。

---

### Phase 4：工程化 intake_runtime 并清理 shim

**目标**：`intake_runtime` 成为正式的 workspace package；ingestion-worker 不再假装自己有本地实现。

#### 4.1 将 intake_runtime 声明为 workspace package

**文件**：
- `E:/AI/My-Project/Enterprise KnowledgeBase/pyproject.toml`
- `services/intake-pipeline/pyproject.toml`

**动作**：
1. 在根 `pyproject.toml` 新增 workspace member：
   ```toml
   "packages/intake_runtime",
   ```
   或等效地把 `services/intake-pipeline/src/intake_runtime` 作为 editable 包暴露。
2. 方案选择（二选一，推荐 A）：
   - **A**：在 `services/intake-pipeline/pyproject.toml` 中声明 `intake_runtime` 为 package（当前 `tool.setuptools.packages.find.where = ["src"]` 已经会包含它，所以只要确保根 workspace 正确解析即可）。
   - **B**：把 `src/intake_runtime` 移到 `packages/intake_runtime/src/intake_runtime` 作为独立 package。
3. 无论哪种方案，目标是：所有 worker 可以通过 `from intake_runtime.xxx import ...` 正常 import，不需要 `sys.path.insert`。

#### 4.2 删除 ingestion-worker 的 shim 文件

**文件**：
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/agent_review_cache.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/agent_reviewer.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/orchestrator.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/index_assets.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/pipeline_utils.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/quality_utils.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/stage_task_worker.py`

**动作**：整文件删除。

#### 4.3 更新 ingestion-worker 中的 import

**文件**：
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/pipeline.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/outbox_deliver.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/app_factory.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/job_event_flow.py`
- 其他 import 了上述 shim 的文件

**动作**：
1. 把 `from ingestion_worker.agent_review_cache import ...` 改为 `from intake_runtime.agent_review_cache import ...`。
2. 把 `from ingestion_worker.orchestrator import ...` 改为 `from intake_runtime.orchestrator import ...`。
3. 以此类推。

#### 4.4 处理 stage_runtime adapter

**文件**：`services/intake-pipeline/ingestion-worker/src/ingestion_worker/stage_runtime.py`

**动作**：
1. 当前文件大部分是 `from intake_runtime.stage_runtime import ...` 的透传。
2. 删除纯透传符号，直接让调用方从 `intake_runtime.stage_runtime` import。
3. 特殊处理：
   - `run_publishing()` 和 `execute_publishing_task()` 因为注入了 `persist_fn=persist_document_and_policy`，暂时保留。
   - 但该 `persist_document_and_policy` 来自 `ingestion_worker.domains.publishing_domain`，最终应改到 publishing-worker 的公共 helper（见 4.5）。

#### 4.5 统一 publishing persistence helper

**文件**：
- `services/intake-pipeline/src/intake_runtime/publishing_persistence.py`
- `services/intake-pipeline/publishing-worker/src/publishing_worker/publishing_domain.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/domains/publishing_domain.py`

**动作**：
1. `intake_runtime.publishing_persistence.persist_document_and_policy()` 是所有 publishing 事实写入的**唯一实现**。
2. `publishing_worker.publishing_domain.persist_document_and_policy()` 已经是对 `intake_runtime.publishing_persistence.persist_document_and_policy()` 的合法委托。
3. `ingestion_worker.domains.publishing_domain.persist_document_and_policy()` 只用于 ingestion-worker 的 sync pipeline；删除该文件和对应 adapter。
4. 如果 `intake_runtime.stage_runtime.execute_publishing_task()` 需要 `persist_fn`，默认使用 `intake_runtime.publishing_persistence.persist_document_and_policy`。

**验收标准**：
- `find services/intake-pipeline/ingestion-worker/src/ingestion_worker -name "*.py"` 后只剩：
  - `__init__.py`
  - `app_factory.py`
  - `document_service_client.py`
  - `indexing_service.py`
  - `job_event_flow.py`
  - `main.py`
  - `outbox_deliver.py`
  - `pipeline.py`
  - `stage_runtime.py`（如果保留 publishing adapter）
- 所有 `from ingestion_worker.xxx import yyy` 不再指向 shim 模块。

---

### Phase 5：Artifact 边界收口

**目标**：`approval-service` 只从稳定的 `result_ref` 读取 artifact，不再 fallback 组装。

#### 5.1 agent-review-worker 必须写入真实 artifact

**文件**：`services/intake-pipeline/src/intake_runtime/stage_runtime.py`

**动作**：
1. 检查 `execute_review_task()` 调用链：
   - `execute_review_task()` → `run_review()` → `run_review_stage()` → `get_agent_reviewer().review()`
2. 确保 review 结果写入 `stage_results.result_ref`，而不是只写 `summary_json`。
3. 如果当前 `result_ref` 为空，修改 `execute_review_task()` 在成功后：
   - 把 `AgentReview` + artifact envelope 序列化为 JSON
   - 写入 deterministic path（如 `s3://.../artifacts/{intake_job_id}/agent_review.json` 或本地 runtime 目录）
   - 更新 `StageResultModel.result_ref = path`
4. artifact envelope 必须包含：
   ```json
   {
     "review_run_id": "...",
     "intake_job_id": "...",
     "source_file_id": "...",
     "parse_snapshot_id": "...",
     "artifact_version": "v1",
     "review_model": "...",
     "prompt_version": "...",
     "artifact_schema_version": "v2",
     "generated_at": "...",
     "agent_review": { "anchored_findings": [...], ... }
   }
   ```

#### 5.2 approval-service 删除 fallback 组装

**文件**：`services/intake-pipeline/approval-service/src/approval_service/review_artifacts.py`

**动作**：
1. 修改 `load_review_artifact_payload(session, intake_job_id)`：
   ```python
   if row is None:
       return None
   if row.result_ref:
       path = Path(row.result_ref)
       if path.exists() and path.is_file():
           return json.loads(path.read_text(encoding="utf-8"))
   # 删除以下 fallback：
   # review_summary = row.summary_json or {}
   # review_context = review_summary.get("review_context", {}) ...
   # return { "review_run_id": ..., "agent_review": ..., ... }
   return None
   ```
2. 调用方（`get_agent_review_internal`）在 payload 为 None 时返回 404，而不是 fallback 组装。

#### 5.3 删除 `summary_json` 中的 artifact 语义滥用

**动作**：
1. 明确 `stage_results.summary_json` 只用于**简短摘要**（如 `conversion_status`、`preliminary_doc_id`）。
2. 不要把完整的 `agent_review` 或 `review_context` 塞进 `summary_json` 作为 artifact 传输通道。
3. 如果现有代码依赖 summary_json 中的 `review_context`，一并改到读 `result_ref`。

#### 5.4 测试 artifact 边界

**文件**：`services/intake-pipeline/approval-service/tests/test_*.py`

**动作**：
1. 新增/修改测试：
   - `anchored_findings = []` 时返回 200，findings 为空数组。
   - `anchored_findings` 有 1 条时正确返回。
   - `anchored_findings` 有多条时正确去重/返回。
   - `result_ref` 缺失时返回 404，不带 fallback 数据。

**验收标准**：
- `approval_service/review_artifacts.py` 中不再出现 `review_summary.get("review_context", {})` 之类的 fallback 逻辑。
- `agent-review-worker` 写入的 artifact 文件能通过 `approval-service` `/internal/tickets/{ticket_id}/agent-review` 原样读出。

---

### Phase 6：投影与 reconciler 决策

**目标**：明确 workbench 投影是主读模型还是实时查询是主读模型；禁止双保险。

#### 6.1 决策

**选项 A（推荐）**：projection 是主读模型
- 删除 `ProjectionReconciler` 的后台循环。
- 删除 `task_projection/service.py` 中实时 fallback 查下游的逻辑。
- 所有 owner 服务必须通过 `/internal/events/{service}` 把变更事件推给 workbench。
- `is_stale` 字段保留用于调试，但不应成为常规修复路径。

**选项 B**：保留 reconciler 作为修复机制
- 定义明确的 `is_stale = true` 触发条件（如事件处理失败、超过 N 分钟未更新）。
- projection 写入路径必须优先，reconciler 只在异常后触发。
- 在 `task_projection/service.py` 中只有在 projection 不存在或 `is_stale=true` 时才查询下游。

**本 plan 推荐选项 A**。理由是：如果事件链路不可靠，应该修复事件链路，而不是靠后台轮询掩盖。

#### 6.2 实施（选项 A）

**文件**：
- `services/workbench-api/src/workbench_api/main.py`
- `services/workbench-api/src/workbench_api/projections/reconciler.py`
- `services/workbench-api/src/workbench_api/task_projection/service.py`

**动作**：
1. `main.py`：删除 lifespan 中对 `reconciliation_loop()` 的启动；保留 `create_app(start_reconciler=False)` 参数但 deprecate。
2. `reconciler.py`：保留 `ProjectionReconciler` 类用于显式手动修复，但删除 `reconciliation_loop()` 的 `while True`。
3. `task_projection/service.py`：删除 `_derive_task_view()` 中实时查询 `intake_client`、`approval_client`、`indexing_client` 的 fallback 分支。只从 projection repository 读取。
4. 更新 workbench tests 中的 fixture：`create_app(start_reconciler=False)`。

#### 6.3 确保事件链路完整

**文件**：
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/outbox_deliver.py`
- `services/intake-pipeline/approval-service/src/approval_service/approval_domain.py`

**动作**：
1. 检查 ingestion-worker 的 `_forward_event_to_workbench()` 是否覆盖了所有需要投影的事件类型。
2. 检查 approval-service 的 `_publish_pending_event()` / `_publish_decided_event()` 是否正确 forward。
3. 确认 workbench `events/routes.py` 的 adapter 能把这些事件转为 `ProjectionEvent`。

**验收标准**：
- workbench-api 启动后不再运行 `reconciliation_loop`。
- `task_projection/service.py` 中不再直接调用 `self._intake_client.get_*()`、`self._approval_client.get_*()`、`self._indexing_client.get_*()`。
- workbench tests 仍能通过（需要提前确保事件 forward 链路完整）。

---

## 4. 验收标准总表

| Phase | 验收项 | 验证命令 |
|---|---|---|
| S | 根 `uv run pytest services/intake-pipeline/document-service/tests -x -q` 通过 | 命令执行 |
| S | 根 `uv run pytest services/intake-pipeline/approval-service/tests -x -q` 通过 | 命令执行 |
| S | 根 `uv run pytest services/intake-pipeline/ingestion-worker/tests/test_repo_guardrails.py -x -q` 通过 | 命令执行 |
| S | `services/smoke_tests/conftest.py` 中无 `sys.path.insert` | `grep -n "sys.path.insert"` |
| 1 | `pipeline.py` 中无 `_drain_outbox_until_source_files_terminal` | `grep -n "_drain_outbox"` |
| 1 | `app_factory.py` 中无 monitor routes | `grep -n "monitor/runs"` |
| 1 | real-chain smoke 通过，且 worker 日志/DB 证明真实 worker 被调用 | 运行 `test_intake_real_chain.py` |
| 2 | document-service 有 `GET /internal/source-files/{id}` | 看路由 |
| 2 | ingestion-worker 有 `GET /internal/intake-jobs/{id}` | 看路由 |
| 2 | publishing-worker 有 `GET /internal/published-documents/{id}` | 看路由 |
| 2 | workbench `task_projection/service.py` 使用新的 document/ingestion/publishing clients | `grep -n "IntakeClient" services/workbench-api/src/workbench_api/task_projection/` |
| 3 | `grep -rn "/v1/documents\|/v1/approval-tickets\|approve-and-publish" services/ packages/ apps/web/src/` 无结果 | grep |
| 3 | `src/intake_pipeline/main.py` 行数 < 50 或文件不存在 | `wc -l` |
| 3 | smoke tests 不再 mount `/intake` 也不再启用 compat writes | 看 `conftest.py` |
| 4 | ingestion-worker 只剩核心文件（见上文列表） | `find` |
| 4 | 所有 `from ingestion_worker.xxx` 的 import 不再指向已删除 shim | `grep -rn "from ingestion_worker" services/intake-pipeline/` |
| 4 | `intake_runtime` 可以从仓库根正常 import | `uv run python -c "from intake_runtime import orchestrator"` |
| 5 | `approval_service/review_artifacts.py` 无 fallback 组装 | `grep -n "summary_json" services/intake-pipeline/approval-service/src/approval_service/review_artifacts.py` |
| 5 | agent-review-worker 写入 `result_ref` | 看 `stage_runtime.execute_review_task` |
| 5 | approval-service `/internal/tickets/{id}/agent-review` 在 result_ref 缺失时返回 404 | 测试 |
| 6 | workbench-api lifespan 不启动 reconciler | 看 `main.py` |
| 6 | `task_projection/service.py` 不直接 fallback 查下游 | grep |

---

## 5. 禁止事项

1. **禁止保留 bypass**：任何“为了测试先留着”的 compat 入口、sync drain、fallback 组装都必须显式标记为 `TODO(delete-compat)` 并在同一 Phase 内删除。
2. **禁止新增 owner 职责到 workbench-api**：workbench 只能做 projection、adapter、UI integration。
3. **禁止直接跑 intake-pipeline 全量测试作为默认验收**：必须按上表跑 targeted tests。
4. **禁止把 `intake_runtime` 的共享逻辑再复制一份到 ingestion-worker**：所有新代码直接 import `intake_runtime.xxx`。
5. **禁止用 `summary_json` 传递 artifact**：artifact 必须走 `result_ref`。

---

## 6. 执行顺序建议

**必须严格按以下顺序执行**：

1. **Phase S**：不完成，后续全部失真。
2. **Phase 2**（修复 workbench 查询接口）：必须在 Phase 3 之前，否则删除 compat root 后 workbench 会 404。
3. **Phase 1**（强制 split）+ **Phase 4**（清理 shim）：可并行，但建议先做 Phase 1（删除 sync pipeline）再做 Phase 4（清理不会重新引入 sync pipeline）。
4. **Phase 3**（删除 compat root）：必须在 Phase 2 完成后。
5. **Phase 5**（artifact 边界）：可以在 Phase 1-4 稳定后做。
6. **Phase 6**（reconciler）：最后做，因为依赖事件链路已完整。

---

## 7. 附录：关键文件速查

| 职责 | 文件路径 |
|---|---|
| Compat Root 主文件 | `services/intake-pipeline/src/intake_pipeline/main.py` |
| Sync Pipeline drain | `services/intake-pipeline/ingestion-worker/src/ingestion_worker/pipeline.py:248-339` |
| Ingestion worker app factory | `services/intake-pipeline/ingestion-worker/src/ingestion_worker/app_factory.py` |
| Outbox deliver | `services/intake-pipeline/ingestion-worker/src/ingestion_worker/outbox_deliver.py` |
| Document service | `services/intake-pipeline/document-service/src/document_service/main.py` |
| Approval service | `services/intake-pipeline/approval-service/src/approval_service/main.py` |
| Approval artifact | `services/intake-pipeline/approval-service/src/approval_service/review_artifacts.py` |
| Publishing worker | `services/intake-pipeline/publishing-worker/src/publishing_worker/main.py` |
| Publishing persistence | `services/intake-pipeline/src/intake_runtime/publishing_persistence.py` |
| Agent reviewer | `services/intake-pipeline/src/intake_runtime/agent_reviewer.py` |
| Stage runtime | `services/intake-pipeline/src/intake_runtime/stage_runtime.py` |
| Workbench config | `services/workbench-api/src/workbench_api/config.py` |
| Workbench intake client | `services/workbench-api/src/workbench_api/downstream_clients/intake_client.py` |
| Workbench task projection | `services/workbench-api/src/workbench_api/task_projection/service.py` |
| Workbench reconciler | `services/workbench-api/src/workbench_api/projections/reconciler.py` |
| Smoke conftest | `services/smoke_tests/conftest.py` |
| Real-chain smoke | `services/smoke_tests/test_intake_real_chain.py` |
| MVP compat smoke | `services/smoke_tests/test_mvp_python_chain.py` |
| Root pyproject | `E:/AI/My-Project/Enterprise KnowledgeBase/pyproject.toml` |

---

*本方案重写自原 INTAKE_PIPELINE_REMEDIATION_PLAN.md，按当前代码真实状态校准。执行时必须逐项验收，禁止跳过。*
