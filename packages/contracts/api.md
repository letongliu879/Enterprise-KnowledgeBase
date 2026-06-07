# contracts 对外接口契约

## 导出的模块

### 枚举 (`from reality_rag_contracts import *`)

| 枚举 | 位置 | wire value 示例 |
|------|------|-----------------|
| `PublishStatus` | enums.py:6 | `draft`, `pending_review`, `published` |
| `IndexStatus` | enums.py:15 | `not_indexed`, `indexing`, `indexed` |
| `JobStatus` | enums.py:23 | `pending`, `running`, `completed`, `failed` |
| `BudgetPolicy` | enums.py:38 | `focused`, `balanced`, `comprehensive` |
| `DocumentSupportTier` | enums.py:45 | `A`, `B`, `C`, `D` |
| `ReviewDecision` | enums.py:53 | `approve`, `reject`, `quarantine` |
| `AdminRole` | enums.py:60 | `platform_admin`, `knowledge_admin`, `reviewer` |
| `ProfileState` | enums.py:68 | `draft`, `published`, `retired` |
| `ApiKeyState` | enums.py:74 | `active`, `disabled`, `revoked` |
| `CollectionLifecycleState` | enums.py:81 | `active`, `archived`, `disabled` |
| `ConversionStatus` | enums.py:87 | `success`, `failed`, `partial` |
| `GovernanceSource` | enums.py:94 | `persisted`, `stubbed`, `unavailable` |
| `HumanReviewStatus` | enums.py:100 | `pending`, `approved`, `deferred` |
| `SourceFileState` | enums.py:107 | `uploading`, `scanned`, `cleanable`, `failed` |
| `UploadSessionStatus` | enums.py:121 | `active`, `completed`, `expired` |
| `ObjectBlobStatus` | enums.py:131 | `active`, `gc_pending`, `deleted` |
| `ScanVerdict` | enums.py:139 | `clean`, `infected`, `error` |
| `IndexRegistryStatus` | enums.py:147 | `indexing`, `indexed`, `active` |
| `IntakeJobState` | enums.py:154 | `created`, `queued`, `processing`, `completed` |
| `StageTaskState` | enums.py:176 | `queued`, `running`, `succeeded`, `failed` |
| `StageAttemptState` | enums.py:187 | `running`, `succeeded`, `failed`, `timeout` |
| `StageName` | enums.py:197 | `conversion`, `agent_review`, `publishing` |
| `ApprovalTicketState` | enums.py:205 | `pending`, `approved`, `rejected`, `returned` |
| `ApprovalAction` | enums.py:216 | `system_approve`, `approve`, `reject` |
| `PublishedDocumentState` | enums.py:227 | `published`, `archived`, `deprecated`, `retracted` |
| `PublishJobState` | enums.py:238 | `created`, `asset_writing`, `persisting` |
| `ReindexJobState` | enums.py:250 | `created`, `index_building`, `activating` |
| `IndexBuildJobState` | enums.py:260 | `created`, `chunking`, `embedding`, `upserting` |
| `IndexedDocumentState` | enums.py:272 | `candidate`, `active`, `tombstoned` |
| `VersionDecision` | enums.py:280 | `new_version`, `independent_document` |
| `OutboxStatus` | enums.py:288 | `pending`, `sent`, `failed` |
| `EventType` | enums.py:296 | `FileReady`, `StageTaskRequested`, `IndexBuildRequested` ... |
| `TelemetryStatus` | enums.py:314 | `started`, `succeeded`, `failed` |
| `TelemetryEventName` | enums.py:324 | ~40 事件名 |
| `LLMCallStatus` | enums.py:375 | `succeeded`, `failed`, `timeout` |
| `OutputMode` | enums.py:32 | `evidence_only`, `with_metadata`, `prompt_text` |

### 状态机

| 状态机 | 位置 | 用途 |
|--------|------|------|
| `DocumentPublishStateMachine` | state_machine.py:18 | `PublishStatus` 之间的 13 条转换 |
| `IndexStateMachine` | state_machine.py:118 | `IndexStatus` 之间的 11 条转换 |
| `IndexRegistryStateMachine` | state_machine.py:181 | `IndexRegistryStatus` 之间的 3 条转换 |
| `InvalidTransitionError` | state_machine.py:14 | 非法转换异常 |

### 索引命名函数

| 函数 | 位置 | 用途 |
|------|------|------|
| `build_versioned_backend_name()` | index_naming.py:18 | 构建稳定的物理后端资源名 |
| `build_opensearch_index_name()` | index_naming.py:43 | 构建 OpenSearch 索引名 |
| `build_qdrant_collection_name()` | index_naming.py:56 | 构建 Qdrant collection 名 |

### 配置

| 类型/函数 | 位置 | 用途 |
|-----------|------|------|
| `IndexingModelConfig` | config.py:16 | Chat + Embedding 模型配置（dataclass） |
| `IndexBackendConfig` | config.py:27 | 后端模式 + URL 配置 |
| `IndexingConfig` | config.py:34 | 聚合配置 |
| `load_indexing_config()` | config.py:40 | 从环境变量加载，链式 fallback |
| `normalize_chat_model()` | config.py:157 | Chat 模型名归一化 |
| `normalize_embedding_model()` | config.py:168 | Embedding 模型别名解析 |

### Indexing 数据模型

| 模型 | 位置 | 用途 |
|------|------|------|
| `IndexVersionStatus` | indexing_models.py:9 | 索引版本状态 StrEnum |
| `IndexVersionRecord` | indexing_models.py:20 | 索引版本 DB 记录 |
| `ChunkRecord` | indexing_models.py:40 | Chunk 后端 upsert 记录（96 字段） |
| `ParseSnapshotRecord` | indexing_models.py:99 | 解析快照记录 |

### 核心数据模型（`models.py`）

| 分组 | 模型 | 用途 |
|------|------|------|
| **租户/组织** | `Tenant` | 租户 |
| **Collection** | `Collection` | 知识库集合 |
| **应用** | `ApplicationProfile` | 应用配置 |
| **权限** | `PermissionContext`, `PrincipalProfile`, `ApiKeyRegistryEntry` | 权限上下文 |
| **治理** | `CanonicalMetadata`, `QualityReport`, `ProcessingRecord` | 企业治理记录 |
| **检索** | `RetrievalRequest`, `RetrievalResponse`, `KnowledgeContext` | 检索契约 |
| **接入 API** | `AccessRetrieveRequest`, `AccessRetrieveResponse` | 外部接入 API |
| **管理 API** | `AdminCollection`, `ParserProfile`, `DocumentSummary` | 管理后台契约 |
| **缓存** | `CacheKeyComponents` | 缓存 key 维度定义 |
| **文档** | `ConversionRequest`, `ConversionResult`, `SourceFile`, `UploadSession` | 文档生命周期 |
| **索引** | `IndexBuildRequestedCommand`, `IndexAssetBundle`, `ChunkAsset` | 索引构建 |
| **编排** | `IntakeJob`, `StageTask`, `StageAttempt`, `StageResult` | 任务编排 |
| **审批** | `ApprovalTicket`, `ApprovalAuditLog` | 审批工作流 |
| **Outbox** | `OutboxEvent`, `ConsumerIdempotency` | 事务性消息 |
| **遥测** | `TelemetryEvent`, `LLMCallLog`, `LLMCostDaily` | 可观测性 |
| **发布** | `PublishedDocument`, `PublishJob`, `ReindexJob` | 文档发布 |
| **Workbench** | `WorkbenchUploadSession`, `WorkbenchChunkEdit`, `WorkbenchTaskView` | 工作台 |

### 重大约束

- **wire 协议**: `IndexBuildRequestedCommand` 中 `final_doc_id` 用 `alias="doc_id"`，所有序列化/反序列化必须经过 Pydantic alias
- **状态转换**: 任何服务不得直接给 `status` 字段赋值，必须通过状态机的 `transition()` 方法
- **事件注册**: 新跨服务事件必须先加 `EventType` 枚举再用 `OutboxEvent` 发送
- **ID 格式**: `col-{topic}`, `ap-{name}`, `doc-{topic}`, `job-{type}-{date}-{seq}`, `ev-{seq}`
