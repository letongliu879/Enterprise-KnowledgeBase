# intake-pipeline 企业级摄入控制面设计

## 1. 定位

`intake-pipeline` 是 Enterprise KnowledgeBase 的企业知识摄入控制面。它负责把外部文件安全、可审计、可恢复地转化为可检索、可治理、可发布的知识文档。

索引与检索最终态分别见：`services/indexing/indexing.md`、`services/retrieval/retrieval.md`。

本模块不是简单的 ETL 链路，也不是几个服务顺序调用。它的核心职责是：

- 接收原始文件并管理对象存储引用
- 执行确定性转换、清洗、质量评分、相似度检测、版本线索检测
- 执行 PII 与 visibility 风险审核
- 执行自动批准或人工审批
- 统一生成最终文档身份、标签、审计记录
- 幂等发布资产、数据库记录、索引
- 在失败、重试、重复消息、人工打回、部分发布失败时保持状态一致

统一边界补充：

- 文档、分库、ACL、审批、发布、生命周期由 `intake-pipeline` 与其下游发布域共同定义。
- `services/workbench-api` 只负责解析/分块预览与人工校验，不拥有文档治理真相。
- intake 可以消费 indexing 产出的 ParseSnapshot，但不拥有 parser/chunker 主链。
- intake 产生的 `canonical_md` / `sanitized_md` 如果暂时存在，只能视为治理辅助资产或过渡产物，不能定义 indexing 的正式解析入口。
- `dataset_id/file_id` 只能作为 indexing workbench 引用，不得替代 `collection_id/final_doc_id`。

## 2. 架构全景

```
[外部文件来源]
  Web Admin / CLI / Feishu / Webhook
        |
        v
┌────────────────────────────────────────────────────┐
│ document-service                                   │
│ - upload session                                   │
│ - object_ref / content_hash 去重                    │
│ - malware scan                                     │
│ - source_file_state                                │
│ - outbox: FileReady                                │
└──────────────────────┬─────────────────────────────┘
                       |
                       v
┌────────────────────────────────────────────────────┐
│ intake-orchestrator                                │
│ - intake_job_state 唯一 owner                       │
│ - stage scheduling                                 │
│ - retry / timeout / compensation                   │
│ - idempotency / input_hash                         │
│ - outbox / event dispatch                          │
└───────┬──────────────────┬──────────────────┬──────┘
        |                  |                  |
        v                  v                  v
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ conversion-     │  │ agent-review-   │  │ approval-       │
│ worker          │  │ worker          │  │ service         │
│ deterministic   │  │ risk facts      │  │ decision        │
└───────┬────────┘  └───────┬────────┘  └───────┬────────┘
        |                   |                   |
        └───────────────────┴───────────────────┘
                            |
                            v
┌────────────────────────────────────────────────────┐
│ publishing-worker                                  │
│ - asset write                                      │
│ - document persist                                 │
│ - indexing orchestration                           │
│ - publish_state                                    │
│ - idempotent publication                           │
└──────────────────────┬─────────────────────────────┘
                       |
                       v
┌────────────────────────────────────────────────────┐
│ indexing-service                                   │
│ - chunking / embedding                             │
│ - vector index upsert                              │
│ - index activate / rollback                        │
│ - outbox: IndexReady                               │
└──────────────────────┬─────────────────────────────┘
                       |
                       v
┌────────────────────────────────────────────────────┐
│ retrieval-service                                  │
│ - active index_version discovery                   │
│ - collection / visibility / lifecycle filtering    │
│ - tombstone handling                               │
└────────────────────────────────────────────────────┘
```

### 2.1 组件职责

| 组件 | 负责 | 不负责 |
|------|------|--------|
| document-service | 原始文件接收、对象引用、扫描、source file 生命周期 | 文档转换、审批、发布 |
| intake-orchestrator | 全局 job 状态机、阶段调度、重试、超时、补偿、事件编排 | 具体转换、LLM 审核、人工审批、写索引 |
| conversion-worker | 轻量标准化、质量、相似度、版本线索 | 正式 parser owner、chunking、embedding、发布、全局状态推进 |
| agent-review-worker | PII span、visibility 风险事实、review 结果持久化 | 最终发布决策、标签治理 |
| approval-service | system auto approve、人工工单、final_doc_id、confirmed_tags、审批审计 | 转换、LLM 调用、写索引 |
| publishing-worker | asset write、document persist、发布编排、发布幂等 | 审批、风险判断、全局调度、chunking/embedding 细节 |
| indexing-service | 预解析、ParseSnapshot、chunking、embedding、vector index upsert、index activate/rollback | 审批、发布决策、全局 job 状态 |
| retrieval-service | 按已发布状态、collection、visibility、active index_version 检索 | 摄入、审批、发布、索引写入 |

`services/workbench-api` 面向文档处理人员与审批人员，其职责必须降格理解：

| 组件 | 负责 | 不负责 |
|------|------|--------|
| workbench-api | ParseSnapshot 展示、chunk 预览、参数调试、人工确认 | collection 治理、文档权限、审批结论、发布状态 |

### 2.2 发布事实源

发布域只能有一个事实源：`published_documents`。

`documents` / `document_policies` 如果继续存在，只能作为兼容读模型或旧系统投影，不得作为发布生命周期、检索可见性、撤回、归档、reindex、重复上传判断的事实源。

规则：

- `published_documents` 是 `final_doc_id` 发布状态、`active_index_version`、`source_content_hash`、visibility、confirmed tags 的唯一写入事实源。
- `documents` / `document_policies` 可以由 publishing domain 投影生成，但不得被其他服务直接写入。
- retrieval/indexing/admin 判断发布可见性时必须以 `published_documents` 或它的受控投影为准。
- 如果兼容期必须双写，双写 owner 仍是 publishing domain，且必须记录投影同步状态；投影失败不得伪装为发布成功。

### 2.3 默认异步、幂等、可重试

生产环境必须假设：

- 事件可能重复投递
- worker 可能在任意阶段崩溃
- 外部模型可能超时或限流
- 对象存储、数据库、索引可能局部失败
- 人工审批可能持续数天
- 同一文件可能同时上传到多个 collection

所有阶段必须支持幂等执行。重复执行同一阶段时，要么返回已有结果，要么安全重试，不得产生重复文档、重复索引、重复审计决策。

### 2.4 状态模型分层

系统固定五套状态，不得混用：

| 状态模型 | owner | 描述 |
|---------|-------|------|
| `source_file_state` | document-service | 原始文件上传、扫描、消费、清理 |
| `intake_job_state` | intake-orchestrator | 摄入任务从创建到完成的全局进度 |
| `approval_ticket_state` | approval-service | system decision 或人工工单生命周期 |
| `publish_state` | publishing-worker | asset、persist、index 的发布进度 |
| `published_document_state` | publishing domain | 已发布文档的可检索、下架、归档、重建索引状态 |

## 3. 身份标识与状态模型

### 3.1 身份标识

#### 标识列表

| 标识 | 生成方 | 作用域 | 是否最终稳定 | 示例 |
|------|--------|--------|--------------|------|
| `upload_id` | document-service | 一次上传会话 | 是 | `upl_01J...` |
| `source_file_id` | document-service | 单个 collection 下的原始文件记录 | 是 | `src_01J...` |
| `object_id` | document-service | 物理对象内容 | 是 | `obj_sha256_abcd...` |
| `intake_job_id` | intake-orchestrator | 单个 source_file 的摄入任务 | 是 | `job_01J...` |
| `stage_attempt_id` | intake-orchestrator | 单次阶段尝试 | 是 | `att_01J...` |
| `preliminary_doc_id` | conversion-worker | 摄入链路内候选文档 | 是，链路内稳定 | `pre_q1_report_20260521_01J...` |
| `review_id` | agent-review-worker | 一次风险审核结果 | 是 | `rev_01J...` |
| `ticket_id` | approval-service | 审批记录或 system decision | 是 | `apv_01J...` |
| `final_doc_id` | approval-service | 最终文档身份 | 是 | `doc_q1_report_v1` |
| `publish_id` | publishing-worker | 一次发布执行 | 是 | `pub_01J...` |
| `trace_id` | 入口生成，链路透传 | 全链路追踪 | 是 | `trc_01J...` |

#### 标识规则

- 所有外部可见 ID 使用前缀加 ULID 或雪花 ID。
- 所有 ID 大小写固定，不允许同一字段有大小写变体。
- `final_doc_id` 一旦发布不得修改。
- `source_file_id` 是 per collection 的记录。同一物理对象进多个 collection 时，产生多个 `source_file_id`，共享同一个 `object_id`。
- `preliminary_doc_id` 不得对外暴露给检索服务，只用于摄入链路和审计追踪。

#### 幂等键

所有阶段必须有显式幂等键：

```
idempotency_key =
  "{intake_job_id}:{stage_name}:{schema_version}:{input_hash}"
```

其中：

- `stage_name` 固定枚举
- `schema_version` 是阶段输入契约版本
- `input_hash` 是阶段输入规范化 JSON 的 SHA-256

幂等规则：

- 同一 `idempotency_key` 已成功，直接返回已有 stage result
- 同一 `idempotency_key` 正在运行，orchestrator 不重复派发；worker 执行前通过 lease 再次校验
- 同一 `idempotency_key` 已失败且可重试，在同一个 `stage_task_id` 下创建新的 `stage_attempt_id`
- 不同 `input_hash` 必须视为不同阶段输入，不得复用旧结果
- 人工打回要求重跑时，orchestrator 创建新的 `stage_task_id`，并在 stage input 中加入 `rerun_round` 和 `return_reason_code`，使新的 `input_hash` 可解释、可审计

### 3.2 source_file_state

owner：document-service

```
UPLOADING
  -> UPLOADED
  -> SCANNING
  -> READY
  -> CLAIMED
  -> CONSUMED
  -> CLEANABLE
  -> CLEANED

任意非终态
  -> FAILED
```

| 状态 | 含义 | 允许进入方 |
|------|------|------------|
| `UPLOADING` | 上传会话已创建，分片或单文件传输中 | document-service |
| `UPLOADED` | bytes 已进入临时对象，hash 校验通过 | document-service |
| `SCANNING` | 恶意文件扫描中 | document-service |
| `READY` | 扫描通过，可被 orchestrator 创建 job | document-service |
| `CLAIMED` | 已被某个 intake_job 绑定 | intake-orchestrator 通过 document-service API |
| `CONSUMED` | intake 主线已成功消费原始文件，并产出治理所需阶段结果或触发后续预解析 | intake-orchestrator 通过 document-service API |
| `CLEANABLE` | 原始对象可进入 GC 判断 | document-service |
| `CLEANED` | 原始临时引用已清理 | document-service |
| `FAILED` | 上传、hash、扫描或读取失败 | document-service |

约束：

- `CONSUMED` 不表示文档已发布。
- `CLEANABLE` 不表示对象 bytes 一定能删除。对象删除必须检查 `object_ref`。
- 只有 `READY` 文件可以创建 intake job。
- 同一个 `source_file_id` 最多绑定一个 `intake_job_id`，由 `intake_jobs.source_file_id` unique 约束保证。
- active source file 定义为 state in (`UPLOADING`, `UPLOADED`, `SCANNING`, `READY`, `CLAIMED`, `CONSUMED`)。
- non-active source file 定义为 state in (`CLEANABLE`, `CLEANED`, `FAILED`)。
- `(content_hash, collection_id)` 的 active unique 约束必须实现为 partial unique index，仅约束 active source file。

### 3.3 intake_job_state

owner：intake-orchestrator

```
CREATED
  -> CONVERSION_QUEUED
  -> CONVERSION_RUNNING
  -> CONVERSION_SUCCEEDED
  -> REVIEW_QUEUED
  -> REVIEW_RUNNING
  -> REVIEW_SUCCEEDED
  -> APPROVAL_REQUESTED
  -> APPROVAL_DECIDED
  -> PUBLISH_QUEUED
  -> PUBLISH_RUNNING
  -> PUBLISHED

人工路径：
APPROVAL_REQUESTED
  -> AWAITING_APPROVAL
  -> APPROVAL_DECIDED

打回路径：
AWAITING_APPROVAL
  -> APPROVAL_DECIDED（decision = return）
  -> CONVERSION_QUEUED 或 REVIEW_QUEUED

失败路径：
任意可重试阶段
  -> RETRY_SCHEDULED
  -> 原阶段_QUEUED

终态：
PUBLISHED / REJECTED / FAILED / CANCELLED / EXPIRED
```

| 状态 | 含义 |
|------|------|
| `CREATED` | job 已创建，尚未派发阶段 |
| `*_QUEUED` | 阶段任务已入队 |
| `*_RUNNING` | worker 已领取任务 |
| `*_SUCCEEDED` | 阶段结果已持久化并通过契约校验 |
| `APPROVAL_REQUESTED` | 已向 approval-service 提交审批请求 |
| `AWAITING_APPROVAL` | approval-service 生成 PENDING 人工工单 |
| `APPROVAL_DECIDED` | 收到 approve/reject/return 决策 |
| `PUBLISH_*` | 发布阶段状态 |
| `PUBLISHED` | 文档资产、数据库、索引全部成功 |
| `REJECTED` | 审批拒绝或被判定重复上传 |
| `FAILED` | 不可恢复失败 |
| `CANCELLED` | 管理员取消 |
| `EXPIRED` | 超过治理 SLA，按策略关闭 |

约束：

- 只有 intake-orchestrator 可以写 `intake_jobs.state`。
- worker 不得直接写 `intake_jobs.state`。
- worker 只写 stage result，orchestrator 校验后推进状态。
- 状态迁移必须使用乐观锁或版本号。

### 3.4 approval_ticket_state

owner：approval-service

```
SYSTEM_DECIDED

PENDING
  -> APPROVED
  -> REJECTED
  -> RETURNED
  -> EXPIRED
```

| 状态 | 含义 |
|------|------|
| `SYSTEM_DECIDED` | auto approve 由系统规则完成，无人工 PENDING |
| `PENDING` | 等待人工审批 |
| `APPROVED` | 人工批准 |
| `REJECTED` | 人工拒绝 |
| `RETURNED` | 人工打回指定阶段 |
| `EXPIRED` | 工单超时关闭 |

约束：

- `SYSTEM_DECIDED` 与 `APPROVED` 都必须产生 `ApprovalDecided`。
- `final_doc_id` 只能在 approve 或 system auto approve 时生成。
- `REJECTED` 不得生成 `final_doc_id`。
- `RETURNED` 必须带 `return_target_stage` 和 `return_reason`。

### 3.5 publish_state

owner：publishing-worker

```
PUBLISH_CREATED
  -> ASSET_WRITING
  -> ASSET_WRITTEN
  -> PERSISTING
  -> PERSISTED
  -> INDEXING
  -> INDEXED
  -> PUBLISH_SUCCEEDED

任意阶段
  -> PUBLISH_RETRY_SCHEDULED
  -> 原阶段

不可恢复
  -> PUBLISH_FAILED
```

约束：

- asset、document record、index 三个动作必须分别记录状态。
- 发布重试必须幂等。
- `PUBLISH_SUCCEEDED` 之后才能让 intake job 进入 `PUBLISHED`。

## 4. 数据模型

### 4.1 document-service 表

核心表包括 `upload_sessions`、`object_blobs`、`source_files`、`malware_scan_results`。除显式标注的字段外，均含标准审计字段（`created_at`、`updated_at` 等）。

#### `upload_sessions`

| 字段 | 类型 | 约束 |
|------|------|------|
| `upload_id` | string | PK |
| `source` | enum | web / cli / feishu / webhook |
| `user_id` | string | nullable |
| `trace_id` | string | not null |
| `status` | enum | active / completed / expired / failed / cancelled |
| `expected_size` / `expected_sha256` | bigint / string | nullable |
| `received_size` | bigint | default 0 |
| `last_chunk_at` / `completed_at` | timestamp | nullable |

`expected_size` 和 `expected_sha256` 在客户端已知时必须提供；`/complete` 时服务端必须计算 SHA-256 和最终大小并回写。若客户端提供过 expected 值，complete 时必须严格比对。

#### `object_blobs`

| 字段 | 类型 | 约束 |
|------|------|------|
| `object_id` | string | PK, `obj_sha256_{hash}` |
| `content_hash` | string | unique |
| `storage_key` | string | not null |
| `size_bytes` | bigint | not null |
| `ref_count` | int | default 0 |
| `status` | enum | active / gc_pending / deleted |
| `deleted_at` | timestamp | nullable |

#### `source_files`

| 字段 | 类型 | 约束 |
|------|------|------|
| `source_file_id` | string | PK |
| `upload_id` / `object_id` | string | FK |
| `collection_id` | string | not null |
| `visibility` | enum | EXTERNAL / INTERNAL |
| `original_name` / `sanitized_name` | string | not null |
| `content_hash` / `size_bytes` | string / bigint | not null |
| `state` | enum | source_file_state |
| `claimed_by_job_id` | string | nullable, unique while active |
| `scan_result_id` | string | nullable |
| `expires_at` | timestamp | nullable |

唯一约束：`(content_hash, collection_id)` partial unique（仅 active state）；`source_file_id` unique。

#### `malware_scan_results`

| 字段 | 类型 | 约束 |
|------|------|------|
| `scan_result_id` | string | PK |
| `source_file_id` | string | FK |
| `engine` / `engine_version` | string | not null |
| `verdict` | enum | clean / infected / error |
| `signature` / `raw_result_ref` | string | nullable |
| `scanned_at` | timestamp | not null |

### 4.2 orchestrator 表

#### `intake_jobs`

| 字段 | 类型 | 约束 |
|------|------|------|
| `intake_job_id` | string | PK |
| `source_file_id` | string | unique |
| `object_id` | string | not null |
| `collection_id` | string | not null |
| `visibility` | enum | not null |
| `state` | enum | intake_job_state |
| `state_version` | int | optimistic lock |
| `current_stage` | enum | nullable |
| `preliminary_doc_id` | string | nullable |
| `review_id` | string | nullable |
| `ticket_id` | string | nullable |
| `final_doc_id` | string | nullable |
| `publish_id` | string | nullable |
| `attempt_count` | int | default 0 |
| `trace_id` | string | not null |
| `created_at` | timestamp | not null |
| `updated_at` | timestamp | not null |
| `deadline_at` | timestamp | nullable |

#### `stage_tasks`

| 字段 | 类型 | 约束 |
|------|------|------|
| `stage_task_id` | string | PK |
| `intake_job_id` | string | FK |
| `stage_name` | enum | conversion / agent_review / publishing |
| `idempotency_key` | string | unique |
| `schema_version` | string | not null |
| `input_hash` | string | not null |
| `state` | enum | queued / running / succeeded / failed / retry_scheduled / cancelled |
| `locked_by` | string | nullable |
| `lock_expires_at` | timestamp | nullable |
| `attempt_count` | int | default 0 |
| `rerun_round` | int | default 0 |
| `rerun_reason_code` | string | nullable |
| `next_run_at` | timestamp | not null |
| `created_at` | timestamp | not null |
| `updated_at` | timestamp | not null |

#### `stage_attempts`

| 字段 | 类型 | 约束 |
|------|------|------|
| `stage_attempt_id` | string | PK |
| `stage_task_id` | string | FK |
| `intake_job_id` | string | FK |
| `stage_name` | enum | not null |
| `attempt_no` | int | not null |
| `worker_id` | string | nullable |
| `state` | enum | running / succeeded / failed / timeout / cancelled |
| `error_code` | string | nullable |
| `error_summary_hash` | string | nullable |
| `started_at` | timestamp | not null |
| `finished_at` | timestamp | nullable |

唯一约束：

- `(stage_task_id, attempt_no)` unique

#### `stage_results`

`stage_results` 只保存成功产物。失败、超时、限流、schema invalid 等尝试结果写入 `stage_attempts`。

| 字段 | 类型 | 约束 |
|------|------|------|
| `stage_result_id` | string | PK |
| `stage_task_id` | string | FK, unique |
| `stage_attempt_id` | string | FK |
| `intake_job_id` | string | FK |
| `stage_name` | enum | not null |
| `idempotency_key` | string | not null |
| `result_hash` | string | not null |
| `result_ref` | string | object storage or jsonb |
| `summary_json` | jsonb | not null |
| `created_at` | timestamp | not null |

### 4.3 conversion-worker 表

#### `conversion_results`

| 字段 | 类型 | 约束 |
|------|------|------|
| `conversion_result_id` | string | PK |
| `intake_job_id` | string | FK |
| `content_hash` / `canonical_hash` | string | not null |
| `preliminary_doc_id` | string | not null |
| `canonical_md_ref` | string | not null |
| `quality_report` / `similarity_hints` | jsonb | not null |
| `version_conflict` | jsonb | nullable |
| `converter_name` / `converter_version` / `cleaning_version` / `schema_version` | string | not null |

唯一约束：`(intake_job_id, preliminary_doc_id)` unique。

复用规则：ConversionStage、CleaningStage、QualityStage 可按 `content_hash + converter_version + cleaning_version + schema_version` 复用；SimilarityCheck、VersionCheck 必须按 `collection_id` 查询，不能跨 collection 复用。

### 4.4 agent-review-worker 表

#### `agent_review_results`

| 字段 | 类型 | 约束 |
|------|------|------|
| `review_id` | string | PK |
| `canonical_hash` / `visibility` | string / enum | not null |
| `model_provider` / `model_name` / `model_version` | string | not null |
| `prompt_version` / `schema_version` | string | not null |
| `pii_report` / `sanitization_spans` / `visibility_check` | jsonb | not null |
| `routing_recommendation` | enum | auto_approve / require_approval |
| `review_status` | enum | succeeded / degraded / failed |

唯一约束：`(canonical_hash, visibility, model_provider, model_name, model_version, prompt_version, schema_version)`，仅用于成功 review 结果复用。失败尝试写入 `stage_attempts` 和 telemetry，不阻止后续重试。

### 4.5 approval-service 表

#### `approval_tickets`

| 字段 | 类型 | 约束 |
|------|------|------|
| `ticket_id` | string | PK |
| `intake_job_id` | string | not null |
| `approval_round` | int | not null |
| `preliminary_doc_id` | string | not null |
| `collection_id` | string | not null |
| `visibility` | enum | not null |
| `state` | enum | approval_ticket_state |
| `routing_recommendation` | enum | not null |
| `decision` | enum | nullable, approve / reject / return |
| `decision_actor` | string | nullable, user id or system |
| `decision_reason` | string | nullable |
| `final_doc_id` | string | nullable |
| `confirmed_tags` | jsonb | nullable |
| `return_target_stage` | enum | nullable |
| `created_at` | timestamp | not null |
| `decided_at` | timestamp | nullable |
| `expires_at` | timestamp | nullable |

唯一约束：

- `(intake_job_id, approval_round)` unique

每次进入人工审批或 system decision 都创建新的 approval ticket。打回后重新执行阶段并再次进入审批时，`approval_round` 递增，历史 ticket 和 audit 不覆盖。

#### `approval_audit_log`

所有审批决策必须追加审计日志，不允许 update 覆盖。

| 字段 | 类型 | 约束 |
|------|------|------|
| `audit_id` | string | PK |
| `ticket_id` | string | FK |
| `intake_job_id` | string | not null |
| `actor_id` | string | not null |
| `action` | enum | system_approve / approve / reject / return / expire |
| `before_state` | string | nullable |
| `after_state` | string | not null |
| `reason` | string | nullable |
| `payload_hash` | string | not null |
| `created_at` | timestamp | not null |

### 4.6 publishing-worker 表

#### `publish_jobs`

| 字段 | 类型 | 约束 |
|------|------|------|
| `publish_id` | string | PK |
| `intake_job_id` | string | unique |
| `final_doc_id` | string | unique |
| `collection_id` | string | not null |
| `state` | enum | publish_state |
| `asset_state` | enum | pending / succeeded / failed |
| `persist_state` | enum | pending / succeeded / failed |
| `index_state` | enum | pending / succeeded / failed |
| `idempotency_key` | string | unique |
| `attempt_count` | int | default 0 |
| `created_at` | timestamp | not null |
| `updated_at` | timestamp | not null |

`publish_jobs` 只表示 final_doc_id 的首次发布。已发布文档的重新索引不创建新的 publish job。

#### `reindex_jobs`

| 字段 | 类型 | 约束 |
|------|------|------|
| `reindex_job_id` | string | PK |
| `final_doc_id` | string | not null |
| `source_index_version` | string | nullable |
| `target_index_version` | string | not null |
| `state` | enum | queued / running / succeeded / failed / cancelled |
| `idempotency_key` | string | unique |
| `attempt_count` | int | default 0 |
| `requested_by` | string | not null |
| `reason` | string | nullable |
| `created_at` | timestamp | not null |
| `updated_at` | timestamp | not null |

唯一约束：

- `(final_doc_id, target_index_version, state)` partial unique where state in (`queued`, `running`)

发布幂等约束：

- `published_documents.final_doc_id` unique
- `documents.final_doc_id` unique 只作为兼容投影约束，不是发布事实源约束
- index write 使用 `final_doc_id + index_version` upsert
- asset path 使用 deterministic path：`collections/{collection_id}/docs/{final_doc_id}/...`

#### `published_documents`

最终文档记录归 publishing domain 所有。`services/admin` 只能通过 publishing domain 的管理接口或授权命令修改 lifecycle state，不得直接绕过审计写表。

| 字段 | 类型 | 约束 |
|------|------|------|
| `final_doc_id` | string | PK |
| `logical_document_id` | string | not null |
| `version` | int | not null |
| `collection_id` | string | not null |
| `visibility` | enum | INTERNAL / EXTERNAL |
| `published_document_state` | enum | PUBLISHED / ARCHIVED / DEPRECATED / RETRACTED / REINDEXING |
| `active_index_version` | string | nullable |
| `canonical_md_ref` | string | not null |
| `sanitized_md_ref` | string | not null |
| `metadata_ref` | string | not null |
| `source_content_hash` | string | not null |
| `canonical_hash` | string | not null |
| `confirmed_tags` | jsonb | not null |
| `supersedes_final_doc_id` | string | nullable |
| `previous_published_document_state` | enum | nullable |
| `created_by_ticket_id` | string | not null |
| `published_at` | timestamp | not null |
| `state_updated_at` | timestamp | not null |

唯一约束：

- `(collection_id, logical_document_id, version)` unique
- `final_doc_id` unique
- `(collection_id, source_content_hash)` non-unique index，用于重复上传时查找已发布文档
- `(collection_id, canonical_hash)` non-unique index，用于相似/重复排查，不作为唯一性约束

`active_index_version` 语义：

- 首次发布的 document 记录创建后、`IndexReady` 前为 null。
- `REINDEXING` 期间默认保留旧 `active_index_version`，新索引 activate 后原子切换为新 version。
- `RETRACTED` 不清空 `active_index_version`，用于审计追溯和受控修复；retrieval-service 必须依赖 `published_document_state` 过滤，不得仅凭该字段检索。
- 只有从未完成索引 activate 的文档允许长期为 null；这类记录不得进入 `PUBLISHED`。

active 切换规则：

- `active_index_version` 只能由 publishing domain 在消费匹配的 `IndexReady` 后条件更新。
- 条件更新必须匹配 `final_doc_id + publish_id/reindex_job_id + target_index_version + 当前 publish_state`。
- 首次发布时，`published_document_state` 只能在 `active_index_version` 已写入同一事务后进入 `PUBLISHED`。
- reindex 时，新 index activate 成功前必须保留旧 `active_index_version`，检索继续使用旧索引。
- 如果 `IndexReady` 已到但发布事务失败，publishing-worker 必须重试同一个 publish/reindex job，不得让 indexing 直接修改 published document 状态。
- retrieval active discovery 只能读取已提交的 `published_documents.active_index_version` 或由 publishing domain 发布的 `DocumentLifecycleChanged` / `PublishCompleted` 后续事件；不得单凭 `IndexReady` 暴露新索引。

#### `published_document_lifecycle_audit`

已发布文档生命周期变更只追加审计，不覆盖历史记录。

| 字段 | 类型 | 约束 |
|------|------|------|
| `lifecycle_audit_id` | string | PK |
| `final_doc_id` | string | not null |
| `from_state` | enum | nullable |
| `to_state` | enum | not null |
| `previous_published_document_state` | enum | nullable |
| `actor_id` | string | not null |
| `reason_code` | string | not null |
| `reason` | string | nullable |
| `command_id` | string | nullable |
| `payload_hash` | string | not null |
| `created_at` | timestamp | not null |

### 4.7 indexing-service 表

#### `index_build_jobs`

| 字段 | 类型 | 约束 |
|------|------|------|
| `index_build_job_id` | string | PK |
| `publish_id` / `reindex_job_id` | string | nullable，二选一 |
| `final_doc_id` / `collection_id` | string | not null |
| `visibility` | enum | INTERNAL / EXTERNAL |
| `target_index_version` / `chunker_version` / `embedding_model_version` | string | not null |
| `sanitized_md_ref` / `metadata_ref` | string | not null |
| `state` | enum | queued / chunking / embedding / upserting / activating / succeeded / failed |
| `chunk_count` / `embedding_count` | int | nullable |
| `idempotency_key` | string | unique |
| `error_code` | string | nullable |

约束：`publish_id` 与 `reindex_job_id` 必须二选一；`(final_doc_id, target_index_version, state)` partial unique（active states）。成功后由 indexing-service outbox 发送 `IndexReady`。

#### `indexed_documents`

| 字段 | 类型 | 约束 |
|------|------|------|
| `final_doc_id` / `index_version` / `collection_id` | string | not null |
| `visibility` | enum | INTERNAL / EXTERNAL |
| `chunker_version` / `embedding_model_version` | string | not null |
| `chunk_count` / `embedding_count` | int | not null |
| `state` | enum | candidate / active / tombstoned |
| `activated_at` | timestamp | nullable |

唯一约束：`(final_doc_id, index_version)` unique。

### 4.8 配置表

#### `collection_configurations`

| 字段 | 类型 | 约束 |
|------|------|------|
| `collection_id` | string | PK |
| `approval_policy_id` | string | not null |
| `review_mode` | enum | rules_only / private_llm / external_llm |
| `auto_tags` | jsonb | not null |
| `approvers` | jsonb | not null |
| `max_parallel_jobs` | int | nullable |
| `config_version` | string | not null |
| `enabled` | bool | not null |
| `created_at` | timestamp | not null |
| `updated_at` | timestamp | not null |

#### `approval_policies`

| 字段 | 类型 | 约束 |
|------|------|------|
| `approval_policy_id` | string | PK |
| `collection_id` | string | nullable |
| `policy_json` | jsonb | not null |
| `config_version` | string | not null |
| `created_by` | string | not null |
| `created_at` | timestamp | not null |
| `updated_at` | timestamp | not null |

配置表由 admin/config domain 管理。配置变更必须写审计，并通过 config_version 被 stage task、approval decision、LLM call log 引用。

### 4.9 telemetry 表

telemetry 表用于排障、SLA、质量优化、成本核算。telemetry 不替代业务表、审计表、stage result，也不得保存文档正文、PII 原值、完整 prompt 明文或完整 LLM response 明文。

四张表共享标准遥测字段（`trace_id`、`created_at`、各类关联 ID），只列出各自特殊语义：

| 表名 | 核心语义 | 特殊字段 |
|------|---------|---------|
| `telemetry_events` | 结构化埋点事件，用于漏斗与质量分析 | `event_name`、`component`、`component_version`、`status`、`duration_ms`、`attributes_json`（已脱敏） |
| `llm_call_log` | 单次模型调用元数据，不存 prompt/response 明文 | `provider`、`model_name`、`prompt_version`、`request_hash`、`response_hash`、`input_token_count`、`output_token_count`、`latency_ms`、`status`、`json_parse_success`、`schema_validation_success` |
| `review_quality_feedback` | 关联 agent-review 输出与审批决策，用于评估模型与规则效果 | `routing_recommendation`、`review_status`、`pii_count_by_type`、`pii_count_by_severity`、`visibility_conflict`、`approval_decision`、`auto_approved`、`manual_override`、`approved_after_review_failure` |
| `llm_cost_daily` | 按天聚合成本与稳定性，可由 `llm_call_log` 离线生成 | `date`、`call_count`、`input_tokens`、`output_tokens`、`estimated_cost`、`avg_latency_ms`、`p95_latency_ms`；联合主键为 `date + provider + model_name + prompt_version + collection_id + visibility` |

## 5. 事件与契约

### 5.1 事件投递原则

所有跨服务事件必须通过 outbox pattern：

1. 服务在本地数据库事务中写业务状态
2. 同事务写 `outbox_events`
3. dispatcher 异步发送事件
4. 消费方用 `event_id` 去重
5. 处理结果落本地表，再由本地状态机推进

不得在业务事务提交前直接调用远端服务推进状态。

例外：ingestion-worker 处理 conversion 阶段 `StageCompleted` 时，需要先把 enriched 事件同步 POST 到 workbench，成功后再在同一事务中记录幂等并提交；失败则回滚，由 outbox poller 重试。

### 5.2 outbox_events

| 字段 | 类型 | 约束 |
|------|------|------|
| `event_id` | string | PK |
| `event_type` | string | not null |
| `aggregate_type` | string | not null |
| `aggregate_id` | string | not null |
| `schema_version` | string | not null |
| `payload_json` | jsonb | not null |
| `payload_hash` | string | not null |
| `idempotency_key` | string | nullable |
| `trace_id` | string | not null |
| `status` | enum | pending / sent / failed |
| `attempt_count` | int | default 0 |
| `next_attempt_at` | timestamp | not null |
| `created_at` | timestamp | not null |
| `sent_at` | timestamp | nullable |

### 5.3 标准事件头

所有事件 payload 必须包含：

```json
{
  "event_id": "evt_01J...",
  "event_type": "FileReady",
  "schema_version": "2026-05-21.v1",
  "producer": "document-service",
  "trace_id": "trc_01J...",
  "occurred_at": "2026-05-21T08:00:00Z",
  "idempotency_key": "...",
  "payload": {}
}
```

### 5.4 核心事件

#### `FileReady`

producer：document-service

consumer：intake-orchestrator

```json
{
  "source_file_id": "src_01J...",
  "object_id": "obj_sha256_abcd",
  "content_hash": "abcd...",
  "collection_id": "finance",
  "visibility": "INTERNAL",
  "original_name": "Q1财务报告.pdf",
  "size_bytes": 1048576
}
```

消费规则：

- 若 `(source_file_id)` 已有 active intake job，忽略重复事件
- 若 source_file_state 不为 READY，拒绝创建 job
- 创建 intake job 后调用 document-service claim，将 source file 标记为 CLAIMED

#### `StageTaskRequested`

producer：intake-orchestrator

consumer：conversion-worker / agent-review-worker / publishing-worker

```json
{
  "intake_job_id": "job_01J...",
  "stage_task_id": "task_01J...",
  "stage_name": "conversion",
  "schema_version": "2026-05-21.v1",
  "input_hash": "sha256...",
  "idempotency_key": "job_01J:conversion:2026-05-21.v1:sha256..."
}
```

消费规则：

- `StageTaskRequested` 只是 worker 的 wake-up 信号，不授予执行权。
- worker 收到事件后必须先按 `stage_task_id` 领取 DB lease。
- 只有 lease 成功的 worker 可以执行阶段任务并创建 `stage_attempt_id`。
- lease 失败必须视为重复投递或其他 worker 已领取，不得执行阶段逻辑。

#### `StageCompleted`

producer：worker

consumer：intake-orchestrator

```json
{
  "intake_job_id": "job_01J...",
  "stage_task_id": "task_01J...",
  "stage_name": "conversion",
  "idempotency_key": "...",
  "result_hash": "sha256...",
  "result_ref": "s3://...",
  "summary": {}
}
```

#### `ApprovalRequested`

producer：intake-orchestrator

consumer：approval-service

```json
{
  "intake_job_id": "job_01J...",
  "source_file_id": "src_01J...",
  "parse_snapshot_id": "pss_01J...",
  "preliminary_doc_id": "pre_q1_report_...",
  "collection_id": "finance",
  "visibility": "INTERNAL",
  "source_binary_ref": "s3://source/finance/Q1-report.pdf",
  "preview_text_ref": "s3://parse-snapshots/pss_01J/preview.txt",
  "chunk_preview_ref": "s3://parse-snapshots/pss_01J/chunk-preview.json",
  "quality_report": {},
  "similarity_hints": [],
  "version_conflict": null,
  "pii_report": {},
  "visibility_check": {},
  "routing_recommendation": "auto_approve"
}
```

#### `ApprovalPending`

producer：approval-service

consumer：intake-orchestrator

```json
{
  "intake_job_id": "job_01J...",
  "ticket_id": "apv_01J...",
  "approval_round": 1,
  "state": "PENDING",
  "created_at": "2026-05-21T08:00:00Z",
  "expires_at": "2026-05-28T08:00:00Z"
}
```

orchestrator 收到 `ApprovalPending` 后将 job state 从 `APPROVAL_REQUESTED` 推进到 `AWAITING_APPROVAL`。

#### `ApprovalDecided`

producer：approval-service

consumer：intake-orchestrator

```json
{
  "intake_job_id": "job_01J...",
  "ticket_id": "apv_01J...",
  "decision": "approve",
  "decision_actor": "system",
  "auto_approved": true,
  "final_doc_id": "doc_q1_report_v1",
  "confirmed_tags": ["financial_report"],
  "version_decision": null,
  "supersedes_final_doc_id": null,
  "archive_superseded": false,
  "return_target_stage": null,
  "reason": "满足自动入库策略"
}
```

#### `PublishRequested`

producer：intake-orchestrator

consumer：publishing-worker

```json
{
  "intake_job_id": "job_01J...",
  "publish_id": "pub_01J...",
  "final_doc_id": "doc_q1_report_v1",
  "source_file_id": "src_01J...",
  "parse_snapshot_id": "pss_01J...",
  "collection_id": "finance",
  "visibility": "INTERNAL",
  "confirmed_tags": ["financial_report"],
  "source_binary_ref": "s3://source/finance/Q1-report.pdf",
  "governance_overlay_ref": "s3://publishing/pub_01J/governance-overlay.json",
  "canonical_asset_ref": "s3://published/finance/doc_q1_report_v1/canonical.md",
  "sanitized_asset_ref": "s3://published/finance/doc_q1_report_v1/sanitized.md",
  "canonical_metadata": {},
  "index_version": "v1"
}
```

#### `IndexBuildRequested`

producer：publishing-worker

consumer：indexing-service

```json
{
  "publish_id": "pub_01J...",
  "reindex_job_id": null,
  "final_doc_id": "doc_q1_report_v1",
  "collection_id": "finance",
  "visibility": "INTERNAL",
  "source_binary_ref": "s3://source/finance/Q1-report.pdf",
  "parse_snapshot_id": "pss_01J...",
  "governance_overlay_ref": "s3://publishing/pub_01J/governance-overlay.json",
  "target_index_version": "v1",
  "canonical_asset_ref": "s3://published/finance/doc_q1_report_v1/canonical.md",
  "sanitized_asset_ref": "s3://published/finance/doc_q1_report_v1/sanitized.md",
  "metadata_ref": "s3://...",
  "index_profile_id": "default-v1",
  "idempotency_key": "doc_q1_report_v1:v1:pub_01J"
}
```

消费规则：

- `publish_id` 与 `reindex_job_id` 必须二选一。
- indexing-service 按 `idempotency_key` 幂等创建或复用 `index_build_job`。
- 同一 `final_doc_id + target_index_version` 同一时间只能有一个 active index build。
- `parse_snapshot_id` 是正式索引构建的主输入之一。
- `canonical_asset_ref` / `sanitized_asset_ref` 在过渡期可作为兼容输入，但不得继续代表 parser owner。
- 成功后发送 `IndexReady`，表示 document index revision 已准备好；失败写入 `index_build_jobs.error_code` 并等待 publishing-worker 或 reindex job 的重试策略处理。

#### `PublishCompleted`

producer：publishing-worker

consumer：intake-orchestrator

```json
{
  "intake_job_id": "job_01J...",
  "publish_id": "pub_01J...",
  "final_doc_id": "doc_q1_report_v1",
  "asset_state": "succeeded",
  "persist_state": "succeeded",
  "index_state": "succeeded",
  "index_version": "v1",
  "searchable": true
}
```

`PublishCompleted` 只能在 asset、document persist、index activate 全部成功后发送。若索引由 indexing-service 异步执行，publishing-worker 必须等待 `IndexReady` 或等价确认后，才能发送 `PublishCompleted`。索引未完成时只能保持 `publish_state = INDEXING` 或 `PUBLISH_RETRY_SCHEDULED`。

当 indexing-service 独立部署时，`IndexReady` 的主消费者是 publishing-worker 和 retrieval-service；intake-orchestrator 只接受 publishing-worker 的 `PublishCompleted` 推进 job 到 `PUBLISHED`，不得直接用 `IndexReady` 推进全局 job 状态。

原子可见性规则：

- `IndexReady` 表示 candidate document index revision 已由 indexing owner 构建完成，不表示文档已发布完成。
- `PublishCompleted` 表示 publishing domain 已把 `published_documents`、`active_index_version`、lifecycle audit、outbox 状态提交完成。
- 检索可见性的最终门槛是 `published_documents.published_document_state = PUBLISHED` 且 `active_index_version` 指向已激活索引。
- `PublishCompleted` 与 `DocumentLifecycleChanged` 必须在同一个 publishing outbox 事务之后投递，避免检索侧读到半提交状态。

#### `IndexReady`

producer：indexing-service。仅当 indexing-service 与 publishing-worker 同进程部署时，允许由 publishing-worker 以 indexing-service 契约代发

consumer：publishing-worker / retrieval-service

```json
{
  "publish_id": "pub_01J...",
  "reindex_job_id": null,
  "final_doc_id": "doc_q1_report_v1",
  "collection_id": "finance",
  "visibility": "INTERNAL",
  "index_version": "v1",
  "chunk_count": 128,
  "embedding_model": "bge-m3",
  "embedding_model_version": "2026-05-21",
  "searchable_at": "2026-05-21T08:00:00Z"
}
```

#### `DocumentLifecycleChanged`

producer：publishing domain（由 `services/admin` 的管理命令或新版本发布流程触发）

consumer：retrieval-service / indexing-service / audit pipeline

```json
{
  "final_doc_id": "doc_q1_report_v1",
  "collection_id": "finance",
  "from_state": "PUBLISHED",
  "to_state": "RETRACTED",
  "reason_code": "PII_MISSED",
  "actor_id": "user_123",
  "effective_at": "2026-05-21T08:00:00Z"
}
```

### 5.5 契约总结

| 契约 | 方向 | 语义 |
|------|------|------|
| `FileReady` | document-service -> orchestrator | source file 可创建 intake job |
| `StageTaskRequested` | orchestrator -> worker | 唤醒 worker 领取阶段任务 |
| `StageCompleted` | worker -> orchestrator | 阶段结果已持久化 |
| `ParsePreviewRequested` | intake-pipeline -> indexing-service | 请求生成 ParseSnapshot 预解析结果 |
| `ParseSnapshotReady` | indexing-service -> intake-pipeline/workbench-api | 预解析快照已可用于治理预览与调试 |
| `ApprovalRequested` | orchestrator -> approval-service | 请求治理决策 |
| `ApprovalPending` | approval-service -> orchestrator | 已创建人工 PENDING 工单 |
| `ApprovalDecided` | approval-service -> orchestrator | 已产生 approve/reject/return |
| `PublishRequested` | orchestrator -> publishing-worker | 请求发布最终文档 |
| `IndexBuildRequested` | publishing-worker -> indexing-service | 请求构建或重建索引 |
| `PublishCompleted` | publishing-worker -> orchestrator | 发布完成 |
| `IndexReady` | indexing-service -> publishing-worker/retrieval-service | 文档索引已可检索 |
| `DocumentLifecycleChanged` | publishing domain -> retrieval/indexing/audit | 已发布文档生命周期变化 |

## 6. 端到端流程

### 6.1 正常自动入库路径

分三阶段：

**阶段一：文件接收与任务创建**
用户上传文件到 document-service（必须指定 `collection_ids` 和 `visibility`），经 SHA-256 校验、恶意扫描后 source file 进入 READY；document-service 通过 outbox 发送 `FileReady`，intake-orchestrator 幂等创建 `intake_job` 并 claim source file 为 CLAIMED。

**阶段二：转换、审核与自动审批**
orchestrator 依次创建 conversion 与 review stage task。conversion-worker 完成转换、清洗、质量与相似度分析后提交 `StageCompleted`；orchestrator 校验通过即将 source file 标记为 CONSUMED，并推进到 review stage。agent-review-worker 执行 DLP 与 LLM 风险审核后提交结果；orchestrator 生成 `ApprovalRequested`，approval-service 判定满足 auto approve，创建 `approval_ticket`（SYSTEM_DECIDED），生成 `final_doc_id`、规则标签与审计日志，发送 `ApprovalDecided`。

**阶段三：发布与清理**
orchestrator 创建 publish task；publishing-worker 写 asset、persist document，请求 indexing-service 构建索引，完成后发送 `PublishCompleted`；orchestrator 将 job 标记为 PUBLISHED，并通知 document-service 将 source file 置为 CLEANABLE，由 document-service GC 判断 object_ref 是否可删。

### 6.2 人工审批路径

触发条件：visibility = EXTERNAL、high/critical PII、visibility conflict、质量 C/D、版本冲突、review degraded/failed 或 collection policy 要求人工审批。

流程：

approval-service 收到 `ApprovalRequested` 后判定不满足 auto approve，创建 `approval_ticket`（PENDING）并发送 `ApprovalPending`；orchestrator 将 job state 置为 AWAITING_APPROVAL。审批人操作 approve/reject/return 后，approval-service 追加审计日志并发送 `ApprovalDecided`；orchestrator 据此推进：approve → publish，reject → REJECTED，return → 指定 stage queued。

### 6.3 打回路径

审批人只能打回到明确阶段：

| 打回目标 | 使用场景 | 重新执行内容 |
|----------|----------|--------------|
| `conversion` | 转换乱码、表格错乱、内容缺失 | conversion + review + approval |
| `agent_review` | 脱敏不正确、风险漏判 | review + approval |

约束：

- 打回必须保留原 ticket 的历史审计，不得覆盖旧 `ticket_id`。
- 重新执行必须产生新的 `stage_task_id`，并通过 `rerun_round`、`return_reason_code` 等输入字段形成新的 `input_hash`。
- 打回后旧审批决策不再有效。
- 打回后如果再次进入 approval，必须创建新的 `ticket_id` 和递增的 `approval_round`，审批界面应展示历史打回记录。

### 6.4 拒绝路径

拒绝后：

- intake job state = REJECTED
- 不生成 publish task
- 不写最终 document
- 不写 index
- orchestrator 必须通知 document-service 将 source file 标记为 CLEANABLE；若通知失败，由补偿任务重试
- 审计日志必须保留拒绝原因
- 若用户修正后重新上传相同 bytes，不复用旧 `source_file_id`；旧记录进入 non-active 后，新上传创建新的 `source_file_id` 和 `intake_job_id`，并共享或复用同一 `object_id`

## 7. document-service 设计

### 7.1 输入

| 来源 | 行为 |
|------|------|
| Web Admin | `POST /upload` multipart，必须显式选择 visibility |
| CLI | `rag-cli push <path> --collection <id> --visibility <internal|external>` |
| Feishu / 企业微信 | 自动同步，强制 INTERNAL |
| Webhook | 第三方推送，默认按接入配置决定，EXTERNAL 必须显式允许 |

### 7.2 visibility 规则

| 场景 | 行为 |
|------|------|
| 手工上传 | 必须显式选择 INTERNAL 或 EXTERNAL |
| 自动同步 | 强制 INTERNAL |
| 缺失 visibility | 拒绝上传 |
| INTERNAL 改 EXTERNAL | 不允许，必须重新上传并重新审核 |
| EXTERNAL 改 INTERNAL | 不允许，必须新建文档关系 |

### 7.3 对象写入

对象写入步骤：

1. 接收 bytes 到 `_tmp/{upload_id}`
2. 计算服务端 SHA-256
3. 对比客户端 `X-Content-SHA256`
4. hash 不匹配，删除临时对象，upload failed
5. hash 匹配，检查 `object_blobs.content_hash`
6. 已存在，复用 object_id，增加 ref
7. 不存在，将临时对象提升到稳定 key
8. 创建 source_file
9. 提交扫描任务

稳定 key：

```
s3://bucket/objects/{sha256[0:2]}/{sha256}
```

不得把原始文件名放入稳定 key。原始文件名只存 metadata，避免路径注入和重命名导致对象 key 不稳定。

### 7.4 分片上传

分片约束：

- 默认分片大小 10MB
- 普通上传上限 100MB
- 分片上传硬上限 2GB
- 每片必须带 chunk hash
- 最终合并后必须校验整体 hash

孤儿分片清理：

- `last_chunk_at < now - 1h` 且未 completed -> expired
- expired session 的 `_tmp/{upload_id}` 对象进入 GC
- 清理动作必须记录 audit

### 7.5 安全扫描

扫描策略：

- 上传成功后异步扫描
- 扫描未完成不得发 `FileReady`
- 扫描失败 state = FAILED
- infected 文件立即进入隔离或清理策略
- 扫描结果保留至少 90 天

### 7.6 原子 claim

orchestrator 创建 job 前必须 claim source file。

API：

```http
POST /internal/source-files/{source_file_id}/claim
X-Service-Token: ...

{
  "intake_job_id": "job_01J...",
  "expected_state": "READY"
}
```

语义：

```sql
UPDATE source_files
SET state = 'CLAIMED',
    claimed_by_job_id = :job_id,
    updated_at = now()
WHERE source_file_id = :source_file_id
  AND state = 'READY'
  AND claimed_by_job_id IS NULL;
```

受影响行数为 1 表示成功。受影响行数为 0 表示已被领取或状态不合法。

claim 恢复规则：

- claim 成功但 job 创建事务失败：orchestrator 必须在恢复任务中按 `claimed_by_job_id` 查找孤儿 claim，并释放回 READY 或标记 FAILED。
- job 已创建但 `FileReady` 重复投递：orchestrator 返回已有 job，不重复 claim。
- source file 已 CLAIMED 但 job 不存在超过 10 分钟：document-service 发 `SourceFileClaimOrphaned` 告警事件。
- source file 已 CLAIMED 且 job 为终态：document-service 可通过只读查询 job 状态执行补偿性状态更新，所有更新必须使用条件更新，避免覆盖 orchestrator 主路径。

### 7.7 source file 状态命令

orchestrator 是 source file 消费状态的主路径通知方。document-service 负责校验状态迁移是否合法。

#### 标记 consumed

```http
POST /internal/source-files/{source_file_id}/mark-consumed
X-Service-Token: ...

{
  "intake_job_id": "job_01J...",
  "conversion_result_id": "conv_01J..."
}
```

语义：

```sql
UPDATE source_files
SET state = 'CONSUMED',
    updated_at = now()
WHERE source_file_id = :source_file_id
  AND state = 'CLAIMED'
  AND claimed_by_job_id = :job_id;
```

#### 标记 cleanable

```http
POST /internal/source-files/{source_file_id}/mark-cleanable
X-Service-Token: ...

{
  "intake_job_id": "job_01J...",
  "reason": "job_terminal"
}
```

语义：

```sql
UPDATE source_files
SET state = 'CLEANABLE',
    updated_at = now()
WHERE source_file_id = :source_file_id
  AND state IN ('CLAIMED', 'CONSUMED')
  AND claimed_by_job_id = :job_id;
```

重复调用必须幂等。若当前状态已经是目标状态，返回成功；若当前状态不允许迁移，返回 409。

## 8. intake-orchestrator 设计

`intake-orchestrator` 是唯一拥有 `intake_job_state` 的组件。其他组件只能做两件事：接收 orchestrator 派发的任务、提交阶段结果或治理决策。其他组件不得直接推进全局摄入状态，不得自行决定全链路下一步。

### 8.1 职责

orchestrator 负责：

- 消费 `FileReady`
- 创建 intake job
- claim source file
- 创建 stage task
- 接收 stage result
- 校验 result schema 和 hash
- 推进 intake job state
- 处理 retry、timeout、dead letter
- 请求 approval
- 请求 publishing
- 维护全链路审计索引

以下职责**不属于** orchestrator：

- 文件 bytes 存储
- 实际转换
- LLM 调用
- 人工审批 UI
- 写最终索引

### 8.2 状态推进规则

所有状态推进必须满足：

- 当前状态符合 expected state
- `state_version` 匹配
- 目标状态是合法迁移
- 必要 stage result 已存在
- 事件写入 outbox 与状态更新同事务

伪代码：

```sql
UPDATE intake_jobs
SET state = :next_state,
    state_version = state_version + 1,
    updated_at = now()
WHERE intake_job_id = :job_id
  AND state = :expected_state
  AND state_version = :expected_version;
```

### 8.3 retry 策略

| 阶段/子阶段 | 对应状态 | 可重试 | 默认策略 | 最大次数 |
|------------|----------|--------|----------|----------|
| conversion | `CONVERSION_*` | 是 | exponential backoff, 1m/5m/15m | 3 |
| agent_review | `REVIEW_*` | 是 | 30s/2m/10m，限流时延长 | 5 |
| publishing asset | `ASSET_WRITING` | 是 | 1m/5m/15m | 5 |
| publishing persist | `PERSISTING` | 是 | 1m/5m/15m | 5 |
| publishing index | `INDEXING` | 是 | 1m/5m/15m/1h | 10 |

approval submit 不是 worker stage。orchestrator 通过 outbox 发送 `ApprovalRequested`，由 approval-service 返回 `ApprovalPending` 或 `ApprovalDecided`。该发送动作的重试由 outbox dispatcher 负责。

不可重试错误：

- unsupported file type
- hash mismatch
- malware infected
- schema incompatible
- collection not found
- visibility invalid

### 8.4 超时策略

| 阶段 | timeout | 行为 |
|------|---------|------|
| conversion running | 30 min | lease 过期，重新入队 |
| agent_review running | 10 min | 重试或 degraded |
| approval pending | 3 days warning, 7 days expire | 通知审批人，超期 EXPIRED |
| publishing running | 30 min | 按子阶段重试 |

### 8.5 dead letter

超过最大重试次数的任务进入 dead letter：

- `stage_tasks.state = failed`
- `intake_jobs.state = FAILED`
- 记录 `failure_code`
- 记录最后一次错误摘要
- 发告警事件 `IntakeJobFailed`

运维可以执行：

- retry from failed stage
- cancel job
- mark as rejected

## 9. conversion-worker 设计

### 9.1 输入

conversion task 输入：

```json
{
  "intake_job_id": "job_01J...",
  "source_file_id": "src_01J...",
  "object_id": "obj_sha256...",
  "collection_id": "finance",
  "visibility": "INTERNAL",
  "original_name": "Q1财务报告.pdf",
  "content_hash": "sha256...",
  "schema_version": "2026-05-21.v1"
}
```

### 9.2 阶段

```
SourceRead
  -> ConversionStage
  -> CleaningStage
  -> QualityStage
  -> SimilarityCheck
  -> VersionCheck
  -> ConversionResultPersist
```

### 9.3 转换输出

```json
{
  "preliminary_doc_id": "pre_q1_report_01J...",
  "logical_document_id": "q1_report",
  "canonical_hash": "sha256...",
  "canonical_md_ref": "s3://...",
  "quality_report": {
    "grade": "A",
    "completeness": 0.97,
    "density": 0.88,
    "structure": 0.91,
    "noise": 0.04,
    "blocking_reasons": []
  },
  "similarity_hints": [
    {
      "final_doc_id": "doc_q1_report_v2",
      "score": 0.94,
      "reason": "minhash_lsh"
    }
  ],
  "version_conflict": null
}
```

### 9.4 相似度

相似度检测：

- 清洗后 canonical_md 提取 shingles
- MinHash 128 permutations
- LSH 16 bands x 8 rows
- 候选集内做完整 Jaccard 验证
- `score >= 0.90` 标记 highly similar
- `0.70 <= score < 0.90` 标记 related

相似度只提供提示，不自动拒绝，不自动合并。

### 9.5 版本线索

`logical_document_id` 初始来自文件名 stem slug。

同 `(collection_id, logical_document_id)` 已存在已发布文档时，输出 `version_conflict`。

conversion-worker 不决定：

- 新版本
- 独立文档
- 重复上传

这些只能由 approval-service 决策。

### 9.6 source preview 运行期约束

- PDF 页数统计限制文件大小并加解析超时，超限或超时返回 `None`，不阻塞后续流程
- manifest 写临时文件后通过原子 `os.replace` 落盘，避免并发写损坏
- 生产环境必须设置环境变量 `REALITY_RAG_INTAKE_RUNTIME_DIR`；未设置时启动即抛错

## 10. agent-review-worker 设计

### 10.1 输入

```json
{
  "intake_job_id": "job_01J...",
  "preliminary_doc_id": "pre_q1_report_01J...",
  "canonical_hash": "sha256...",
  "canonical_md_ref": "s3://...",
  "visibility": "INTERNAL",
  "quality_report": {},
  "schema_version": "2026-05-21.v1"
}
```

### 10.2 PII 策略

PII 检测分层：

| 层级 | 机制 | 负责内容 |
|------|------|----------|
| L1 | regex/rule | 手机号、身份证、邮箱、银行卡、IP、URL、内部域名 |
| L2 | NER | 姓名、地址、组织、职位 |
| L3 | LLM | 薪酬、医疗、人员名单、未公开项目、上下文敏感风险 |

结构化 PII 必须优先使用规则和 NER，LLM 只做补充。

### 10.3 sanitization_spans

脱敏结果必须使用 span：

```json
{
  "start": 128,
  "end": 139,
  "original": "13800138000",
  "replacement": "[手机号]",
  "type": "phone",
  "severity": "medium",
  "detector": "regex",
  "confidence": 1.0,
  "reason": "matched_cn_mobile"
}
```

规则：

- `start/end` 基于 canonical_md 的 Unicode code point offset
- span 不允许重叠，重叠时保留 severity 更高者
- 本地按 start 倒序替换，生成 sanitized_md
- LLM 不输出 sanitized_md 全文
- 审批 UI 基于 spans 做高亮对比

### 10.4 visibility_check

EXTERNAL 文档额外检查：

- 内部邮箱域
- 内部系统 URL
- 未公开产品代号
- 组织架构或员工名单
- 客户合同或报价
- 源代码片段和密钥形态

任一高风险命中时：

```json
{
  "conflict": true,
  "severity": "high",
  "items": [
    {
      "type": "internal_domain",
      "span": {"start": 20, "end": 38},
      "reason": "external document contains internal admin URL"
    }
  ]
}
```

### 10.5 LLM 供应商策略

agent-review-worker 必须支持：

- 规则模式：不调用外部 LLM
- 私有模型模式：调用企业内模型服务
- 外部模型模式：调用配置的外部供应商

每个 collection 可配置允许的 review mode；未配置时按全局默认 review mode 执行。

### 10.6 routing recommendation

agent-review-worker 输出的是建议，不是最终决策：

| 条件 | recommendation |
|------|----------------|
| INTERNAL + 质量 A/B + 无 high/critical PII + 无 visibility conflict + review succeeded | auto_approve |
| EXTERNAL | require_approval |
| high/critical PII | require_approval |
| visibility conflict | require_approval |
| 质量 C/D | require_approval |
| review degraded/failed | require_approval |

## 11. approval-service 设计

`auto_approve` 是 approval-service 产生的 system decision。自动入库不生成 PENDING 人工工单，但必须生成：`final_doc_id`、`confirmed_tags`、`approval_decision`、`approval_audit_log`、`PublishRequested` 事件。

approval-service 不写资产、不写索引、不直接持久化最终文档。approval-service 只产生 `ApprovalDecided`。实际发布由 publishing-worker 执行。

### 11.1 ApprovalPolicy

每个 collection 有审批策略：

```json
{
  "collection_id": "finance",
  "default_mode": "auto",
  "external_requires_manual": true,
  "high_pii_requires_manual": true,
  "version_conflict_requires_manual": true,
  "quality_min_auto_grade": "B",
  "auto_tags": ["financial_report"],
  "approvers": ["user_1", "user_2"]
}
```

### 11.2 system auto approve

必须全部满足：

- `routing_recommendation = auto_approve`
- collection policy 允许 auto
- visibility = INTERNAL
- 无 version_conflict
- quality grade >= policy threshold
- review_status = succeeded
- 无 high/critical PII

system auto approve 输出：

```json
{
  "decision": "approve",
  "decision_actor": "system",
  "auto_approved": true,
  "final_doc_id": "doc_q1_report_v1",
  "confirmed_tags": ["financial_report"],
  "reason": "满足自动入库策略"
}
```

### 11.3 人工审批

审批界面必须展示：

- 原始文件名、collection、visibility
- quality report
- PII span 对比
- visibility conflict
- similarity hints
- version_conflict
- 规则标签
- 人工标签编辑
- canonical/sanitized 切换
- 完整审计上下文

审批动作：

| 动作 | 必填字段 |
|------|----------|
| approve | confirmed_tags |
| reject | rejection_reason |
| return | return_target_stage, return_reason |

### 11.4 版本冲突与相似度审批

当 `version_conflict != null` 时，approval-service 必须要求审批人选择 `version_decision`，否则不能 approve。

| version_decision | 含义 | approve 后行为 |
|------------------|------|----------------|
| `new_version` | 当前文档是同一 logical document 的新版本 | 生成 `doc_{logical_document_id}_v{N+1}`，并按策略 archive 旧版本 |
| `independent_document` | 同名但不是同一文档 | 生成 `doc_{logical_document_id}_{digest}_v1`，旧文档保持原状态 |
| `business_duplicate` | 审批人判断当前文档与已有文档业务上重复 | 不生成 final_doc_id，ticket state = REJECTED，job state = REJECTED |

审批请求必须携带：

```json
{
  "version_conflict": {
    "logical_document_id": "contract",
    "existing_final_doc_id": "doc_contract_v1",
    "existing_state": "PUBLISHED",
    "existing_published_at": "2026-01-01T00:00:00Z"
  },
  "similarity_hints": [
    {
      "final_doc_id": "doc_q1_report_v2",
      "score": 0.94,
      "relation": "highly_similar"
    }
  ]
}
```

相似度 hints 的 UI 要求：

- 展示 Top N 相似文档，默认 N = 3
- 支持当前 sanitized_md 与历史文档 canonical/sanitized 的并排 diff
- 支持审批人将 similarity hint 标记为 `related` 或 `not_related`
- 不支持自动 merge
- 不支持因相似度单独自动 reject
- 若审批人选择 `business_duplicate`，必须填写或选择重复目标文档

`ApprovalDecided` 在 approve 且存在版本冲突时必须包含：

```json
{
  "version_decision": "new_version",
  "supersedes_final_doc_id": "doc_contract_v1",
  "archive_superseded": true
}
```

### 11.5 final_doc_id

生成规则：

| 场景 | final_doc_id |
|------|--------------|
| 全新文档 | `doc_{logical_document_id}_v1` |
| 新版本 | `doc_{logical_document_id}_v{N+1}` |
| 同名独立文档 | `doc_{logical_document_id}_{digest}_v1` |

约束：

- final_doc_id 由 approval-service 唯一生成
- publishing-worker 不得生成或修改 final_doc_id
- 同一 logical document 新版本发布成功后，旧版本是否 archive 由审批决策携带

### 11.6 决策幂等性

`decision` 接口的幂等键按 `ticket_id` 作用域隔离。同一 `idempotency_key` 只能复用同一 ticket 的决策结果，跨 ticket 不共享缓存。

## 12. publishing-worker 设计

### 12.1 输入

`PublishRequested`

### 12.2 发布步骤

```
AssetWrite
  -> PersistDocument
  -> RequestIndexBuild
  -> WaitIndexReady
  -> VerifyPublished
  -> PublishCompleted
```

### 12.3 AssetWrite

写入 deterministic paths：

```
collections/{collection_id}/docs/{final_doc_id}/canonical.md
collections/{collection_id}/docs/{final_doc_id}/sanitized.md
collections/{collection_id}/docs/{final_doc_id}/metadata.json
collections/{collection_id}/docs/{final_doc_id}/quality_report.json
collections/{collection_id}/docs/{final_doc_id}/review_report.json
```

重复写入必须覆盖相同内容或校验 hash 一致。

### 12.4 PersistDocument

写入发布事实源必须 upsert `published_documents` by `final_doc_id`：

- 若不存在，insert
- 若存在且 payload_hash 相同，视为成功
- 若存在但 payload_hash 不同，标记冲突，停止发布
- 如需兼容旧查询，可由 publishing domain 同步投影到 `documents` / `document_policies`，但投影不是生命周期事实源

### 12.5 RequestIndexBuild / WaitIndexReady

索引构建：

- publishing-worker 不直接执行 chunking、embedding、vector index upsert
- publishing-worker 发送 `IndexBuildRequested` 或调用等价内部 command API
- indexing-service 优先复用 `ParseSnapshot`，按 `final_doc_id + index_version` 幂等构建 candidate index
- indexing-service 成功后发送 `IndexReady`
- publishing-worker 收到匹配 `publish_id/reindex_job_id + final_doc_id + index_version` 的 `IndexReady` 后，才能进入 `VerifyPublished`
- 索引失败不得回滚 approval decision
- 索引失败进入 publish retry

### 12.6 indexing-service 边界

publishing-worker 负责编排发布，不直接承担所有索引细节。索引可由独立 `indexing-service` 执行。

| 职责 | publishing-worker | indexing-service |
|------|-------------------|------------------|
| 接收 PublishRequested | 是 | 否 |
| 写 published assets | 是 | 否 |
| 持久化 published_documents | 是 | 否 |
| 投影 documents/document_policies 兼容读模型 | 可选 | 否 |
| chunking | 否 | 是 |
| embedding | 否，除非同进程部署 | 是 |
| vector index upsert | 否，除非同进程部署 | 是 |
| index activate / rollback | 发起/记录 | 执行 |
| 发送 IndexReady | 可转发 | 是 |

chunking、embedding、vector index upsert 的 owner 是 indexing-service。即使同进程部署，也必须按 indexing-service 的契约和版本记录执行。

独立部署时的事件闭环：

1. publishing-worker 完成 asset write 和 document persist
2. publishing-worker 向 indexing-service 发送 `IndexBuildRequested`，携带 `publish_id`、`final_doc_id`、`source_binary_ref`、`parse_snapshot_id`、`governance_overlay_ref`、`index_version`
3. indexing-service 复用 `ParseSnapshot` 执行 final chunk materialization、embedding、vector index upsert、activate
4. indexing-service 通过自己的 outbox 发送 `IndexReady`
5. publishing-worker 消费 `IndexReady` 后将 `publish_state` 推进到 `INDEXED/PUBLISH_SUCCEEDED`
6. publishing-worker 发送 `PublishCompleted`

retrieval-service 可以消费 `IndexReady` 更新 active index discovery，但不得把仅收到 `IndexReady` 等同于 intake job 已完成；job 完成只以 `PublishCompleted` 为准。

### 12.7 indexing 边界

`intake-pipeline` 只定义发送给 `indexing` 的发布输出，不定义 chunk schema、embedding schema、OpenSearch/Qdrant 写入结构或 retrieval filter 内部契约。

由 `indexing` owner 文档定义：

- `NormalizedDocument`
- `ChunkRecord`
- chunking profile
- embedding profile
- index version registry
- OpenSearch/Qdrant record

`intake-pipeline` 对 indexing 的唯一稳定发布输出是 `IndexBuildRequested` 级别的契约：

- `tenant_id`
- `collection_id`
- `final_doc_id`
- `publish_version`
- `visibility`
- `confirmed_tags`
- `source_binary_ref`
- `parse_snapshot_id`
- `governance_overlay_ref`
- `source_content_hash`
- `index_profile_id`

字段映射规则：

- `canonical_asset_ref` / `sanitized_asset_ref` / `metadata_ref` 可以作为过渡兼容字段继续存在。
- 这些字段用于治理审计、人工复核或 fallback，不再代表正式 parser 输入。
- 正式索引主输入应收敛到 `source_binary_ref + parse_snapshot_id + governance_overlay_ref`。

### 12.8 index_version 语义

`index_version` 表示 collection 级检索索引结构和 embedding/chunking 契约版本，不等于文档版本。

`index_version` 由 indexing owner 管理。`intake-pipeline` 只保存当前文档生效的 `active_index_version` 引用，不生成 index version 内部结构。

单文档 publish/reindex 不激活新的 collection `index_version`，只请求 indexing 在当前 active collection `index_version` 下生成新的 `document_index_revision`。collection 级 rebuild、schema/profile/embedding/chunking 变更才创建并激活新的 `index_version`。

同一 `final_doc_id` 可以在同一 collection `index_version` 下存在多个历史 `document_index_revision`，但只能有一个 current revision。retrieval 只查询当前 active index_version 内未 tombstone 的 current revision。

### 12.9 activate / rollback

索引发布分两步：

1. 写入当前 active collection index version 下的 candidate document revision
2. 校验 chunk count、embedding count、metadata 完整性后将 document revision 标记为 READY

document revision ready 后发送 `IndexReady`。collection `index_version` activate/rollback 只能由 indexing owner 在 collection 级执行，不得由单文档 publish/reindex 触发。

### 12.10 retrieval 边界

`intake-pipeline` 不定义 retrieval 内部过滤实现。它只保证 published document 输出携带检索侧需要的事实：

- `tenant_id`
- `collection_id`
- `final_doc_id`
- `published_document_state`
- `visibility`
- `active_index_version`
- `confirmed_tags`

retrieval 如何组合权限、BM25、vector、fusion、rerank、context pack，由 `services/retrieval/retrieval.md` 和顶层架构文档定义。

不可检索状态：

- `ARCHIVED`
- `DEPRECATED`，除非调用方显式要求包含 deprecated
- `RETRACTED`

retract 或 unpublish 必须产生 tombstone 或 delete-by-final_doc_id 操作，确保旧 chunk 不再被检索。

## 13. 已发布文档生命周期

### 13.1 published_document_state

owner：publishing domain。`services/admin` 是对外管理入口，不直接拥有状态表；它通过 publishing domain 的受控命令变更 lifecycle state。

```
PUBLISHED
  ├── -> ARCHIVED
  ├── -> DEPRECATED
  ├── -> RETRACTED
  └── -> REINDEXING -> 原状态
```

| 状态 | 含义 | 是否默认可检索 |
|------|------|----------------|
| `PUBLISHED` | 当前有效文档 | 是 |
| `ARCHIVED` | 被新版本替代的历史版本 | 否 |
| `DEPRECATED` | 仍保留但不推荐使用 | 默认否，可显式包含 |
| `RETRACTED` | 因错误、合规、误审批撤回 | 否 |
| `REINDEXING` | 正在重建索引，旧索引是否可用由策略决定 | 视策略 |

`REINDEXING` 是临时状态，必须记录 `previous_published_document_state`。reindex 完成后恢复到原状态。默认只对 `PUBLISHED` 文档发起 reindex；如需对 `ARCHIVED` 或 `DEPRECATED` 文档 reindex，必须显式传入管理原因。

### 13.2 触发规则

| 操作 | 触发方 | 是否需要审批 | 索引行为 |
|------|--------|--------------|----------|
| 新版本发布 archive 旧版 | approval decision | 已在审批中确认 | 旧版 tombstone 或从 active index 移除 |
| 手动 deprecate | admin | 需要管理权限 | retrieval 默认过滤 |
| retract | admin / compliance | 需要强权限和原因 | 立即 tombstone |
| reindex | admin / indexing-service | 不需要内容审批 | 新 index_version activate 后切换 |

### 13.3 retract 语义

retract 用于已发布文档发现严重问题，例如漏检 PII、误审批、法律风险。

retract 必须：

- 追加 lifecycle audit
- 发送 `DocumentLifecycleChanged`
- 触发 index tombstone
- retrieval-service 在收到事件或下次同步后不再返回该文档
- 保留原始审计和资产，除非合规策略要求物理删除

### 13.4 新版本语义

当 approval-service 决策 `version_decision=new_version`：

- 新文档获得 `doc_{logical_document_id}_v{N+1}`
- 旧版本按策略进入 `ARCHIVED`
- retrieval-service 默认只返回最新 `PUBLISHED` 版本
- 历史版本可在 admin 或显式历史查询中访问

## 14. 外部 API 契约

本章定义对前端、CLI、Admin、运维工具暴露的 API。worker 不直接暴露管理 API。所有管理 API 由对应 service 或 `services/admin` 聚合层提供。

### 14.1 通用 API 规则

- 所有 API 返回必须包含 `request_id`
- 所有写操作必须支持 `Idempotency-Key`
- 所有错误必须返回标准 `error_code`
- 所有时间使用 UTC ISO-8601
- 分页统一使用 `limit + cursor`
- 外部 API 不暴露内部 `stage_task_id` 以外的敏感执行细节，除非 admin 权限

标准错误响应：

```json
{
  "request_id": "req_01J...",
  "error_code": "SOURCE_FILE_NOT_READY",
  "message": "source file is not ready",
  "retryable": false,
  "details": {}
}
```

### 14.2 document-service API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/uploads` | 创建上传 session，需 `Idempotency-Key` |
| PUT | `/uploads/{upload_id}/content` | 单文件上传 bytes，需 `X-Content-SHA256` |
| PUT | `/uploads/{upload_id}/chunks/{chunk_index}` | 分片上传，需 `X-Chunk-SHA256` |
| POST | `/uploads/{upload_id}/complete` | 完成上传，返回生成的 `source_files` |
| DELETE | `/uploads/{upload_id}` | 取消上传 session |
| GET | `/source-files/{source_file_id}` | 查询 source file 状态与元数据 |

示例：创建上传 session

```http
POST /uploads
Idempotency-Key: ...

{
  "original_name": "Q1财务报告.pdf",
  "size_bytes": 1048576,
  "sha256": "abcd...",
  "collection_ids": ["finance"],
  "visibility": "INTERNAL",
  "source": "web"
}
```

返回字段：`upload_id`、`mode`、`chunk_size`、`expires_at`。

示例：查询 source file

```http
GET /source-files/{source_file_id}
```

返回字段：`source_file_id`、`collection_id`、`visibility`、`state`、`claimed_by_job_id`、`content_hash`、`original_name`、`created_at`。

### 14.3 intake-orchestrator API

#### 查询 job

```http
GET /intake-jobs/{intake_job_id}
```

返回字段：`intake_job_id`、`source_file_id`、`collection_id`、`visibility`、`state`、`current_stage`、`preliminary_doc_id`、`final_doc_id`、`created_at`、`updated_at`。

#### 查询 job timeline

```http
GET /intake-jobs/{intake_job_id}/timeline
```

返回阶段事件、状态迁移、retry、approval、publish 摘要。不得返回正文或 PII 原值。

#### 从阶段重试

```http
POST /intake-jobs/{intake_job_id}/retry
Idempotency-Key: ...

{
  "from_stage": "agent_review",
  "reason": "LLM provider restored"
}
```

#### 取消 job

```http
POST /intake-jobs/{intake_job_id}/cancel
Idempotency-Key: ...

{
  "reason": "operator requested"
}
```

### 14.4 approval-service API

#### 待审列表

```http
GET /approval/tickets?state=PENDING&collection_id=finance&limit=50&cursor=...
```

返回字段：items（含 `ticket_id`、`intake_job_id`、`collection_id`、`visibility`、`quality_grade`、`has_version_conflict`、`pii_high_or_critical`、`created_at`）、`next_cursor`。

#### 审批详情

```http
GET /approval/tickets/{ticket_id}
```

返回审批所需的报告引用、PII span 摘要、相似度 hints、version_conflict、标签。正文通过受控 artifact URL 或后端代理按权限读取，不进入普通 API 列表响应。

#### 提交审批决策

```http
POST /approval/tickets/{ticket_id}/decision
Idempotency-Key: ...

{
  "decision": "approve",
  "confirmed_tags": ["financial_report"],
  "version_decision": "new_version",
  "business_duplicate_target_final_doc_id": null,
  "return_target_stage": null,
  "reason": "确认可入库"
}
```

约束：

- `decision=approve` 且存在 version_conflict 时，`version_decision` 必填
- `decision=reject` 时，`reason` 必填
- 审批人判定 `business_duplicate` 时，`business_duplicate_target_final_doc_id` 必填，最终按 reject 处理
- `decision=return` 时，`return_target_stage` 和 `reason` 必填

### 14.5 已发布文档管理 API

已发布文档的管理 API 不由 publishing-worker 暴露。由 `services/admin` 聚合层暴露。

`services/admin` 是命令入口，不直接写 `published_documents`。所有 lifecycle 写入必须进入 publishing domain：

1. `services/admin` 校验调用方权限、参数和 `Idempotency-Key`
2. 写入 lifecycle command 或调用 publishing domain 内部命令 API
3. publishing domain 条件更新 `published_documents`
4. publishing domain 追加 lifecycle audit
5. publishing domain 发送 `DocumentLifecycleChanged`

manual review 旁路退场规则：

- `services/admin` 的 `/admin/manual-review/*` 路径如果仍存在，只能标记为临时兼容路径。
- 该路径不得直接写 `published_documents`、`documents`、`document_policies`、`index_build_jobs` 或触发索引。
- 人工审核通过必须转为 approval-service decision 或 publishing domain command。
- 旁路兼容期内的任何直接写表行为都必须在文档和代码中标记为 deprecated，并进入退场清单。
- 新功能不得依赖 manual-review 旁路扩展发布或补索引能力。

#### 查询发布状态

```http
GET /documents/{final_doc_id}
```

#### 下架 / 撤回

```http
POST /documents/{final_doc_id}/retract
Idempotency-Key: ...

{
  "reason_code": "pii_missed",
  "reason": "发现漏检手机号"
}
```

#### 标记 deprecated

```http
POST /documents/{final_doc_id}/deprecate
Idempotency-Key: ...

{
  "reason": "被新制度替代"
}
```

#### 重新索引

```http
POST /documents/{final_doc_id}/reindex
Idempotency-Key: ...

{
  "reindex_job_id": "ridx_01J...",
  "target_index_version": "v2",
  "reason": "embedding model upgrade"
}
```

## 15. 安全与权限

### 15.1 服务间认证

所有 `/internal/*` 必须认证：

- mTLS 优先
- Service token 可作为补充
- token 必须支持轮换
- internal API 不暴露公网

#### 服务间只读 owner API（workbench 消费）

`workbench-api` 通过以下内部 API 查询 intake-pipeline 拥有的状态：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/internal/source-files` | 注册 source file（command 语义，带 idempotency） |
| GET | `/internal/source-files/{source_file_id}` | 查询 source file 只读视图 |
| GET | `/internal/intake-jobs/{intake_job_id}` | 查询 intake job 只读视图 |
| GET | `/internal/published-documents/{published_document_id}` | 查询已发布文档只读视图 |

这些 API 不暴露给公网，仅供平台内部服务消费。

### 15.2 最小权限

| 组件 | 对象存储权限 |
|------|--------------|
| document-service | read/write source objects |
| conversion-worker | read source, write conversion assets |
| agent-review-worker | read canonical, write review assets |
| approval-service | read reports, write approval audit |
| publishing-worker | read sanitized/canonical, write published assets |

### 15.3 审计保留

| 审计类型 | 保留 |
|----------|------|
| upload audit | 90 天默认，可配置 |
| malware scan result | 90 天默认，可配置 |
| stage result summary | 180 天默认，可配置 |
| approval audit | 不少于 1 年 |
| publish audit | 不少于 1 年 |

## 16. 基础设施边界

### 16.1 默认消息实现

默认实现：

- PostgreSQL `outbox_events`
- dispatcher polling
- consumer idempotency table
- stage task DB lease

可替换实现：

- Kafka
- RabbitMQ
- Redis Streams
- 云厂商队列

替换消息中间件不得改变事件契约、幂等键、consumer 去重语义。

### 16.2 stage task 领取

默认不使用 Redis/ZooKeeper 分布式锁。

stage task 领取使用数据库 lease：

```sql
UPDATE stage_tasks
SET state = 'running',
    locked_by = :worker_id,
    lock_expires_at = now() + interval '10 minutes',
    updated_at = now()
WHERE stage_task_id = :task_id
  AND state IN ('queued', 'retry_scheduled')
  AND next_run_at <= now()
  AND (locked_by IS NULL OR lock_expires_at < now());
```

worker 必须定期 heartbeat 延长 lease。lease 过期后 orchestrator 可重新入队。

### 16.3 数据库边界

默认部署允许同一个 PostgreSQL instance，但必须按 schema/table ownership 隔离：

| owner | schema 示例 |
|-------|-------------|
| document-service | `docsvc.*` |
| intake-orchestrator | `orchestrator.*` |
| conversion-worker | `conversion.*` |
| agent-review-worker | `review.*` |
| approval-service | `approval.*` |
| publishing-worker | `publishing.*` |
| indexing-service | `indexing.*` |
| telemetry | `telemetry.*` |

规则：

- 服务只能写自己 owner 的表
- 只允许通过 API/event 跨 owner 修改状态
- 允许只读报表视图，但不得让业务逻辑依赖跨 owner join
- 未来可按 schema 拆分为独立数据库
- 每个 owner 拥有自己的 outbox

### 16.4 背压与熔断

必须支持：

- outbox dispatcher 速率限制
- stage queue depth limit
- LLM provider rate limit
- indexing-service circuit breaker
- object storage retry budget
- per collection 并发上限

熔断时行为：

- LLM 不可用：review degraded，进入 require_approval，不阻塞所有 job
- approval-service 不可用：ApprovalRequested 留在 outbox/队列，job 保持 APPROVAL_REQUESTED
- indexing-service 不可写：publish 子阶段 retry，并启用熔断避免压垮索引
- document-service claim orphaned：自动释放或标记 failed，并告警

## 17. 横切关注点

### 17.1 重复上传语义

#### duplicate handling

当 `(content_hash, collection_id)` 命中已有记录时，按三类处理：

**仍在流程中（READY / CLAIMED / CONSUMED / PROCESSING / REVIEW / APPROVAL）**：返回已有的 `source_file_id` 和/或 `intake_job_id`，不创建新的 active source file。`published_document`（PUBLISHED 且 `source_content_hash` 相同）同理，返回已有 `final_doc_id`，不重复摄入。

**终态拒绝/取消（REJECTED / CANCELLED）**：必须创建新的 `source_file_id` 与 `intake_job_id`，保留旧审计。CANCELLED 不允许直接复用原 source_file 创建新 job；如需继续，由运维 retry 原 job 或用户重新上传。

**已清理/失败（CLEANED / FAILED）**：CLEANED 可创建新 source_file，复用或重写 object_id；FAILED 可 retry 原 job，也可重新上传创建新 source_file 并关联同一 `object_id`。

#### 多 collection 上传

多 collection 上传逐个判定：

- 已存在的 collection 返回已有状态
- 不存在的 collection 创建新的 `source_file_id`
- 同一物理 bytes 共享 `object_id`
- 任一 collection 的拒绝不影响其他 collection

#### duplicate response

命中 active source file、active job 或已发布文档时，重复上传响应必须包含：

```json
{
  "duplicate": true,
  "source_file_id": "src_01J...",
  "intake_job_id": "job_01J...",
  "final_doc_id": "doc_q1_report_v1",
  "state": "PUBLISHED",
  "action": "reuse_existing"
}
```

已发布文档的重复命中必须基于 `published_documents.source_content_hash` 或等价发布索引，不得只依赖仍处于 active 的 `source_file`。source file 进入 `CLEANABLE/CLEANED` 后，仍必须能通过发布记录判断相同内容是否已经入库。

### 17.2 配置管理

#### 配置 owner

| 配置 | owner |
|------|-------|
| ApprovalPolicy | approval-service |
| review mode | agent-review-worker / admin config |
| retry / timeout | intake-orchestrator |
| LLM provider priority | agent-review-worker |
| quality threshold | approval-service policy |
| chunking / embedding / index_version | indexing-service |

#### 配置要求

- 所有配置必须有 `config_version`
- 配置变更必须审计
- 支持热更新
- worker 执行时必须记录使用的 config_version
- 旧 job 按创建时或阶段开始时的 config_version 执行，不能被中途静默改变

#### collection 配置

collection 配置至少包含：

```json
{
  "collection_id": "finance",
  "approval_policy_id": "apol_finance_v3",
  "review_mode": "external_llm",
  "auto_tags": ["financial_report"],
  "approvers": ["user_1", "user_2"],
  "max_parallel_jobs": 10
}
```

### 17.3 错误码体系

错误码格式：

```
{DOMAIN}_{REASON}
```

`DOMAIN` 优先使用产生错误的组件名或业务域：

- `DOCUMENT`：上传、对象、hash、扫描
- `SOURCE_FILE`：source file 状态迁移
- `CONVERSION`
- `REVIEW`
- `APPROVAL`
- `PUBLISH`
- `INDEX`
- `CONFIG`

示例：

| error_code | retryable | HTTP |
|------------|-----------|------|
| `DOCUMENT_HASH_MISMATCH` | false | 400 |
| `DOCUMENT_TOO_LARGE` | false | 413 |
| `SOURCE_FILE_NOT_READY` | false | 409 |
| `SOURCE_FILE_ALREADY_CLAIMED` | false | 409 |
| `CONVERSION_UNSUPPORTED_TYPE` | false | 422 |
| `CONVERSION_TIMEOUT` | true | 504 |
| `REVIEW_PROVIDER_TIMEOUT` | true | 504 |
| `REVIEW_SCHEMA_INVALID` | true | 502 |
| `APPROVAL_TICKET_NOT_PENDING` | false | 409 |
| `PUBLISH_INDEX_UNAVAILABLE` | true | 503 |
| `CONFIG_VERSION_NOT_FOUND` | false | 500 |

所有 error_code 必须进入 telemetry。worker stage 的失败 error_code 写入 `stage_attempts`；成功 stage 的摘要写入 `stage_results.summary_json`。不得为了记录失败而创建成功语义的 `stage_results`。

### 17.4 容量与并发

#### worker 扩展

- conversion-worker 无状态，可水平扩展
- agent-review-worker 受 LLM rate limit 约束
- publishing-worker 受 indexing-service 和 embedding 资源约束
- orchestrator 通过 DB lease 保证多实例安全

#### 大文件策略

GB 级 PDF 或大文档：

- conversion 必须 streaming 读取
- 禁止一次性把完整 bytes 读入内存
- canonical_md 可分段写 artifact
- stage result 只存摘要和 artifact ref
- 超过转换时间上限进入 retry 或 failed

#### 背压

背压触发条件：

- stage queue depth 超阈值
- LLM provider rate limit
- indexing circuit open
- object storage error ratio 超阈值
- DB connection pool 饱和

背压行为：

- 暂停 FileReady 消费
- 延迟创建新 stage task
- 对低优先级 collection 限流
- 保持已审批 publish task 不丢失

### 17.5 测试策略

必须覆盖：

- 状态机合法迁移测试
- 非法状态迁移拒绝测试
- idempotency 重复执行测试
- outbox replay 测试
- stage lease 过期重领测试
- content duplicate 上传测试
- business duplicate 审批测试
- approval version_decision 测试
- publish partial failure 测试
- index activate/rollback 测试
- LLM schema invalid / timeout 降级测试
- telemetry 敏感字段禁入测试
- chaos test：worker crash、DB transient error、object storage timeout、LLM provider outage

## 18. 可观测性

### 18.1 分层目标

intake-pipeline 的埋点分三层：

| 层级 | 目标 | 存储/系统 | 示例 |
|------|------|-----------|------|
| Metrics | 实时监控、告警、SLA | Prometheus / OpenTelemetry metrics | 阶段耗时、失败率、backlog |
| Tracing | 单 job 排障、跨服务调用链 | OpenTelemetry trace | trace_id 串联 upload -> publish |
| Analytics Events | 流程优化、质量分析、成本分析 | `telemetry_events` / ClickHouse / warehouse | 漏斗、人工打回、LLM 成本 |

三层共享统一字段命名，但用途不同。Metrics 必须低基数，Analytics 可以高维但不得保存敏感明文。

### 18.2 必须透传字段

所有日志、metrics label、trace span、telemetry event 必须尽可能携带：

- `trace_id`
- `intake_job_id`
- `source_file_id`
- `collection_id`
- `visibility`
- `stage_name`
- `stage_task_id`，如适用
- `ticket_id`，如适用
- `review_id`，如适用
- `publish_id`，如适用
- `final_doc_id`，如适用
- `component`
- `component_version`
- `schema_version`

### 18.3 禁止进入普通埋点的数据

以下内容不得写入 metrics、trace attributes、`telemetry_events`、`llm_call_log`、`llm_cost_daily`：

- 原始文件 bytes
- `canonical_md` 明文
- `sanitized_md` 明文
- PII 原值
- 完整 prompt 明文
- 完整 LLM response 明文
- 完整 `sanitization_spans.original`
- 对象存储 presigned URL
- service token、API key、cookie、session id

如需保存 prompt、response、canonical、sanitized 等可复核内容，只能写入受权限控制的 artifact，并通过 hash 与 telemetry 关联。

### 18.4 TelemetryEvent 契约

所有结构化埋点使用统一契约：

```json
{
  "event_id": "tel_01J...",
  "event_name": "conversion_completed",
  "event_time": "2026-05-21T08:00:00Z",
  "schema_version": "2026-05-21.v1",
  "trace_id": "trc_01J...",
  "intake_job_id": "job_01J...",
  "source_file_id": "src_01J...",
  "collection_id": "finance",
  "visibility": "INTERNAL",
  "stage_name": "conversion",
  "stage_task_id": "task_01J...",
  "component": "conversion-worker",
  "component_version": "1.4.2",
  "status": "succeeded",
  "duration_ms": 3812,
  "error_code": null,
  "retry_count": 0,
  "attributes": {}
}
```

约束：

- `event_name` 必须来自固定枚举。
- `attributes` 只能放枚举、计数、hash、分桶值、版本号。
- `attributes` 不得放正文片段、PII 原值、prompt 明文。
- 发送失败不得阻塞主链路，但必须可重放或可从业务表补算。

### 18.5 阶段事件枚举

每个阶段必须产生 started、succeeded、failed/degraded 三类事件（如适用）：

- **upload**：`upload_started`、`upload_completed`、`upload_failed`
- **scan**：`scan_started`、`scan_completed`、`scan_failed`
- **conversion**：`conversion_started`、`conversion_completed`、`conversion_failed`
- **quality / similarity / version**：`quality_scored`、`similarity_checked`、`version_checked`
- **review**：`review_started`、`review_completed`、`review_degraded`、`review_failed`
- **approval**：`approval_requested`、`approval_pending`、`approval_decided`、`approval_returned`、`approval_expired`
- **publish**：`publish_started`、`publish_completed`、`publish_failed`，子阶段事件 `asset_written`、`document_persisted`、`index_upserted`
- **job 级**：`intake_job_completed`、`intake_job_failed`、`intake_job_cancelled`

### 18.6 阶段事件推荐 attributes

各事件推荐携带的 attributes 按阶段归类：

- **upload**：`file_size_bucket`、`source`、`chunked`、`content_hash_prefix`
- **scan**：`engine`、`engine_version`、`verdict`
- **conversion**：`file_type`、`converter_name`、`converter_version`、`canonical_size_bucket`
- **quality**：`quality_grade`、`completeness_bucket`、`density_bucket`、`structure_bucket`、`noise_bucket`
- **similarity**：`high_similarity_count`、`related_count`、`max_similarity_bucket`
- **version**：`has_version_conflict`
- **review**：`review_status`、`routing_recommendation`、`pii_count_total`、`visibility_conflict`
- **approval**：`decision`、`auto_approved`、`manual_override`、`return_target_stage`
- **publish**：`chunk_count_bucket`、`index_version`、`embedding_model_version`；子阶段 `asset_written` 额外带 `asset_count`、`asset_bytes_bucket`、`payload_hash`；`document_persisted` 额外带 `final_doc_id`、`published_document_state`；`index_upserted` 额外带 `index_latency_bucket`

### 18.7 LLM 调用埋点

每次外部或私有模型调用必须写 `llm_call_log`（字段见 4.9 节），并产生 trace span。

埋点用途：成本核算、供应商稳定性分析、prompt/model 版本质量对比、schema 解析失败排查、限流与超时告警。

### 18.8 Review 质量闭环

agent-review-worker 的输出必须与 approval-service 的最终决策关联，形成 `review_quality_feedback`（字段见 4.9 节）。

质量闭环必须能回答：哪个 `prompt_version` 的人工打回率最高；哪类 PII 误报最多；哪些 collection 的人工覆盖率最高；review degraded 后被人工 approve 的比例；EXTERNAL 文档 visibility conflict 的命中质量；quality grade 与人工拒绝/打回之间的关系。

### 18.9 LLM 成本聚合

`llm_cost_daily` 按天聚合：

- `provider`
- `model_name`
- `model_version`
- `prompt_version`
- `collection_id`
- `visibility`
- `call_count`
- `success_count`
- `failure_count`
- `input_tokens`
- `output_tokens`
- `estimated_cost`
- `avg_latency_ms`
- `p95_latency_ms`

成本聚合不得依赖外部账单才可用。外部账单用于校准单价和核对，不作为唯一成本来源。

### 18.10 Metrics

必须暴露的指标按四类分组：

- **job 生命周期**：`intake_jobs_created_total`、`intake_jobs_published_total`、`intake_jobs_failed_total`、`end_to_end_intake_duration_seconds`
- **stage 执行**：`stage_duration_seconds`、`stage_retry_total`、`stage_failed_total`、`outbox_pending_total`、`dead_letter_total`
- **审批决策**：`approval_pending_total`、`auto_approve_total`、`manual_decision_total`、`manual_approve_total`、`manual_reject_total`、`manual_return_total`、`manual_override_total`
- **LLM 与质量**：`llm_call_total`、`llm_token_total`、`llm_error_total`、`llm_schema_validation_failure_total`、`review_degraded_total`、`publish_failure_total`

ratio 类指标不直接作为主指标暴露。`auto_approve_ratio`、`manual_override_ratio`、`llm_error_ratio` 等比例必须由 counter 通过 Prometheus recording rule 或等价指标系统计算，避免不同实例重复计算导致口径不一致。

Metrics label 必须控制基数。允许 label：

- `component`
- `stage_name`
- `status`
- `visibility`
- `provider`
- `model_name`
- `prompt_version`

禁止把 `intake_job_id`、`source_file_id`、`final_doc_id` 作为 metrics label。

### 18.11 Tracing

每个 intake job 必须形成单条 trace。关键 span 按组件分组：

- **document-service**：`document.upload`、`document.scan`
- **orchestrator**：`orchestrator.create_job`、`orchestrator.schedule_stage`
- **conversion-worker**：`conversion.run`
- **agent-review-worker**：`agent_review.run`、`agent_review.llm_call`
- **approval-service**：`approval.decide`
- **publishing-worker**：`publishing.asset_write`、`publishing.persist_document`、`publishing.upsert_index`

trace attribute 不得包含敏感明文。单个 trace 至少可定位：卡在哪个 stage、哪次 retry 成功或失败、哪个 LLM provider/model 出错、publish 哪个子阶段失败。

### 18.12 Run Trace / Artifact Model

`intake-pipeline` 的 tracing 不能只停留在 span；最终态必须形成可查询、可回放的 intake run。

run 身份至少绑定：

- `trace_id`
- `intake_job_id`
- `source_file_id`
- `collection_id`
- `final_doc_id`，如适用
- `ticket_id`，如适用
- `publish_id`，如适用

关键 step 至少包括：

- upload
- malware scan
- conversion
- quality
- similarity
- version check
- agent review
- approval
- asset write
- document persist
- index upsert / index build request

关键 artifact 至少包括：

- 原始文件元数据摘要
- canonical markdown / sanitized markdown 引用
- quality report 引用
- similarity / version check 摘要
- agent review 结果摘要
- approval decision 引用
- publish 结果摘要
- 发给 indexing 的 `IndexBuildRequested` 引用

规则：

- 普通 telemetry 只保留摘要、计数、hash、状态，不直接放文档正文和敏感明文。
- 详细中间产物通过 `artifact_ref` 挂到受控存储，由 `services/admin` 统一查询。
- 人工排查某次入库时，必须能按 `trace_id` 或 `intake_job_id` 看到完整 step tree、per-step latency、retry、error_code 和 artifact summary。

### 18.13 告警

必须告警：

- FileReady backlog 超阈值
- stage_tasks retry 激增
- dead letter 非零
- approval pending 超 SLA
- publish failed 非零
- malware detected
- EXTERNAL visibility conflict 非零或激增
- outbox pending 超阈值
- LLM error ratio 超阈值
- LLM schema validation failure 激增
- LLM token 用量异常增长
- review_degraded 激增
- manual_override_ratio 激增
- auto_approve_ratio 异常下降

## 19. 运维与恢复

### 19.1 管理操作

允许的管理操作：

- retry job from stage
- cancel job
- expire approval ticket
- replay outbox event
- reindex published document
- mark source file cleanable

所有管理操作必须写 audit。

### 19.2 replay 规则

事件 replay 必须安全：

- consumer 先按 `event_id` 去重
- 再按业务 idempotency_key 去重
- 已成功状态不得回退
- 不允许 replay 产生新的 final_doc_id

### 19.3 数据修复边界

允许修复：

- 重发未发送 outbox event
- 重建缺失索引
- 重新执行 failed stage
- 清理无引用对象

不允许修复：

- 修改已发布 final_doc_id
- 覆盖 approval audit
- 无审计地修改 visibility
- 手动删除有引用 object_blob
- 将敏感明文补写进 telemetry 或 llm_call_log

## 附录 A. 现有代码映射与演进约束

本章用于把当前 intake-pipeline 代码映射到目标边界。目标架构不因现有代码妥协；允许同进程部署，但代码边界必须按目标契约切开。

### A.1 stage 映射

| 当前代码阶段 | 目标组件 |
|-------------|----------|
| `ConversionStage` | conversion-worker |
| `DedupStage` | conversion-worker 的重复/相似线索或 orchestrator 重复策略 |
| `VersionStage` | conversion-worker 产出 version_conflict，approval-service 决策 |
| `QualityStage` | conversion-worker |
| `ReviewStage` | agent-review-worker |
| `DecisionStage` | approval-service + orchestrator 状态推进 |
| `AssetStage` | publishing-worker |
| `PersistStage` | publishing-worker |
| `IndexingService` | indexing-service / publishing-worker 编排 |

### A.2 同进程部署约束

允许在同一进程内运行 orchestrator 和 worker，但必须满足：

- 使用同样的 stage task 输入输出 schema
- 使用同样的 idempotency_key
- stage result 必须持久化
- 不允许 stage 直接修改 intake job 全局状态
- 不允许 approval 逻辑混入 conversion/review
- 不允许 publishing 生成 final_doc_id

### A.3 旧 intake job 模型迁移

现有 intake job 映射为新模型：

| 旧字段/概念 | 新模型 |
|------------|--------|
| `job_id` | `intake_job_id` |
| `source_files` | `source_files` + `intake_jobs` |
| `conversion_report` | `stage_results` + `conversion_results` |
| `status` | `intake_job_state` |
| `report_asset_path` | stage result artifact |

迁移策略：

- 已完成旧 job 保留只读历史
- 新摄入只写新 `intake_jobs`
- 如需查询统一视图，由 `services/admin` 聚合旧 intake job 记录和新 `intake_jobs`
