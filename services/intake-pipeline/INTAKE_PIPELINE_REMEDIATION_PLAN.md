# Intake Pipeline Remediation Plan

## 1. 结论

`services/intake-pipeline` 当前仍是过渡态系统，不是边界清晰、可独立部署、可验证的正式服务集合。

当前问题不是单点 bug，而是几类结构性问题叠加：

- owner 边界不清：`source file`、`intake job`、`approval`、`publish`、`indexing` 仍有职责重叠
- 正式链路与 compat/smoke 链路混杂，根 `intake_pipeline.main` 仍在冒充正式入口
- split workers 仍大量反向依赖 `ingestion-worker` 内部实现
- fallback / shim / legacy `StageContext` 仍承载主链
- `AgentReview artifact` 仍是 stub，无法复核、无法定位、无法成为后续结构化问题流转的基础

本次整改的目标不是继续在过渡态架构上补功能，而是：

1. 收敛 owner 边界
2. 固化真实正式链路
3. 清理 compat / shim / fallback
4. 在稳定主链上实现真实 `AgentReview artifact`


## 2. 当前阶段约束

本轮整改必须遵守以下约束：

1. **只能改当前工作树**
   - 工作目录限定在 `C:\Users\LLT\.codex\worktrees\9785\Enterprise KnowledgeBase`

2. **当前阶段可以改 `workbench-api`，但不能让它成为 owner**
   - `workbench-api` 可以进入正式实施范围
   - 允许落地 approval 回调、projection、matcher、routes、frontend 跳转
   - 但 `workbench-api` 仍然只能承担 projection / read-model / adapter / UI integration，不得承担 source file、review artifact、indexing chunk 的 owner 职责

3. **当前阶段先不要做 agent 缓存方案**
   - 不把 prompt cache、input cache、二次 review cache 作为本轮交付项
   - 现有 cache 实现即使暂时保留，也不得成为新的 owner、主键或跨服务契约基础

4. **要保留完整闭环目标，并按 owner 边界正确落地**
   - 你最初提出的 intake -> approval -> workbench -> matcher -> frontend 闭环仍然是正式目标
   - 现在这条闭环可以进入实施，但必须建立在前面 owner、artifact、compat、fail-fast 已经收口的基础上


## 3. 目标边界

最终边界应收敛为：

| 模块 | 应保留职责 | 不应继续承担 |
|---|---|---|
| `document-service` | upload session、object blob、source file、scan、`FileReady` outbox | approval、publishing、indexing、workbench projection |
| `ingestion-worker` | orchestrator、`intake_job` state、stage scheduling、outbox dispatch | conversion/review/publishing 具体执行、document owner API、indexing owner API |
| `conversion-worker` | conversion stage execution | source file owner、approval、publishing、indexing owner |
| `agent-review-worker` | review stage execution、真实 `AgentReview artifact` 生成与持久化 | approval decision、stub artifact、workbench projection、finding 二次分发 owner |
| `approval-service` | ticket lifecycle、decision、`final_doc_id`、approval audit、`AgentReview artifact` 只读查询 | review 执行、stub artifact 生成、finding 结构二次拼装 |
| `publishing-worker` | publish stage、published document state、asset/document persist、index build command | approval decision、retrieval direct lifecycle patch |
| `services/indexing` | parse snapshot / chunk / indexing owner | intake compat owner |
| `src/intake_pipeline/main.py` | compat/smoke helper only | 正式 intake owner、正式 internal API、正式 publish/index 主链 |

正式链路应固定为：

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
- `approval-service` 只读 review artifact，不再生成 stub
- 当前阶段不让 `workbench` 成为任何 owner


## 4. 已确认的核心问题

### 4.1 根 `intake_pipeline.main` 仍像正式服务

问题：

- 仍暴露 `/v1/documents`、`/v1/approval-tickets`、`/internal/source-files` 等混合接口
- 仍以本地状态、直连 publish/indexing 等逻辑承载业务
- compat/smoke 成功会掩盖真实链路问题

整改方向：

- 明确降级为 `SMOKE/COMPAT ONLY`
- 不再向它新增正式业务能力
- 默认验证路径尽快迁出


### 4.2 `/internal/source-files` 双 owner

问题：

- 根服务与 `document-service` 同时承载 `/internal/source-files`
- contract / 实现 / 下游调用语义不一致

整改方向：

- `document-service` 成为唯一 source file owner
- `ingestion-worker` 成为唯一 `intake_job` lifecycle owner
- 正式链路从 `FileReady outbox` 启动


### 4.3 split workers 仍依赖 `ingestion_worker.*`

问题：

- `conversion-worker`、`agent-review-worker`、`publishing-worker` 仍反向 import `ingestion_worker` 内部实现
- 目录拆分了，但运行时边界没有真正拆开

整改方向：

- 先显式收口运行时依赖
- 只有在 2A 后仍有结构性共享实现耦合时，才做 shared runtime 抽包


### 4.4 fallback / shim / `StageContext` 仍在主链

问题：

- fallback 让错误拓扑在开发环境里继续“假装可用”
- shim 继续诱导新代码依赖旧路径
- `StageContext` 让新逻辑继续接触 legacy session/repo/identity

整改方向：

- fail-fast 前移
- shim 明确弃用并逐步删除
- `StageContext` 退回 adapter 层，不再作为新逻辑核心接口


### 4.5 `AgentReview artifact` 仍是 stub

问题：

- `approval-service` 的 `/internal/tickets/{ticket_id}/agent-review` 当前返回硬编码 artifact
- `quality_findings`、`risk_flags`、`evidence_anchors`、`suggested_fixes` 都是空壳
- 无法回答“哪里有问题、问题是什么、证据在哪”

整改方向：

- `agent-review-worker` 产出真实 artifact
- `approval-service` 只读 artifact
- 删除 stub 返回


## 5. 对你最初 8 点方案的取舍

你最开始提出的 8 点方案没有错，**作为最终闭环蓝图是可以完成的**。但按当前工作树和“不要留下技术债”的要求，必须做取舍。

### 5.1 不采用“只改第 5 个 subtask prompt + schema”作为正式方案

原始想法：

- 在 `services/intake-pipeline/ingestion-worker/src/ingestion_worker/agent_reviewer.py`
- 只改第 5 个 subtask（`decision`）的 prompt 和输出 schema
- 让它在输出 `decision` / `reasons` 的同时输出 `anchored_findings`
- 不改 subtask 数量，不增加 LLM 调用次数

这**不应作为正式整改方案**，原因是：

- 它把“是否有问题”和“如何提取稳定证据”绑在一次输出里，长期会耦合 decision 与 evidence extraction
- 它会把当前错误的 reviewer 架构继续固化为正式架构
- 你明确提出的去重规则、无稳定证据时允许空 findings、一个文档一次输出全部问题，这些在 decision subtask 上硬塞进去，质量和可控性都不够
- 后续如果要演进到更稳定的 reviewer，反而要拆第二次

结论：

- **第 1 点可以作为探索性 spike 的思路，但不进入正式 remediation plan**
- 正式方案应直接走“单文档、单 agent、文档级并发、两阶段 review”


### 5.2 `contracts` 增加 `anchored_findings` 是正式方案的一部分

原始想法：

- 在 `packages/contracts/src/reality_rag_contracts/models.py`
- 给 `AgentReview` 新增可选 `anchored_findings: list[AnchoredFinding]`
- 新增 `AnchoredFinding` 子模型

这部分保留，但要调整成**不制造字段层级技术债**的版本：

- `AgentReview` 新增 `anchored_findings`，保持向后兼容
- `AnchoredFinding` 只包含 finding 自身字段
- `source_file_id`、`parse_snapshot_id`、`review_run_id`、`artifact_version` 属于 artifact envelope，不要在每个 finding 上重复


### 5.3 approval 向 workbench 透传 findings 现在进入正式实施范围

原始想法：

- `approval-service` 的事件 payload 携带完整 findings 发给 workbench

这不再是“后续再做”的事项，而是 `AgentReview artifact` 落地后的下一阶段正式工作：

- `approval-service` 继续保持“只读真实 artifact”的边界，不在 workbench 集成时回退成拼装 stub
- approval callback / projection / matcher 现在可以正式接入
- 但透传时必须直接沿用 artifact 里稳定生成的 finding 结构，不允许下游重新发明字段语义


### 5.4 workbench / matcher / routes / frontend 现在进入正式实施范围

原始 4-8 点方案不再只是后续目标，而是当前可以执行的正式阶段：

1. approval callback 携带完整 findings
2. adapter 将每个 finding 展开成 projection event
3. projector 写入 agent review projection
4. matcher 用 `source_quote` 对 chunk 做模糊匹配
5. routes 返回 matched / unmatched findings
6. frontend 用 `source_quote` 做搜索跳转

但有几个关键修正必须现在就定死：

- `finding_id` 不能由 approval 或 adapter 临时生成随机 UUID
- `finding_id` 必须由 review artifact 生产侧稳定生成，并一路透传到下游
- `workbench-api` 只能消费 artifact / callback / indexing chunk 内容，不能反向变成 review artifact owner
- matcher 只能做“匹配与回填”，不能重写 finding 语义本身


## 6. AgentReview 的正式目标设计

这一节必须纳入 remediation 主线，不是旁支小功能。

### 6.1 reviewer 目标架构

reviewer 的正式目标架构应为：

- **单文档、单 agent**
- **文档级并发**
- **两阶段 review**

这里的“并发”是指**多份文档并行处理**，不是把一份文档拆成多个字段级子任务并行跑。


### 6.2 Phase A：Main Review

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

职责：

- 回答“这份文档整体是否有问题”
- 给出审批与发布判断
- 不强制输出 `anchored_findings`


### 6.3 Phase B：Findings Extraction

触发条件：

- `decision != approve`
- 或 `publish_recommendation != published`
- 或 `confidence < REVIEW_FINDINGS_THRESHOLD`
- 或命中 `REVIEW_FINDINGS_REQUIRED_TAGS`

输出：

- `anchored_findings[]`

要求：

- 仍然是**一份文档一次调用**
- 一次性输出该文档的全部主要问题
- 不是把一个文档拆成多个问题分别调用

配置约束：

- `REVIEW_FINDINGS_THRESHOLD` 必须是显式配置
- `REVIEW_FINDINGS_REQUIRED_TAGS` 必须是显式配置
- reviewer 行为 owner 固定在 `intake-pipeline`


### 6.4 第二次 prompt 必须包含的规则

第二次 findings extraction prompt 必须明确要求模型：

1. 输出该文档的全部主要问题
2. 按严重度排序
3. 多个本质相同的问题只保留一个 finding
4. 如果多个片段都支持同一问题，只保留最有代表性的 `source_quote`
5. 无法稳定定位原文证据时，不要编造 finding
6. 即使主 review 判断有风险，只要无法提取稳定片段，也允许 `anchored_findings=[]`

这条规则是正式要求，不是可选优化。


### 6.5 `source_quote` 的要求

`source_quote` 必须是可复核、可搜索、可后续匹配 chunk 的文本片段。

当前阶段要求：

- 以问题片段为中心，包含前后约 50 个字符上下文
- 优先保持自然句子边界；做不到时再按字符窗口截断
- 必须保留原文顺序，不做总结性改写
- 允许因文档头尾而短于 100 字


### 6.6 artifact envelope、finding 字段与 owner

这是本轮必须一次定对的地方。

#### artifact envelope 必须至少包含

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

#### artifact summary 必须至少包含

```text
document_type
suggested_authority_level
detected_pii
diff_summary
decision
confidence
reasons
risk_tags
suggested_actions
publish_recommendation
sections_requiring_review
```

#### 每个 `AnchoredFinding` 必须至少包含

```text
finding_id
source_quote
problem_summary
severity
confidence
```

这里要特别强调：

- `source_file_id` 和 `parse_snapshot_id` **不能后置**
- 但它们属于 **artifact envelope**
- 不应该冗余复制到每一个 finding 上

这样做的原因是：

- 后续 workbench / matcher 需要稳定归属关系
- 但 finding 重复携带 owner 字段会制造冗余和演进负担


### 6.7 `finding_id` 规则

`finding_id` 必须由 review artifact 生产侧稳定生成，而不是由 approval 或 adapter 下游临时生成。

推荐规则：

```text
finding_id = sha256(
  source_file_id
  + parse_snapshot_id
  + normalized_problem_summary
  + normalized_source_quote
)
```

目标不是保证跨所有 rerun 绝对不变，而是：

- 避免随机 UUID 带来的无意义漂移
- 降低后续投影、人工审阅、问题引用的不稳定性


### 6.8 artifact 的写入与读取边界

必须定死：

- `agent-review-worker` 是 artifact 唯一写入方
- `approval-service` 是 artifact 只读消费方
- `approval-service` 不得从多个表临时拼一个“伪 artifact”
- cache 不得充当 artifact store

读取路径要求：

- `approval-service` 必须通过稳定 lookup 读取 artifact
- lookup 至少支持 `ticket_id -> intake_job_id/source_file_id/parse_snapshot_id -> review artifact`
- 同一 `review_run_id` 重试必须幂等，不生成重复 artifact


## 7. 分阶段整改计划

本计划分两条线推进：

1. **整改主线**：先把 owner、链路、运行时边界、fallback、compat 收口
2. **能力建设主线**：在整改主线稳定后，实现真实 `AgentReview artifact`

这样做是为了避免把“边界整改”和“能力建设”绑在一趟车上。


### 7.1 整改主线

#### Phase 0：冻结 compat 扩散，前移 fail-fast

目标：

- 先停止继续往 compat 链路堆功能
- 尽早暴露错误拓扑，而不是继续靠 fallback 伪装成“真实链路”

动作：

- 标记 `src/intake_pipeline/main.py` 为 `SMOKE/COMPAT ONLY`
- README / 启动脚本明确区分真实链路与 compat 链路
- 不再向根 `intake_pipeline.main` 新增正式业务接口
- 给 shim 加 deprecation 标记
- 前移 fail-fast：
  - 生产环境要求显式 downstream URL
  - 缺失必要 URL 时直接 fail fast
  - `ALLOW_LOCAL_FALLBACK_FOR_TESTS=true` 只允许测试或显式 smoke 使用

验收：

- 默认开发/运行路径下，缺失关键 downstream 配置不会静默走本地 fallback
- 文档明确声明正式 owner 边界和 compat 边界


#### Phase 1：统一 source file owner，并前移默认验证路径

目标：

- `/internal/source-files` 只有一个正式 owner
- source file owner 与 intake job owner 明确分离
- 默认验证路径切到真实链路

动作：

- `document-service` 接管 `/internal/source-files`
- 更新 contract / schema / OpenAPI owner 描述
- source file 注册成功后写 `FileReady outbox`
- `ingestion-worker` 消费后创建 `intake_job`
- README、脚本、smoke 默认路径切到：
  - `document-service -> FileReady -> ingestion-worker`
- compat 路径保留，但降级为显式 `legacy/smoke-only`

验收：

- source file 持久化与 idempotency 正常
- `document-service -> FileReady -> ingestion-worker intake_job created` 真实链路 smoke 通过
- README / 脚本 / 默认 smoke 不再把根 `intake_pipeline.main` 作为首选正式入口


#### Phase 2A：显式收口运行时边界

目标：

- 先拿到“可部署、可测试、依赖显式”的 split workers

动作：

- split workers 不再依赖隐式 `PYTHONPATH` / workspace layout 才能运行
- 清理启动脚本里把 `ingestion-worker/src` 直接塞给其它 worker 的默认方式
- 让包依赖和运行依赖都显式化

验收：

- split workers 不再依赖隐式 `PYTHONPATH`
- 能证明运行时边界已显式化


#### Phase 2B：确有必要时再提 shared runtime

目标：

- 只在 2A 完成后仍存在明显共享实现耦合时，再提 shared runtime

动作：

- 提取 shared runtime
- `conversion-worker` / `agent-review-worker` / `publishing-worker` 改为依赖 shared package
- `ingestion-worker` 自身也改为依赖 shared package

说明：

- 2B 不是整改主线的前置阻塞项
- 2B 是长期结构整理，不是为了前期“证明边界存在”

验收：

- 共享实现的归属清晰
- 抽包不再依赖隐式 workspace layout


#### Phase 3：清理 shim / fallback / `StageContext`

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


#### Phase 4：退役根 compat 主链

目标：

- `/v1/documents` 不再作为默认正式主链

动作：

- compat smoke 与 real-chain smoke 分开
- README 默认流程维持真实链路
- 根 `intake_pipeline.main` 不再被正式消费者使用

验收：

- 真实链路 smoke 不依赖 `/v1/documents`
- compat 链路只作为显式 legacy/smoke helper 存在


### 7.2 能力建设主线

#### Phase 5：实现真实 `AgentReview artifact`

这是完整方案的一部分，但属于**能力建设**，不是“先把 owner 边界拉直”的最小整改项。

前置条件：

- 整改主线至少完成到 Phase 3
- 默认验证路径已经切到真实链路
- reviewer / approval 所依赖的 owner 与 transport 已稳定


##### Phase 5A：重构 reviewer 架构

- 正式架构改为“单文档、单 agent、文档级并发、两阶段 review”
- 不再把“单文档内 5 个字段级 LLM 调用并行”当作长期正式架构
- 不把“只改第 5 个 subtask prompt + schema”纳入正式方案


##### Phase 5B：扩 contracts

- 在 `AgentReview` 中新增可选 `anchored_findings`
- 新增 `AnchoredFinding` 子模型
- 保持向后兼容，现有字段不删不改


##### Phase 5C：持久化真实 artifact

- `agent-review-worker` 写入真实 review artifact
- artifact 具备稳定 envelope、summary、findings、审计元数据
- cache 即使暂时保留，也只是实现细节，不得成为 public contract


##### Phase 5D：`approval-service` 改为只读 artifact

- `/internal/tickets/{ticket_id}/agent-review` 查询真实 artifact
- 删除 stub 返回
- `approval-service` 不再二次拼装 findings


##### Phase 5 验收

- 人工审批 ticket 能拿到真实 `AgentReview artifact`
- artifact 至少能稳定定位到 `source_file_id` 和 `parse_snapshot_id`
- 对有问题的文档，能返回完整 `anchored_findings`
- 对无问题的文档，允许 `anchored_findings=[]`
- 主 review 判断有风险但无法提取稳定证据时，也允许 `anchored_findings=[]`


#### Phase 6：workbench / indexing 闭环集成

这一阶段现在进入正式实施范围，但它仍然是建立在前面主链整改和真实 `AgentReview artifact` 已落地的前提上。

这一阶段要做：

1. approval callback / event payload 携带完整 findings
2. adapter 将每个 finding 展开为 projection event
3. projector 写入 agent review projection
4. matcher 扫描未匹配 findings
5. 调 indexing 的 `parse-snapshots/{id}/chunks` 拿 chunk 全文
6. 对 `source_quote` 与 chunk content 做模糊匹配
7. 回填 `evidence_id / page_from / page_to`
8. routes 返回 matched / unmatched findings
9. frontend 用 `source_quote` 做搜索与跳转

这里对应你最早提出的 3-8 点闭环方案。  
结论是：**可以完成，而且现在应当作为正式阶段实施，但不能破坏前面已经收好的 owner 边界。**


#### Phase 7：删除旧代码

删除顺序：

1. 删除纯 re-export shim
2. 删除 local fallback 分支
3. 删除 `IngestionPipeline.run()` 作为正式入口的用法
4. 删除根 `intake_pipeline.main` 的 source file compat API
5. 删除根 `intake_pipeline.main` 的 publish/index 直连链路
6. 如 smoke 已迁移，移动或删除根 `intake_pipeline.main`

每一步删除前必须跑：

```text
services/intake-pipeline/* tests
contracts tests
real-chain smoke or targeted smoke
```


## 8. 当前阶段做与不做

### 当前阶段做

- 整改主线 Phase 0-4
- 在整改主线稳定后推进 Phase 5

当前阶段重点：

- owner 收敛
- 默认验证路径切到真实链路
- 运行时依赖显式化
- fallback / shim / `StageContext` 清理
- 在稳定主链上实现真实 `AgentReview artifact`


### 当前阶段不做

- 新的 agent 缓存设计与实现


## 9. 验收标准

### 整改主线验收

整改主线完成后，应满足：

- `document-service` 是唯一 source file owner
- `ingestion-worker` / orchestrator 是唯一 `intake_job` owner
- 默认验证路径已经切到真实链路
- split workers 的依赖与运行边界已显式化
- 生产不启用 local fallback
- `StageContext` 只作为 legacy adapter，不是新逻辑主接口
- compat 主链已降级为显式 legacy/smoke-only


### `AgentReview artifact` 验收

Phase 5 完成后，应满足：

- reviewer 正式架构是“单文档、单 agent、文档级并发、两阶段 review”
- `agent-review-worker` 能产出真实 artifact
- `approval-service` 不再返回 stub AgentReview
- `anchored_findings` 支持 0 个、1 个或多个 finding
- 相近问题经过去重后不会被拆成多条重复 finding
- 主 review 有风险但无稳定证据时允许空 findings
- 当前阶段不引入新的 agent cache 复杂度


### 最终全链路验收

后续闭环完成后，还应满足：

- approval 能把真实 findings 提供给 workbench
- workbench 能把 findings 投影为结构化问题列表
- 未匹配 findings 能通过 matcher 回填 `evidence_id/page_from/page_to`
- frontend 能在已匹配与未匹配两种情况下展示问题并跳转


## 10. 建议实施顺序

最稳妥的顺序：

1. 先做 Phase 0，冻结 compat 扩散，并前移 fail-fast
2. 再做 Phase 1，解决 source file / intake job owner 冲突，并前移默认验证路径切换
3. Phase 1 完成后立刻建立最小真实链路 smoke
4. 再做 Phase 2A，先把 split workers 的依赖显式化
5. 如 2A 后仍有明显共享实现耦合，再做 Phase 2B shared runtime
6. 再做 Phase 3，清理 fallback / shim / `StageContext`
7. 再做 Phase 4，退役根 compat 主链
8. 整改主线稳定后，再做 Phase 5，实现真实 `AgentReview artifact`
9. 再做 Phase 6 workbench / indexing 闭环集成
10. 最后做 Phase 7 删除旧代码

不要跳过前面的 owner / 链路整改，直接做 findings 投影。  
也不要把 shared runtime 抽包和 `AgentReview artifact` 能力建设，误当成“先把边界拉直”的最小前置项。  
正确顺序是：先把主链、owner、默认验证路径和 fail-fast 做实，再补 review artifact 能力，最后再接 workbench 闭环。
