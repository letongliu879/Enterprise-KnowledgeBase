# Intake Pipeline Remediation Plan

## 1. 结论

`services/intake-pipeline` 当前不是一套边界完全清晰的独立服务集合，而是一套过渡态系统：

- 已经切出了 `document-service`、`approval-service`、`conversion-worker`、`agent-review-worker`、`publishing-worker`、`indexing-service`。
- 但真实运行仍大量依赖 `ingestion-worker` 内部模块。
- 根包 `src/intake_pipeline/main.py` 仍作为 smoke/compat 服务被 README、脚本和 smoke tests 启动。
- 多个 owner API 在根服务和拆分服务之间重复存在。
- 一批 compatibility shim、fallback、legacy `StageContext` 仍在承载主链。

整改目标不是继续补功能，而是收敛所有权、删除兼容层、把正式链路和 smoke 链路分开。

## 2. 目标边界

最终应形成以下边界：

| 模块 | 应保留职责 | 不应继续承担 |
|---|---|---|
| `document-service` | upload session、object blob、source file、scan、FileReady outbox | approval、publishing、indexing、workbench projection |
| `ingestion-worker` | orchestrator、intake job state、stage scheduling、outbox dispatch | conversion/review/publishing 具体执行、document owner API、indexing owner API |
| `conversion-worker` | conversion stage execution | source file owner、approval、publishing、indexing owner |
| `agent-review-worker` | review stage execution、AgentReview artifact 生成 | approval decision、stub artifact |
| `approval-service` | ticket lifecycle、decision、final_doc_id、approval audit、AgentReview artifact read model | conversion/review execution、publishing、stub finding |
| `publishing-worker` | publish stage、published document state、asset/document persist、index build command | approval decision、retrieval direct lifecycle patch without command discipline |
| `indexing-service` under intake-pipeline | compatibility service only, if still required | 现代 `services/indexing` 的替代 owner |
| `src/intake_pipeline/main.py` | smoke/compat helper only | 正式 intake owner、正式 internal API、正式 publish/index 主链 |

正式入口应是：

```text
document-service:/upload or /internal/source-files
  -> FileReady outbox
  -> ingestion-worker orchestrator
  -> conversion-worker
  -> agent-review-worker
  -> approval-service
  -> publishing-worker
  -> services/indexing
```

`src/intake_pipeline/main.py:/v1/documents` 只能作为 smoke 兼容入口，不能再扩展业务能力。

关键所有权约束：

- `document-service` 只拥有 source file 事实、blob 事实、scan 状态和 FileReady outbox。
- `intake_job` 由 `ingestion-worker` / orchestrator 创建和推进，`document-service` 不直接创建、不直接更新。
- `SourceFileView` 可以在需要时暴露已关联的 `intake_job_id`，但这只能是 orchestrator 已创建 job 后的只读关联结果，不能反向要求 `document-service` 拥有 job lifecycle。
- contract/openapi 需要同步反映上述边界，避免继续写成 “intake-pipeline 创建 source file 并同时创建 intake job”。

## 3. 当前主要问题

### 3.1 根 `intake_pipeline.main` 是 smoke/compat 服务，但仍像正式服务

文件：

```text
services/intake-pipeline/src/intake_pipeline/main.py
```

问题：

- `IntakeService` 用内存字典保存 `_documents`、`_tickets`。
- `enter_document` 写 `.verify/runtime` 文件。
- `enter_document` 同步调用 indexing parse preview。
- `_publish_from_ticket` 直接写 `published_documents`。
- `_publish_from_ticket` 同步调用 indexing index job 和 activate。
- 同文件暴露 `/v1/documents`、`/v1/approval-tickets`、`/internal/source-files` 等混合接口。

风险：

- 重启丢状态。
- 绕过 document-service、approval-service、publishing-worker 的 owner 边界。
- smoke 成功会掩盖正式链路问题。
- 其他模块容易误接这个服务，把 compat 当正式 owner。

整改：

- 将该文件标记为 `compat/smoke only`。
- 禁止新增正式业务接口。
- README 和启动脚本中标注该服务只用于 smoke。
- 后续把正式消费者切到 `document-service`、`approval-service`、`publishing-worker`。
- 完成迁移后删除或移动到 `services/intake-pipeline/smoke-compat/`。

### 3.2 `/internal/source-files` 存在双 owner

冲突位置：

```text
services/intake-pipeline/src/intake_pipeline/main.py
services/intake-pipeline/document-service/src/document_service/main.py
contracts/openapi/intake-internal.yaml
```

现状：

- 根 `intake_pipeline.main` 的 `/internal/source-files` 接收 command-envelope 风格请求，但只写内存。
- `document-service` 的 `/internal/source-files` 接收 `object_id/content_hash/upload_id`，写数据库。
- `contracts/openapi/intake-internal.yaml` 描述的是 `SourceFileRegisterRequest` / `SourceFileView`。
- 该 OpenAPI 当前 owner 描述仍是 `intake-pipeline`，且描述里暗示注册 source file 会创建 associated intake job；这和目标边界里的 `document-service` source-file owner、`ingestion-worker` intake-job owner 不一致。
- `workbench-api` 的 `IntakeClient` 目前按 contract 调用 `/internal/source-files`。

风险：

- 同一路径不同语义。
- workbench-api 如果指向根服务，会得到非持久化 source file。
- workbench-api 如果指向 document-service，当前请求体不匹配。
- idempotency 在根服务里是进程内 dict，不可靠。

整改：

- `document-service` 成为 `/internal/source-files` 的唯一 owner。
- 拆分或更新 `contracts/openapi/intake-internal.yaml`：source file registration 的 owner 改为 `document-service`，intake job read/write contract 归 `ingestion-worker` / orchestrator。
- `document-service` 实现 source file registration contract 的请求和响应，但不创建、不推进 `intake_job`。
- `document-service` 成功注册 source file 后写 FileReady outbox；由 `ingestion-worker` 消费后创建 intake job。
- idempotency 写 SQL，而不是内存 dict。
- 根 `intake_pipeline.main:/internal/source-files` 标记 deprecated，迁移完成后删除。
- workbench-api 的 intake base URL 指向 document-service。

### 3.3 split worker 仍依赖 `ingestion_worker` 内部代码

位置：

```text
services/intake-pipeline/conversion-worker/src/conversion_worker/main.py
services/intake-pipeline/agent-review-worker/src/agent_review_worker/main.py
services/intake-pipeline/publishing-worker/src/publishing_worker/main.py
services/intake-pipeline/ingestion-worker/src/ingestion_worker/stage_runtime.py
services/intake-pipeline/ingestion-worker/src/ingestion_worker/stage_task_worker.py
```

现状：

- conversion-worker import `ingestion_worker.stages.schemas`、`pure_stages`、`stage_runtime`、`stage_task_worker`。
- agent-review-worker import `ingestion_worker.agent_reviewer`、`agent_review_cache`、`stage_runtime`。
- publishing-worker import `ingestion_worker.stage_runtime`、`stage_task_worker`。
- worker 的 `pyproject.toml` 没有声明对 `ingestion-worker` 的包依赖。

风险：

- 拆分服务只是目录拆分，不是运行时边界拆分。
- 任意修改 `ingestion_worker` 都可能破坏三个 worker。
- 部署依赖靠 PYTHONPATH 或 workspace layout 隐式成立。
- 测试绿不代表独立服务可部署。

整改：

- 提取共享包，例如：

```text
packages/intake_runtime/
  stage_schemas.py
  pure_stages.py
  stage_runtime.py
  stage_task_worker.py
  stage_adapters.py
```

- conversion/review/publishing worker 依赖 `reality-rag-intake-runtime`。
- `ingestion-worker` 也依赖该共享包。
- worker 不再 import `ingestion_worker.*`。

### 3.4 compatibility shim 和 fallback 仍在主链上

位置：

```text
services/intake-pipeline/ingestion-worker/src/ingestion_worker/domains/approval_domain.py
services/intake-pipeline/ingestion-worker/src/ingestion_worker/domains/document_domain.py
services/intake-pipeline/ingestion-worker/src/ingestion_worker/domains/indexing_domain.py
services/intake-pipeline/ingestion-worker/src/ingestion_worker/domains/outbox.py
services/intake-pipeline/ingestion-worker/src/ingestion_worker/indexing_service.py
```

现状：

- `approval_domain.py` 是 remote-or-local fallback selector。
- `document_domain.py` 是 re-export compatibility shim。
- `indexing_domain.py` 是 re-export compatibility shim。
- `outbox.py` 是 backward compatibility re-export。
- `indexing_service.py` 虽然已经要求 `INDEXING_SERVICE_URL`，但仍包含大量 legacy API facade 和兼容命名。

风险：

- 新代码容易继续 import shim。
- local fallback 让 owner 边界在测试/开发中失真。
- 同一 interface 既可能 HTTP 调用，也可能本地直接写 owner 表。

整改：

- 生产环境禁用 local fallback。
- 所有 fallback 通过显式 `ALLOW_LOCAL_FALLBACK_FOR_TESTS=true` 才允许。
- 给 shim 文件加 deprecation 注释和退场日期。
- 改完引用后删除纯 re-export 文件。

### 3.5 旧同步 pipeline 自消费 outbox

位置：

```text
services/intake-pipeline/ingestion-worker/src/ingestion_worker/pipeline.py
```

现状：

- `IngestionPipeline.run()` 支持同步传入 source file path。
- `_drain_outbox_until_source_files_terminal()` 在同一进程里轮询 orchestrator、conversion、review、publishing dispatcher。

风险：

- 这更像集成测试 helper，不是正式生产链路。
- 它会掩盖 worker 独立部署、消息延迟、lease、重试、幂等问题。
- 继续保留为主入口会让正式链路和测试链路分叉。

整改：

- 标记 `IngestionPipeline.run()` 为 smoke/test helper。
- 正式链路只从 document-service FileReady outbox 启动。
- smoke tests 逐步改成真实多服务链路，不再依赖 `/v1/documents`。

### 3.6 AgentReview artifact 还是 stub

位置：

```text
services/intake-pipeline/approval-service/src/approval_service/main.py
```

现状：

- `/internal/tickets/{ticket_id}/agent-review` 返回硬编码 artifact。
- `quality_findings`、`risk_flags`、`evidence_anchors`、`suggested_fixes` 都为空。
- `prompt_hash` 是 `sha256:stub`。

风险：

- workbench 无法展示哪里有问题、什么问题、怎么改。
- AgentReview 不能和原文/chunk anchor 对齐。
- 自动审核事实不可复核。

整改：

- agent-review-worker 持久化真实 artifact。
- approval-service 只读该 artifact。
- artifact schema 至少包含 finding、evidence anchor、source quote、chunk quote、suggested fix。
- 删除 stub 返回。

### 3.7 `StageContext` 是遗留耦合核心

位置：

```text
services/intake-pipeline/ingestion-worker/src/ingestion_worker/stages/protocol.py
services/intake-pipeline/ingestion-worker/src/ingestion_worker/stages/adapters.py
services/intake-pipeline/ingestion-worker/docs/stage-context-mapping.md
```

现状：

- `StageContext` 是 mutable context。
- 内含 `session`、`document_repo`、`policy_repo`。
- 同时保留 `job_id`、`intake_job_id`、`doc_id`、`final_doc_id`、`source_file_path`、`source_file_id`。
- adapters 在 legacy context 与 stage schema 之间转换。

风险：

- stage 看似 schema 化，实际仍能通过 context 接触数据库和旧字段。
- worker 之间的输入输出契约不够硬。
- 新旧身份字段容易混用。

整改：

- 新 stage 只接受 schema input，返回 schema output。
- `StageContext` 保留在 adapter 层，禁止新逻辑直接依赖。
- 逐步删除 `session/repo` 字段。
- 逐步删除 legacy `job_id/source_file_path/doc_id` 作为主字段。

## 4. 分阶段整改计划

### Phase 0: 标记边界和冻结新增

目标：

- 先停止扩散，不急删代码。

动作：

- 在 `src/intake_pipeline/main.py` 文件头加注释：`SMOKE/COMPAT ONLY`。
- 在 README 和 `scripts/ekb-svc.py` 相关说明中标注根 service 只用于 smoke。
- 禁止继续往根 `intake_pipeline.main` 增加正式业务接口。
- 给 `ingestion_worker/domains/*` compatibility shim 加 deprecation 注释。

验收：

- 文档明确：正式 source file owner 是 document-service。
- 文档明确：正式 approval owner 是 approval-service。
- 文档明确：正式 indexing owner 是 `services/indexing` 或明确的现代 indexing service，不是根 intake。

### Phase 1: 统一 source file internal API

目标：

- `/internal/source-files` 只有一个正式 owner。
- source file owner 与 intake job owner 在 contract、实现和文档里明确分离。

动作：

- 改 `document-service` 的 `/internal/source-files` 请求体，兼容 source file registration schema。
- 更新或拆分 `SourceFileRegisterRequest.schema.json` / `SourceFileView.schema.json` 的 owner 说明：source file 归 `document-service`，`intake_job` 归 `ingestion-worker` / orchestrator。
- `SourceFileView.intake_job_id` 如果保留，只能是可选只读关联字段；不得作为 `document-service` 创建 job 的验收要求。
- 返回更新后的 `SourceFileView.schema.json`。
- 补 `GET /internal/source-files/{source_file_id}`。
- `GET /internal/intake-jobs/{intake_job_id}` 明确由 orchestrator endpoint 提供，不挂到 `document-service`。
- 补 `GET /internal/published-documents/{published_document_id}`，或明确由 publishing endpoint 提供。
- idempotency 写 SQL。
- source file 注册成功后写 FileReady outbox，作为正式链路启动点。
- workbench-api 的 `IntakeClient` 指向 document-service。
- 根 `intake_pipeline.main` 同路径接口进入 deprecated。

验收：

- workbench-api 创建 upload session 后得到持久化 source_file。
- 重复 idempotency_key 不创建重复 source_file。
- 重启服务后 idempotency 仍成立。
- `/internal/source-files` contract test 通过。
- 最小真实链路 smoke 通过：`document-service:/internal/source-files` 注册 source file 后，FileReady outbox 被 `ingestion-worker` 消费并创建 `intake_job`。
- contract test 能证明 `document-service` 不直接拥有 `intake_job` lifecycle。

### Phase 2: 提取 shared intake runtime

目标：

- split workers 不再依赖 `ingestion_worker` 应用包。

动作：

- 新增共享包：

```text
packages/intake_runtime/
```

- 移入或重建以下模块：

```text
stage_runtime.py
stage_task_worker.py
stages/schemas.py
stages/pure_stages.py
stages/adapters.py
```

- conversion-worker、agent-review-worker、publishing-worker 改 import 到 shared package。
- `ingestion-worker` 也改 import 到 shared package。
- worker `pyproject.toml` 显式依赖 shared package。

验收：

- conversion-worker 不再 import `ingestion_worker.*`。
- agent-review-worker 不再 import `ingestion_worker.*`。
- publishing-worker 不再 import `ingestion_worker.*`。
- worker 单独测试时不需要把 ingestion-worker/src 塞进 PYTHONPATH。
- Phase 1 的最小真实链路 smoke 仍通过，证明 runtime 抽包没有只保住旧 compat 链路。

### Phase 3: 清理 fallback 和 shim

目标：

- local fallback 只在 tests/smoke 使用。

动作：

- `approval_domain.py`：生产必须使用 `APPROVAL_SERVICE_URL`，local fallback 只在测试开关下启用。
- `indexing_service.py`：保留 HTTP facade，但删除 legacy local API 语义和多余别名。
- 删除或替换纯 re-export：

```text
ingestion_worker/domains/outbox.py
ingestion_worker/domains/document_domain.py
ingestion_worker/domains/indexing_domain.py
```

- 所有新代码直接 import owner package 或 shared runtime，不 import shim。

验收：

- grep 不再出现业务代码 import `ingestion_worker.domains.outbox`。
- grep 不再出现业务代码 import `ingestion_worker.domains.indexing_domain`。
- production 配置缺少必要 downstream URL 时 fail fast。

### Phase 4: 退役根 compat publish 链路

目标：

- `/v1/documents` 不再作为正式主链。

动作：

- 将 `src/intake_pipeline/main.py:/v1/documents` 标记为 smoke only。
- smoke tests 分两类：
  - compat smoke：允许继续测试 `/v1/documents`。
  - real chain smoke：沿用 Phase 1 已建立的真实链路 smoke，并扩展到 `document-service:/upload` 触发 FileReady outbox。
- README 默认启动流程改为真实链路。
- `scripts/ekb-svc.py` 不把根 `intake_pipeline.main` 标成正式 intake。

验收：

- 真实链路 smoke 不依赖 `/v1/documents`。
- 根 `intake_pipeline.main` 不再被 workbench-api 或 admin 作为正式 downstream。

### Phase 5: 实现真实 AgentReview artifact

目标：

- workbench 能展示可定位 finding。

动作：

- agent-review-worker 将 review 输出持久化为 artifact。
- artifact 包含：

```text
finding_id
severity
category
problem_summary
problem_detail
evidence_id
source_file_id
parse_snapshot_id
page_from
page_to
source_anchor
source_quote
chunk_quote
why_wrong
suggested_fix
suggested_operation
confidence
```

- approval-service `/internal/tickets/{ticket_id}/agent-review` 查询真实 artifact。
- 删除 stub artifact。

验收：

- 人工审批 ticket 能拿到真实 AgentReview artifact。
- artifact 至少能定位 source file 和 parse snapshot。
- finding 能被 workbench 投影为右侧问题列表。

### Phase 6: 删除旧代码

删除顺序：

1. 删除纯 re-export shim。
2. 删除 local fallback 分支。
3. 删除 `IngestionPipeline.run()` 作为正式入口的使用。
4. 删除根 `intake_pipeline.main` 的 internal source file API。
5. 删除根 `intake_pipeline.main` 的 publish/index 直连链路。
6. 如 smoke 已迁移，移动或删除根 `intake_pipeline.main`。

每一步必须先跑：

```text
services/intake-pipeline/* tests
services/workbench-api tests affected by intake client
contracts schema/openapi tests
real-runtime smoke or equivalent targeted smoke
```

## 5. 删除候选清单

### 可优先删除，但需先改引用

```text
ingestion-worker/src/ingestion_worker/domains/outbox.py
ingestion-worker/src/ingestion_worker/domains/document_domain.py
ingestion-worker/src/ingestion_worker/domains/indexing_domain.py
```

原因：

- 主要是 re-export compatibility shim。
- 删除前需要替换所有 import。

### 暂不能直接删除

```text
src/intake_pipeline/main.py
ingestion-worker/src/ingestion_worker/pipeline.py
ingestion-worker/src/ingestion_worker/stages/protocol.py
ingestion-worker/src/ingestion_worker/stage_runtime.py
```

原因：

- 仍被 README、scripts、smoke tests 或 split workers 引用。
- 需要先迁移调用方和 shared runtime。

### 需要替换后删除

```text
approval-service/src/approval_service/main.py 中的 AgentReview stub
src/intake_pipeline/main.py 中的 /internal/source-files 兼容实现
src/intake_pipeline/main.py 中的 /v1/documents approve-and-publish 链路
```

## 6. 验收标准

整改完成后应满足：

- `document-service` 是唯一 source file owner。
- `ingestion-worker` / orchestrator 是唯一 intake job lifecycle owner。
- `/internal/source-files` 契约和实现一致。
- source file contract 不要求 `document-service` 创建或推进 `intake_job`。
- split workers 不 import `ingestion_worker.*`。
- production 不启用 local fallback。
- `StageContext` 只作为 legacy adapter，不是新逻辑主接口。
- AgentReview artifact 不再是 stub。
- workbench-api 不再接根 `intake_pipeline.main`。
- smoke/compat 链路与正式链路在文档和启动脚本中明确区分。
- 删除旧代码不会破坏真实 upload -> review -> approval -> publish -> indexing 链路。

## 7. 建议实施顺序

最稳妥的顺序：

1. 先做 Phase 0，写明边界，避免误用。
2. 再做 Phase 1，解决 workbench 和后端 owner API 的实际冲突。
3. Phase 1 完成后立刻建立最小真实链路 smoke，至少覆盖 `document-service -> FileReady outbox -> ingestion-worker intake_job created`。
4. 再做 Phase 2，解除 split workers 对 `ingestion_worker` 的隐式依赖。
5. 再做 Phase 3，清理 fallback/shim。
6. 再做 Phase 5，补 AgentReview 真实 artifact。
7. 最后做 Phase 4/6，退役旧 smoke/compat 主链。

不要一开始就直接删除 `src/intake_pipeline/main.py`。它当前仍被 smoke、README 和脚本使用，直接删会让验证链路断掉。正确做法是先把正式消费者迁走，再把它降级为 smoke helper，最后再决定是否删除。
