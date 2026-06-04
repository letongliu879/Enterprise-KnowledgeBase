# Intake Pipeline Remediation Plan

## 0. 当前快照

本文档已根据当前工作树代码现状重新整理，用于回答两个问题：

1. 这份整改计划现在应该怎么排优先级
2. 当前代码已经执行到了什么程度

状态标记：

- `未开始`：当前工作树里没有可靠证据表明已落地
- `进行中`：已经有部分代码或测试支撑，但边界、验收或默认路径仍未收口
- `已完成`：当前工作树内已有明确实现，且与目标方向基本一致

### 0.1 当前执行进度总览

| 项目 | 状态 | 代码现状 |
|---|---|---|
| 测试止血：关闭 `TestClient` / 避免 health test 启动后台 poller | `进行中` | 当前工作树中多个 smoke test 已改成 context-managed `TestClient`；3 个后台 worker 已提供正式 `create_app(start_background_poller=False)` 入口，health smoke 不再依赖测试内 monkeypatch lifespan |
| Phase S：测试生命周期与资源治理 | `进行中` | 已新增仓库级 guardrail test，约束裸 `return TestClient(...)` 与测试内 lifespan monkeypatch；但统一 fixture、超时/资源预算、更多服务覆盖仍未完成 |
| Phase 0：compat 根入口降级、前移 fail-fast | `进行中` | `src/intake_pipeline/main.py` 已自述为 compatibility-only，根 `/internal/source-files*` 写接口已退役为只读诊断视图；compat 写入口现已默认禁用，且启用后要求显式 downstream URL；`workbench create_upload` 也已不再默认触发 compat source-file 注册；但默认验证路径与剩余 fallback 仍未完整收口 |
| Phase 1：统一 source file owner | `进行中` | `document-service` 已承载 `/internal/source-files*` 写路径并写出 `FileReady`；compat 根服务保留只读诊断视图；是否已完全切走所有默认入口仍需继续收口 |
| Phase 2A：显式收口运行时边界 | `进行中` | split workers 已不再直接反向 import `ingestion_worker.*`；`indexing-service` 已增加定向测试防止从仓库根测错目标；但包解析/导入目标冲突与隐式路径依赖仍未彻底解决 |
| Phase 2B：shared runtime 抽包 | `未开始` | 当前未见正式 shared runtime 抽包完成态，不应提前推进 |
| Phase 3：清理 shim / fallback / `StageContext` | `进行中` | `pure_stages.py` 与 schema input/output 已存在；但 `StageContext` 仍在 runtime、adapters、tests 中承担过渡职责 |
| Phase 4：退役根 compat 主链 | `进行中` | 根 compat API 仍暴露 `/v1/documents` 等 legacy 路径；但 in-process smoke 对 compat 的使用已被显式标注并通过环境开关启用，不再是静默默认路径 |
| Phase 5A：reviewer 两阶段架构 | `进行中` | 当前已有 findings extraction 逻辑与规则，但尚未证明 reviewer 架构已完全收敛为正式目标形态 |
| Phase 5B：contracts 增加 `anchored_findings` | `已完成` | `packages/contracts` 已包含 `anchored_findings` 相关字段与校验测试 |
| Phase 5C：真实 review artifact 持久化 | `进行中` | `approval-service/review_artifacts.py` 已从 `StageResultModel.result_ref` 或 `summary_json` 读取 artifact payload；但 artifact store、owner 边界与幂等约束仍需继续收口 |
| Phase 5D：`approval-service` 只读 artifact | `进行中` | `/internal/tickets/{ticket_id}/agent-review` 已改为读 payload，不再是纯硬编码 stub；但仍带有 fallback 组装与下游归一化逻辑 |
| Phase 6：approval/workbench/indexing 闭环 | `进行中` | 当前 approval payload 已带 findings 归一化结构；matcher / routes / frontend 闭环不在本目录内完全闭合 |
| Phase 7：删除旧代码 | `未开始` | 不应提前推进 |

### 0.2 本轮必须先解决的事实

当前最紧急的问题不是 owner 蓝图，而是**测试与后台生命周期治理缺位**：

- worker app 在 lifespan 中会启动无限轮询的 outbox poller
- 不正确的测试夹具会让后台任务残留
- 残留任务若持续异常，会不断产生日志与资源累积
- 在这种前提下直接跑整套测试，可能再次把 Python 进程推到极高内存

因此，后续整改顺序必须把“止血层”前置。


## 1. 结论

`services/intake-pipeline` 仍是过渡态系统，不是边界清晰、可独立部署、可验证的正式服务集合。

当前问题不是单点 bug，而是以下几类问题叠加：

- owner 边界不清：`source file`、`intake job`、`approval`、`publish`、`indexing` 仍有职责重叠
- 正式链路与 compat/smoke 链路混杂，根 `intake_pipeline.main` 仍在冒充正式入口
- 运行时边界仍不够显式，存在导入目标冲突与隐式路径依赖
- fallback / shim / legacy `StageContext` 仍承载主链
- 测试生命周期治理缺位：后台 poller、`TestClient`、日志捕获、整套测试执行策略都缺少硬约束
- `AgentReview artifact` 已有部分落地，但 owner、store、幂等、字段边界仍未完全定死

本次整改目标应明确为：

1. 先止血，避免测试再次拖死机器
2. 收敛 owner 边界
3. 固化真实正式链路
4. 清理 compat / shim / fallback / 导入歧义
5. 在稳定主链上收口真实 `AgentReview artifact`


## 2. 当前阶段约束

本轮整改必须遵守以下约束：

1. **只以当前工作树现状为准**
   - 不再引用旧 worktree 路径
   - 当前仓库根目录为 `E:\AI\My-Project\Enterprise KnowledgeBase`

2. **当前阶段可以改 `workbench-api`，但不能让它成为 owner**
   - `workbench-api` 可以进入正式实施范围
   - 允许落地 approval 回调、projection、matcher、routes、frontend 跳转
   - 但 `workbench-api` 仍然只能承担 projection / read-model / adapter / UI integration，不得承担 source file、review artifact、indexing chunk 的 owner 职责

3. **当前阶段不把 agent cache 设计作为主目标**
   - 不把 prompt cache、input cache、二次 review cache 作为本轮交付主项
   - 现有 cache 即使暂时保留，也不得成为新的 owner、主键或跨服务契约基础

4. **验收必须受控**
   - 禁止把“直接跑 `services/intake-pipeline/* tests` 全量测试”作为默认验收动作
   - 优先使用单服务定向测试、真实链路 smoke、带超时/资源边界的 targeted smoke


## 3. 目标边界

最终边界应收敛为：

| 模块 | 应保留职责 | 不应继续承担 |
|---|---|---|
| `document-service` | upload session、object blob、source file、scan、`FileReady` outbox | approval、publishing、indexing、workbench projection |
| `ingestion-worker` | orchestrator、`intake_job` state、stage scheduling、outbox dispatch | conversion/review/publishing 具体执行、document owner API、indexing owner API |
| `conversion-worker` | conversion stage execution | source file owner、approval、publishing、indexing owner |
| `agent-review-worker` | review stage execution、真实 `AgentReview artifact` 生成与持久化 | approval decision、review payload 下游 owner、workbench projection owner |
| `approval-service` | ticket lifecycle、decision、`final_doc_id`、approval audit、`AgentReview artifact` 只读查询 | review 执行、伪 artifact 拼装、finding 语义 owner |
| `publishing-worker` | publish stage、published document state、asset/document persist、index build command | approval decision、retrieval direct lifecycle patch |
| `services/indexing` | parse snapshot / chunk / indexing owner | intake compat owner |
| `src/intake_pipeline/main.py` | compat/smoke helper only | 正式 intake owner、正式 internal API、正式 publish/index 主链 |

正式链路目标：

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

关键边界约束：

- `document-service` 是唯一 source file owner
- `ingestion-worker` / orchestrator 是唯一 `intake_job` owner
- `agent-review-worker` 是唯一 review artifact 写入方
- `approval-service` 只读 review artifact，不再生成伪 artifact
- 当前阶段不让 `workbench` 成为任何 owner


## 4. 已确认的核心问题

### 4.1 根 `intake_pipeline.main` 仍像正式服务

问题：

- 仍暴露 `/v1/documents`、`/v1/approval-tickets` 等 legacy 入口
- 仍保留本地状态、直连 publish/indexing 的 compat 逻辑
- compat/smoke 成功会掩盖真实链路问题

现状：

- 模块头注释已明确 self-positioning 为 compatibility-only
- `/internal/source-files*` 写接口已从 compat 根服务退场，仅保留只读诊断视图

结论：

- 该项不是 `未开始`，而是 `进行中`

### 4.2 `/internal/source-files` owner 已部分收口，但尚未完全退役 compat 入口

问题：

- 当前主写路径已在 `document-service`
- 但仓库里仍保留 compat 根服务的 source-file 诊断接口与旧路径叙事

现状：

- `document-service` 已承载 `/internal/source-files` 及后续 claim/mark/start-scan/complete-scan 等写接口
- compat 根服务已有注释说明写 owner 已退役

结论：

- 该项状态应为 `进行中`，不是纯待做

### 4.3 split workers 的反向 import 问题已明显缓解，但运行时边界仍未完全收口

问题：

- 原 plan 假设 split workers 仍大量反向 import `ingestion_worker.*`
- 当前工作树里，这一点已经不是主矛盾

现状：

- `conversion-worker`、`agent-review-worker`、`publishing-worker` 当前源码中未再直接依赖 `ingestion_worker.*`
- 但仍存在 `intake_runtime` 共享层、隐式导入路径、顶层包名冲突等问题

结论：

- 原 plan 对问题描述已经过时
- 应改为“运行时边界与导入目标歧义尚未彻底解决”

### 4.4 fallback / shim / `StageContext` 仍在主链

问题：

- fallback 让错误拓扑在开发环境继续“假装可用”
- shim 继续诱导新代码依赖旧路径
- `StageContext` 仍在 runtime、adapter、tests 中承担过渡职责

现状：

- `pure_stages.py` 与 schema input/output 已存在
- `StageContext` 仍未退回纯 adapter 边界

结论：

- 该项为 `进行中`

### 4.5 `AgentReview artifact` 不再是纯 stub，但尚未完全收口为最终态

问题：

- 原 plan 将其描述为“当前返回硬编码 artifact”，这已经不准确

现状：

- `packages/contracts` 已有 `anchored_findings`
- `agent_reviewer.py` 已有 findings extraction 规则
- `approval-service/review_artifacts.py` 已能从 `StageResultModel.result_ref` 或 `summary_json` 读取 artifact payload
- `approval-service` 已能把 findings 归一化并透传下游字段

仍未完成的点：

- artifact store 仍带 fallback 组装逻辑
- 读取链路、owner 边界、幂等语义还没完全定死
- 下游 payload 里仍可能出现 envelope / finding 字段重复与边界漂移

结论：

- 该项应改为 `进行中`

### 4.6 测试生命周期与后台任务治理缺位

问题：

- 多个 worker app 在 lifespan 中启动无限轮询后台任务
- 错误的测试夹具会导致 shutdown 不可靠，后台任务残留
- 残留任务若持续异常，会放大日志捕获与内存占用
- 这正是本轮“Python 涨到 12GB”的直接风险源

现状：

- 当前工作树已对若干 smoke test 进行局部止血
- 但原 plan 完全没有覆盖这类问题

结论：

- 该项必须上升为最高优先级整改内容

### 4.7 包解析与测试导入目标冲突

问题：

- 仓库中存在重复顶层包名与多源 `pythonpath`
- 在仓库根执行测试时，测试可能导入错误目标

影响：

- 测试即使“通过”也可能测错服务
- 这会让整改计划的验收失真

结论：

- 该项必须纳入运行时边界整改，而不是留给后续处理


## 5. 对原方案的保留与修订

### 5.1 保留的方向

以下方向仍然成立：

- source file owner 收敛到 `document-service`
- intake orchestrator 收敛到 `ingestion-worker`
- compat 根入口降级
- `AgentReview artifact` 由 `agent-review-worker` 生产、`approval-service` 只读消费
- workbench / matcher / frontend 闭环建立在真实 findings 之上

### 5.2 必须修订的地方

以下内容必须改写：

- 旧 worktree 路径约束
- “`AgentReview artifact` 仍是 stub”的表述
- “split workers 仍大量反向 import `ingestion_worker.*`”的表述
- “每一步删除前必须跑 `services/intake-pipeline/* tests`”的验收方式
- 缺少测试生命周期与资源治理这一整改主线


## 6. `AgentReview` 正式目标

这部分方向基本保留，但按当前代码现状视为**延续整改**而不是从零开始。

### 6.1 reviewer 目标架构

- **单文档、单 agent**
- **文档级并发**
- **两阶段 review**

### 6.2 Main Review

输入：

- canonical markdown
- quality report
- collection / authority context

输出至少包含：

- `document_type`
- `suggested_authority_level`
- `detected_pii`
- `diff_summary`
- `decision`
- `confidence`
- `reasons`
- `risk_tags`
- `suggested_actions`
- `publish_recommendation`
- `sections_requiring_review`

### 6.3 Findings Extraction

触发条件：

- `decision != approve`
- 或 `publish_recommendation != published`
- 或 `confidence < REVIEW_FINDINGS_THRESHOLD`
- 或命中 `REVIEW_FINDINGS_REQUIRED_TAGS`

输出：

- `anchored_findings[]`

正式要求：

1. 一份文档一次调用，输出该文档全部主要问题
2. 多个本质相同问题只保留一个 finding
3. 多个片段支持同一问题时只保留最有代表性的 `source_quote`
4. 无法稳定定位原文证据时，不编造 finding
5. 即使主 review 判断有风险，也允许 `anchored_findings=[]`

### 6.4 artifact 边界

artifact envelope 至少包含：

```text
review_run_id
intake_job_id
source_file_id
parse_snapshot_id
artifact_version
review_model
prompt_version
artifact_schema_version
generated_at
```

每个 `AnchoredFinding` 至少包含：

```text
finding_id
source_quote
problem_summary
severity
confidence
```

边界要求：

- `finding_id` 必须由 review artifact 生产侧稳定生成
- `approval-service` 不得把 fallback 组装长期固化为正式 owner 行为
- cache 不得充当 artifact store


## 7. 分阶段整改计划

本计划改为三条线推进：

1. **止血主线**：先控制测试资源、后台任务、导入冲突
2. **边界整改主线**：再收口 owner、正式链路、compat、fallback
3. **能力建设主线**：最后收口 `AgentReview artifact` 与闭环集成

### 7.1 Phase S：测试与资源止血

目标：

- 防止测试再次拖死机器
- 让后续所有整改建立在可安全执行的反馈回路上

动作：

- 统一 `TestClient` 使用规范：必须 `with TestClient(...)` 或 `yield` fixture
- worker health/smoke test 默认不得启动真实 lifespan poller
- 为带 `while True` poll loop 的 app 提供显式 test mode / noop lifespan
- 建立最小回归集，默认只跑单服务定向测试
- 为 targeted smoke 增加超时、日志边界、必要时的内存观察
- 识别并修复测试导入错包问题

验收：

- 不再存在裸 `return TestClient(app)` 的 fixture
- health/smoke 测试不会启动常驻后台 poller
- targeted test 可在受控时间内完成
- 从仓库根运行定向测试时，不会测错服务目标

### 7.2 Phase 0：冻结 compat 扩散，前移 fail-fast

目标：

- 停止继续向 compat 链路堆功能
- 尽早暴露错误拓扑，而不是继续靠 fallback 伪装成真实链路

动作：

- 继续强化 `src/intake_pipeline/main.py` 的 compatibility-only 定位
- README / 启动脚本明确区分真实链路与 compat 链路
- 不再向根 compat 服务新增正式业务接口
- 给 shim 加 deprecation 标记
- 对关键 downstream URL 前移 fail-fast
- 明确哪些 fallback 只允许测试使用

验收：

- 缺失关键 downstream 配置不会静默走本地 fallback
- 文档明确声明正式 owner 边界和 compat 边界

### 7.3 Phase 1：统一 source file owner，并前移默认验证路径

目标：

- `/internal/source-files` 只有一个正式 owner
- source file owner 与 intake job owner 明确分离
- 默认验证路径切到真实链路

动作：

- 保持 `document-service` 作为唯一 source file 写 owner
- 保持 `FileReady -> ingestion-worker` 为正式 intake 启动路径
- README、脚本、smoke 默认路径切到真实链路
- compat 路径仅保留为显式 legacy/smoke helper

验收：

- source file 持久化与 idempotency 正常
- `document-service -> FileReady -> ingestion-worker intake_job created` 真实链路 smoke 通过
- 默认 smoke 不再以 compat 根入口为首选

### 7.4 Phase 2A：显式收口运行时边界

目标：

- 拿到“可部署、可测试、依赖显式”的 split workers

动作：

- 清理隐式 `PYTHONPATH` / workspace layout 依赖
- 消除重复顶层包名造成的导入歧义
- 清理启动脚本里对其它 worker 塞 `ingestion-worker/src` 的默认方式
- 让包依赖与运行依赖都显式化

验收：

- split workers 不依赖隐式 `PYTHONPATH`
- 从仓库根运行定向测试不会导入错包
- 运行时边界可证明已显式化

### 7.5 Phase 2B：确有必要时再提 shared runtime

目标：

- 仅在 2A 完成后仍存在明显共享实现耦合时，再提 shared runtime

说明：

- 2B 不是整改主线前置阻塞项
- 2B 是结构整理，不是止血项

### 7.6 Phase 3：清理 shim / fallback / `StageContext`

目标：

- 主链不再依赖 shim / fallback / legacy context

动作：

- 删除纯 re-export shim
- 把 local fallback 收敛到显式测试场景
- `StageContext` 限缩到 adapter 层
- 新 stage 逻辑只收 schema input / output

验收：

- 生产配置缺 URL 时 fail fast
- 主业务代码不再 import shim
- 新逻辑不以 `StageContext` 作为核心接口

### 7.7 Phase 4：退役根 compat 主链

目标：

- `/v1/documents` 不再作为默认正式主链

动作：

- compat smoke 与 real-chain smoke 分开
- README 默认流程维持真实链路
- 根 `intake_pipeline.main` 不再被正式消费者使用

验收：

- 真实链路 smoke 不依赖 `/v1/documents`
- compat 链路只作为显式 legacy/smoke helper 存在

### 7.8 Phase 5：收口真实 `AgentReview artifact`

前置条件：

- Phase S 完成
- 边界整改主线至少完成到 Phase 3

子阶段：

- 5A：reviewer 架构收口到单文档、单 agent、文档级并发、两阶段 review
- 5B：contracts 与 artifact 字段边界收口
- 5C：`agent-review-worker` 写入真实 artifact
- 5D：`approval-service` 改为只读 artifact，删除长期 fallback 语义

验收：

- `approval-service` 不再依赖伪 artifact 组装作为常态路径
- artifact 能稳定定位到 `source_file_id`、`parse_snapshot_id`
- `anchored_findings` 支持空集合与多条 finding
- `finding_id` 稳定生成

### 7.9 Phase 6：workbench / indexing 闭环集成

该阶段在真实 artifact 稳定后推进：

1. approval callback / event payload 携带完整 findings
2. adapter 将每个 finding 展开为 projection event
3. projector 写入 agent review projection
4. matcher 扫描未匹配 findings
5. 调 indexing 的 `parse-snapshots/{id}/chunks` 拿 chunk 全文
6. 对 `source_quote` 与 chunk content 做模糊匹配
7. 回填 `evidence_id / page_from / page_to`
8. routes 返回 matched / unmatched findings
9. frontend 用 `source_quote` 做搜索与跳转

### 7.10 Phase 7：删除旧代码

删除前置要求：

- 不跑无边界的全量测试
- 仅在 targeted tests、contracts tests、real-chain smoke 都通过时推进删除


## 8. 当前阶段做与不做

### 当前阶段做

- 先完成 Phase S
- 再推进整改主线 Phase 0-4
- 在整改主线稳定后推进 Phase 5

当前阶段重点：

- 测试生命周期与资源治理
- owner 收敛
- 默认验证路径切到真实链路
- 运行时依赖显式化
- fallback / shim / `StageContext` 清理

### 当前阶段不做

- 新的 agent 缓存设计与实现
- 提前做 shared runtime 抽包
- 在止血完成前直接跑 intake-pipeline 全量测试


## 9. 验收标准

### 9.1 止血主线验收

- 不再存在裸 `return TestClient(app)` fixture
- worker health/smoke test 不会启动常驻 poller
- targeted tests 有明确超时与清理边界
- 从仓库根运行定向测试不会导入错包

### 9.2 整改主线验收

- `document-service` 是唯一 source file owner
- `ingestion-worker` / orchestrator 是唯一 `intake_job` owner
- 默认验证路径已切到真实链路
- split workers 的依赖与运行边界已显式化
- 生产不启用 local fallback
- `StageContext` 只作为 legacy adapter，不是新逻辑主接口
- compat 主链已降级为显式 legacy/smoke-only

### 9.3 `AgentReview artifact` 验收

- reviewer 正式架构是“单文档、单 agent、文档级并发、两阶段 review”
- `agent-review-worker` 能产出真实 artifact
- `approval-service` 不再依赖 stub/伪 artifact 作为正式路径
- `anchored_findings` 支持 0 个、1 个或多个 finding
- 相近问题经过去重后不会被拆成多条重复 finding
- 主 review 有风险但无稳定证据时允许空 findings

### 9.4 最终全链路验收

- approval 能把真实 findings 提供给 workbench
- workbench 能把 findings 投影为结构化问题列表
- 未匹配 findings 能通过 matcher 回填 `evidence_id/page_from/page_to`
- frontend 能在已匹配与未匹配两种情况下展示问题并跳转


## 10. 建议实施顺序

最稳妥的顺序：

1. 先做 Phase S，先止血
2. 再做 Phase 0，冻结 compat 扩散，并前移 fail-fast
3. 再做 Phase 1，解决 source file / intake job owner 冲突，并前移默认验证路径切换
4. Phase 1 完成后立刻建立最小真实链路 smoke
5. 再做 Phase 2A，先把 split workers 的依赖与导入目标显式化
6. 如 2A 后仍有明显共享实现耦合，再做 Phase 2B shared runtime
7. 再做 Phase 3，清理 fallback / shim / `StageContext`
8. 再做 Phase 4，退役根 compat 主链
9. 整改主线稳定后，再做 Phase 5，收口真实 `AgentReview artifact`
10. 再做 Phase 6 workbench / indexing 闭环集成
11. 最后做 Phase 7 删除旧代码

禁止事项：

- 不要跳过 Phase S，直接跑整套测试
- 不要跳过 owner / 链路整改，直接做 findings 投影
- 不要把 shared runtime 抽包误当成当前最小前置项

正确顺序是：**先止血，再收口边界，再补 artifact，最后接闭环。**
