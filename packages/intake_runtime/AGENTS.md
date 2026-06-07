# intake_runtime — 文档摄入管道运行时

## 定位
intake_runtime 是 Reality-RAG 文档摄入管道的核心运行时库，实现了 3-stage 管道：Conversion → Agent Review → Publishing。支持两种执行模式：单进程协调（`OrchestratorService`）和事件驱动（split workers）。

**不做的事**：不直接操作数据库（通过 persistence 的 Repository）、不属于具体的 worker 进程（worker 各自引用此包）、不管理用户态工作台。

## 边界原则
- 每个 stage 有纯函数 executor（`pure_stages.py`），输入=DTO + 依赖注入，输出=DTO
- Stage 间数据传递通过 `StageContext`（`stages/protocol.py:27`）
- Stage input/output 带确定性 hash（`input_hash` / `result_hash`），用于幂等和变更检测
- 日志记录通过 `hash_utils.py` 的 `canonical_json` + `sha256_hash`
- 转换器（`converters/`）采用策略模式：`BaseConverter` ABC → `RAGFlowConverter`（HTTP 代理）
- 代理审核（`agent_reviewer.py`）采用两轮策略：主审核 + 条件性发现提取，支持缓存
- DB Lease（`lease_service.py`）保证阶段任务不被多 worker 重复抢
- 事件通过事务性 outbox 发布（`OrchestratorService` → `EventPublisher`）

## 核心数据流
```
SourceFile ready
  │
  ▼ Conversion Stage
  ├── 选择转换器 (RAGFlowConverter)
  ├── 运行解析 → ConversionResult + QualityReport
  ├── 版本冲突检测 → VersionConflictInfo
  └── out: ConversionStageOutput
  │
  ▼ Review Stage
  ├── 检查缓存 AgentReviewCache (key=content+quality+collection+model)
  ├── DeepSeekAgentReviewer 两轮审核
  ├── 结果缓存 24h (approve) / 不缓存 (reject)
  └── out: ReviewStageOutput
  │
  ▼ Publishing Stage
  ├── build_canonical_metadata
  ├── persist_document_and_policy
  ├── build_index_asset_bundle (ChunkAsset + OpenSearch + Qdrant)
  └── out: PublishingStageOutput
  │
  ▼ Outbox: StageCompleted (+ ApprovalRequested / PublishCompleted)
```

## 关键对象
- `StageContext`：所有 stage 共享的可变上下文（`stages/protocol.py:27`）
- `PipelineStage` Protocol：`run(ctx: StageContext) -> StageContext`（`stages/protocol.py:66`）
- `{StageName}StageInput` / `{StageName}StageOutput`：每个 stage 的输入输出 DTO
- `DeepSeekAgentReviewer`：两轮 LLM 审核引擎（`agent_reviewer.py:88`）
- `OrchestratorService`：job/task/attempt 生命周期 + outbox 事件管理（`orchestrator.py:38`）
- `StageTaskLeaseService`：DB 租约管理（`lease_service.py:17`）
- `RAGFlowConverter`：HTTP 代理转换器（`converters/ragflow_converter.py:34`）

## 约束
- 纯 stage executor 不依赖 `StageContext`（`pure_stages.py` 设计原则）
- `stage_runtime.py` 提供的顶层函数（`run_conversion`/`run_review`/`run_publishing`）不可在纯函数中调用
- 适配器函数（`adapters.py`）负责 `Context ↔ DTO` 双向转换，不得绕过
- 审核缓存 `AgentReviewCache` Protocol 支持 `InMemoryAgentReviewCache` / `RedisAgentReviewCache`
- 审核缓存的 TTL：approve=86400s，其他=None
- `do_approve` 时跳过 LLM 发现提取（`agent_reviewer.py:92`）
- publish 状态下跳过审核和发布（`skip_reason` 记录）
- 版本冲突检测在 conversion 阶段完成，结果存入 `VersionConflictInfo`
