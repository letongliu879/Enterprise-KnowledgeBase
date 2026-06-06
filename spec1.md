# Spec: 全链路 Bug 修复与验证 (2026-06-06 ~ 2026-06-07)

## 用户决策

1. **不修修补补** — 一次性修完所有根因再验证，不留技术债
2. **不用 mock 测试糊弄** — 必须用真实 API + MCP 调用验证，通过 Access 服务检索
3. **用真实数据集文档** — 从 `.verify/runtime/intake-real-smoke/` 取 docx 文件，不能自己造 md
4. **部署级测试必须启动真实服务** — 不能用 in-process mock
5. **Agent Review 卡住 → 人工审批通过绕过** — 通过 workbench API 批量 approve tickets
6. **API Key 60 分钟过期 → 开发环境禁用** — `MAX_PROJECTION_STALENESS_MINUTES = 0`（需加 `> 0` 守卫）

## 发现的 Bug 列表 (共 18 个)

### A. 投影同步系统

| # | Bug | 文件 | 修复 |
|---|-----|------|------|
| 1 | FileReady outbox 事件缺少 `state` 字段 | `document-service/main.py` | 删除重复的 outbox 写入（`_emit_file_ready` 已正确处理） |
| 2 | `claimed_by` 字段名错误（应为 `claimed_by_job_id`） | `document-service/main.py` | 修正字段名，导致 source file 查询返回 500 |
| 3 | `consumed_by`/`consumed_at` 字段不存在于 SourceFileModel | `document-service/main.py` | 用 state 推导替代 |
| 4 | `_derive_overall_status` 不识別 `"processing"` | `projector.py` + `reconciler.py` | 添加到 `intake_job_state` 识别列表 |
| 5 | `_build_task_row` 只从当前事件 payload 推导状态，不合并已有投影 | `projector.py` | `_apply_task_event` 先加载已有投影，`_build_task_row` 合并新旧状态 |
| 6 | IntakeJobStateChanged (v=30) 和 StageCompleted (v=30) 版本冲突 | `intake_adapter.py` + `outbox_deliver.py` | IntakeJobStateChanged → v=25，StageCompleted 保持 v=30 |
| 7 | `_deliver_file_ready` 没有向 workbench 发送 IntakeJobStateChanged | `outbox_deliver.py` | 添加 `_post_native_events_to_workbench` 调用 |
| 8 | `make_deliver_callback` 重复转发 FileReady（被 v=25 事件跳过） | `outbox_deliver.py` | 从转发列表移除 FileReady |
| 9 | IntakeJobStateChanged adapter 不映射 `source_file_id`/`source_file_state` | `intake_adapter.py` | 添加映射 |
| 10 | 投影卡在 uploading/ready/parsing 无法自动恢复 | `task_projection/routes.py` | 添加 `_correct_status()` 读时修复 + auto-recovery 查询下游 |

### B. 管道 Worker 死任务恢复

| # | Bug | 文件 | 修复 |
|---|-----|------|------|
| 11 | `acquire_lease` SQL WHERE 不包含 RUNNING 状态，worker 崩溃后任务永远卡死 | `lease_service.py` | WHERE 条件加入 `RUNNING` |
| 12 | `_start_existing_stage` lease 获取失败仍返回 should_ack=True | `stage_runtime.py` | 返回 should_ack=False 让事件重试 |
| 13 | 无死任务恢复机制 | `stage_task_worker.py` + `stage_tasks.py` | 新增 `recover_stuck_stage_tasks()` + `find_stuck_running()` |
| 14 | conversion/agent-review/publishing worker 未接入恢复 | 三个 worker 的 `main.py` | poll loop 中加入恢复调用 |

### C. 环境变量/配置

| # | Bug | 文件 | 修复 |
|---|-----|------|------|
| 15 | `INDEXING_SERVICE_URL` 未设 → conversion 失败 | `ekb-svc.py` | 添加 conversion-worker env |
| 16 | `REALITY_RAG_SIDECAR_DIR` 未设 → agent review 失败 | `ekb-svc.py` | 添加 agent-review-worker + publishing-worker env |
| 17 | `INTAKE_BASE_URL` 未设 → workbench 连不上 ingestion | `ekb-svc.py` | 添加 workbench-api env，端口 18088 |
| 18 | `RETRIEVAL_SERVICE_URL` 未设 → indexing 完成后 chunk 不同步到检索 DB | `ekb-svc.py` | 添加 indexing service env，端口 18182 |
| 19 | Supervisor 一个服务失败就杀死全部 | `ekb-svc.py` | 移除 `self.shutdown()` 调用 |

### D. 检索层

| # | Bug | 文件 | 修复 |
|---|-----|------|------|
| 20 | API Key 60 分钟过期 → Access 拒绝所有检索请求 | `ApiKeyRegistry.java` | `MAX_PROJECTION_STALENESS_MINUTES = 0`，加 `> 0` 守卫 |
| 21 | 上传去重阻止失败文档重新上传 | `document-service/main.py` | 检测 intake job failed → gc 旧 source file 后放行 |

## 全链路最终验证

**文档**: 第七组REST服务技术与应用.pptx (真实 docx 数据集)  
**结果**: 22 条 evidence items, `hybrid_fusion:opensearch_bm25`, score=1.0

```
upload → conversion → review → approval → publish → index → chunk sync → REST检索 → MCP检索
  ✓         ✓           ✓         ✓          ✓        ✓         ✓           ✓           ✓
```

## 关键文件修改清单

### 投影系统
- `services/workbench-api/src/workbench_api/projections/projector.py`
- `services/workbench-api/src/workbench_api/projections/reconciler.py`
- `services/workbench-api/src/workbench_api/events/adapters/intake_adapter.py`
- `services/workbench-api/src/workbench_api/task_projection/routes.py`
- `services/workbench-api/src/workbench_api/upload_sessions/routes.py`

### 管道运行时
- `packages/intake_runtime/src/intake_runtime/lease_service.py`
- `packages/intake_runtime/src/intake_runtime/stage_runtime.py`
- `packages/intake_runtime/src/intake_runtime/stage_task_worker.py`
- `packages/persistence/src/reality_rag_persistence/repositories/stage_tasks.py`

### Worker 服务
- `services/intake-pipeline/agent-review-worker/src/agent_review_worker/main.py`
- `services/intake-pipeline/conversion-worker/src/conversion_worker/main.py`
- `services/intake-pipeline/publishing-worker/src/publishing_worker/main.py`
- `services/intake-pipeline/ingestion-worker/src/ingestion_worker/outbox_deliver.py`
- `services/intake-pipeline/document-service/src/document_service/main.py`

### 配置
- `scripts/ekb-svc.py`
- `services/access/src/main/java/com/realityrag/access/security/ApiKeyRegistry.java`

### 测试
- `services/workbench-api/tests/test_task_projection.py` — 新增 `TestProjectionEventSequence`
- `services/smoke_tests/test_deployment_smoke.py` — 部署级 E2E 测试
- `scripts/ekb_smoke_test.py` — 独立全链路 smoke 测试
- `scripts/ekb_e2e_full.py` — 完整数据集 E2E 测试
- `.claude/mcp.json` — MCP server 配置

## 第二轮修复 (本轮窗口)

| # | Bug | 文件 | 修复 |
|---|-----|------|------|
| 22 | ApprovalRequested 事件失败后不重试 | `outbox_deliver.py` + `app_factory.py` | `recover_stuck_approvals()` 扫描 `awaiting_approval` 的 intake job，补全 `logical_document_id` + `version` 后重发事件；接入 poll loop |
| 23 | `MAX_PROJECTION_STALENESS_MINUTES=0` 让所有 key 立即过期 | `ApiKeyRegistry.java` | 加 `> 0` 守卫：`if (MAX_PROJECTION_STALENESS_MINUTES > 0 && ...)` |

## 过程中发现的新问题（未修，留待后续窗口）

1. **`workbench_projection_events.event_id` 列太短** — `VARCHAR(64)`，agent_review findings 的 event_id 含 SHA256 hash 超长，INSERT 报 `value too long`。workbench 投影事件丢失。
2. **4 个 docx 数据集文件是空文件（0 字节）** — `2000年10月公司现状`、`付款单`、`内部银行贷款程序`、`财务管理规章制度`。上传必定失败。
3. **2 个 docx 无文本内容（纯图片）** — `审计报告W@`、`所有者权益W@`。转换报 `no canonical preview text`，应降级为"无内容"而非标记 failed。
4. **Outbox 重试上限 10 次后永久放弃** — FileReader、StageCompleted、PublishCompleted 等事件无恢复扫描。StageTask 和 Approval 已修，其余未覆盖。
5. **`ekb-svc.py start` 在 Windows 下不稳定** — subprocess 偶尔 exit code 1，start 总是被 backgrounded。
6. **`_deliver_approval_event` HTTP 4xx 被当作成功** — `return resp.status_code < 500` 导致 400/422 被标记为 sent，审批实际未发生。
7. **approval recovery 缺字段导致 422** — `recover_stuck_approvals` 初版缺少 `logical_document_id` 和 `version`，approval service 返回 422 Unprocessable Entity。已修复。

## 剩余技术债

1. **`IndexBuildCompleted` 事件未转发到 workbench** — indexing 完成后不通知 workbench，`active_index_version` 不显示（不影响检索功能）
2. **`workbench_projection_events.event_id` 列太短** — VARCHAR(64) 不够存 hash 前缀的 event_id
3. **Outbox 事件无统一恢复机制** — 只有 StageTask 和 Approval 有，FileReader/StageCompleted/PublishCompleted 没有
4. **Docx 空文件/纯图片应有降级而非失败**
5. **部署测试无法在 CI 中跑** — 需要 Docker 基础设施
6. **`_deliver_approval_event` HTTP 4xx 应返回 False 触发重试**
7. **ekb-svc.py Windows 兼容性**
