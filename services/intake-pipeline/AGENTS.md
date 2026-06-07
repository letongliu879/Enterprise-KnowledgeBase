# intake-pipeline — 企业知识摄入控制面

## 定位
intake-pipeline 是平台唯一的摄取控制面 owner，负责从外部文件安全、可审计、可恢复地转化为可检索、可治理、可发布的知识文档。

**不做的事**：文档解析分块与索引写入（归 indexing）、检索过滤与排序（归 retrieval）、解析预览 UI 与参数调试（归 workbench-api）。

## 边界原则
- `ingestion-worker` 是唯一拥有 `intake_job_state` 的组件；其他 worker 只接收任务、提交结果，不得推进全局状态
- `document-service` 是 `source_file_state` 的唯一 owner；orchestrator 通过 HTTP API 进行 claim/consumed/cleanable 操作，不得直接写表
- `approval-service` 是 `approval_ticket_state` 和 `final_doc_id` 的唯一 owner；publishing-worker 不得生成或修改 `final_doc_id`
- `publishing-worker` 是 `published_document_state` 的唯一 owner；admin 只能通过 publishing domain 的受控命令变更 lifecycle state
- 所有跨服务事件必须通过 outbox pattern：同一事务写业务状态 + outbox_events，dispatcher 异步发送，consumer 按 event_id 去重
- 所有阶段必须有显式幂等键：`{intake_job_id}:{stage_name}:{schema_version}:{input_hash}`
- `published_documents` 是发布生命周期的唯一事实源，`documents`/`document_policies` 只作为兼容读模型
- `dataset_id/file_id` 只能作为 indexing workbench 引用，不得替代 `collection_id/final_doc_id`
- 人工打回需要重跑时，必须递增 `approval_round`，保留旧 ticket 和审计

## 核心数据流
```
上传: POST /upload -> DocumentService -> SHA-256 校验 + 恶意扫描
  -> source_file state: UPLOADING -> UPLOADED -> SCANNING -> READY -> FileReady(outbox)

摄入: FileReady -> intake-orchestrator -> claim -> 创建 intake_job
  -> CONVERSION_QUEUED -> conversion-worker 执行转换
  -> REVIEW_QUEUED -> agent-review-worker 执行 PII/风险审核
  -> APPROVAL_REQUESTED -> approval-service 决策
  -> APPROVAL_DECIDED(approve) -> PUBLISH_QUEUED -> publishing-worker 执行发布
  -> PUBLISHED

发布: PublishRequested -> AssetWrite -> PersistDocument -> RequestIndexBuild
  -> WaitIndexReady -> VerifyPublished -> PublishCompleted

生命周期: PUBLISHED -> ARCHIVED / DEPRECATED / RETRACTED / REINDEXING
```

## 关键对象
- `source_file_state`：UPLOADING -> UPLOADED -> SCANNING -> READY -> CLAIMED -> CONSUMED -> CLEANABLE -> CLEANED / FAILED，由 document-service 管理
- `intake_job_state`：CREATED -> CONVERSION_* -> REVIEW_* -> APPROVAL_REQUESTED -> APPROVAL_DECIDED -> PUBLISH_* -> PUBLISHED / REJECTED / FAILED / CANCELLED / EXPIRED，由 orchestrator 管理
- `approval_ticket_state`：SYSTEM_DECIDED / PENDING -> APPROVED / REJECTED / RETURNED / EXPIRED，由 approval-service 管理
- `publish_state`：PUBLISH_CREATED -> ASSET_WRITING -> ASSET_WRITTEN -> PERSISTING -> PERSISTED -> INDEXING -> INDEXED -> PUBLISH_SUCCEEDED / PUBLISH_FAILED，由 publishing-worker 管理
- `published_document_state`：PUBLISHED -> ARCHIVED / DEPRECATED / RETRACTED / REINDEXING，由 publishing domain 管理

## 子服务职责矩阵

| 子服务 | 拥有 | 不拥有 |
|--------|------|--------|
| document-service | upload_sessions, object_blobs, source_files, malware_scan, FileReady outbox | 文档转换、审批、发布 |
| ingestion-worker (orchestrator) | intake_jobs, stage_tasks, stage_attempts, stage_results, 全局状态机 | 具体转换、LLM 审核、写索引 |
| conversion-worker | conversion_results，转换/清洗/质量/相似度/版本线索 | 发布决策、全局状态推进 |
| agent-review-worker | agent_review_results, PII spans, visibility facts | 最终发布决策、标签治理 |
| approval-service | approval_tickets, approval_audit_log, final_doc_id 生成 | 资产写入、索引、发布 |
| publishing-worker | published_documents, published_document_lifecycle_audit, publish_jobs, 资产写入 | 审批、chunking/embedding 细节 |
| indexing-service (facade) | 转发 index run/activate/rollback | 审批、发布决策、全局 job 状态 |

## 身份标识规则
- `upload_id` = `upl_` + ULID，由 document-service 生成
- `source_file_id` = `src_` + ULID，per-collection 唯一
- `object_id` = `obj_sha256_{hash}`，内容寻址
- `intake_job_id` = `job_` + ULID，每个 source_file 唯一
- `stage_attempt_id` = `att_` + ULID
- `ticket_id` = `atck_` + token_hex(12)，由 approval-service 生成
- `final_doc_id` = `doc_{logical_id}_v{N}`，由 approval-service 唯一生成
- `publish_id` = `pub_` + ULID

## 幂等键规则
```
idempotency_key = "{intake_job_id}:{stage_name}:{schema_version}:{input_hash}"
```
- 同一 key 已成功 -> 直接返回已有 stage result
- 同一 key 正在运行 -> 不重复派发
- 同一 key 已失败且可重试 -> 在同一个 `stage_task_id` 下创建新的 `stage_attempt_id`
- 不同 `input_hash` -> 不得复用旧结果
- 人工打回重跑 -> 新 `stage_task_id`，input 中加入 `rerun_round` + `return_reason_code`

## 约束
- worker 不得直接写 `intake_jobs.state`，只能写 stage result，由 orchestrator 校验后推进
- 状态迁移必须使用乐观锁或版本号（`state_version`）
- 只有 `READY` 的 source file 可以创建 intake job
- 同一 `source_file_id` 最多绑定一个 `intake_job_id`
- `final_doc_id` 一旦发布不得修改
- `REJECTED` 不得生成 `final_doc_id`
- `RETURNED` 必须带 `return_target_stage` 和 `return_reason`
- 所有审批决策必须追加审计日志，不允许 update 覆盖
- 已发布文档生命周期变更只追加审计，不覆盖历史记录
- 配置变更必须写审计，并通过 `config_version` 被 stage task、approval decision、LLM call log 引用
- telemetry 禁止保存文档正文、PII 原值、完整 prompt/response 明文
- `active_index_version` 只能由 publishing domain 在消费匹配的 `IndexReady` 后条件更新
- 不允许通过 admin 旁路直接写 `published_documents`、`documents`、`index_build_jobs`

## 关键事件契约
| 事件 | 方向 | 语义 |
|------|------|------|
| FileReady | document-service -> orchestrator | source file 可创建 intake job |
| StageTaskRequested | orchestrator -> worker | 唤醒 worker 领取阶段任务 |
| StageCompleted | worker -> orchestrator | 阶段结果已持久化 |
| ApprovalRequested | orchestrator -> approval-service | 请求治理决策 |
| ApprovalPending | approval-service -> orchestrator | 已创建人工工单 |
| ApprovalDecided | approval-service -> orchestrator | 决策结果 |
| PublishRequested | orchestrator -> publishing-worker | 请求发布 |
| IndexBuildRequested | publishing-worker -> indexing-service | 请求构建索引 |
| PublishCompleted | publishing-worker -> orchestrator | 发布完成 |
| IndexReady | indexing-service -> publishing-worker | 索引已可检索 |
| DocumentLifecycleChanged | publishing domain -> retrieval/indexing | 生命周期变化 |

## 重试策略
| 阶段 | 默认策略 | 最大次数 |
|------|----------|----------|
| conversion | exponential backoff 1m/5m/15m | 3 |
| agent_review | 30s/2m/10m | 5 |
| publishing asset | 1m/5m/15m | 5 |
| publishing persist | 1m/5m/15m | 5 |
| publishing index | 1m/5m/15m/1h | 10 |

不可重试：unsupported file type / hash mismatch / malware infected / schema incompatible / collection not found / visibility invalid
