# persistence 对外接口契约

## 顶层导出 (`from reality_rag_persistence import ...`)

| 符号 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `EventPublisher` | class | `outbox.py:25` | 事务性 outbox 事件发布器 |
| `OutboxDispatcher` | class | `outbox.py:191` | 后台轮询事件投递器 |
| `IngestionMonitorStore` | class | `ingestion_monitor.py:19` | 文件系统摄入监控存储 |
| `TERMINAL_RUN_STATUSES` | set | `ingestion_monitor.py:12` | `{"completed", "failed", "cancelled"}` |

## 基础设施 (`database.py`)

| 函数 | 说明 |
|------|------|
| `get_session() -> Session` | 获取新 SQLAlchemy Session（lazy engine） |
| `create_all()` | 创建所有表（仅 dev 用） |
| `drop_all()` | 删除所有表（仅 dev 用） |
| `override_url_for_testing(url)` | 测试用 SQLite 覆盖 |
| 环境变量: `DATABASE_URL` | PostgreSQL 连接字符串（默认 `postgresql://postgres:postgres@localhost:5432/reality_rag`） |

## 全部 Repository (`from reality_rag_persistence.repositories import ...`)

| Repository | 文件 | 操作的主要 Model |
|------------|------|-----------------|
| `AdminUserRepository` | `admin_users.py` | `AdminUserModel` |
| `AdminSessionRepository` | `admin_users.py` | `AdminSessionModel` |
| `ApiKeyRegistryRepository` | `api_key_registry.py` | `ApiKeyRegistryEntry` / `ApiKeyRegistryEntryAdmin` |
| `ApplicationProfileRepository` | `application_profiles.py` | `ApplicationProfile` |
| `ApprovalAuditLogRepository` | `approval_audit_log.py` | `ApprovalAuditLog` |
| `ApprovalTicketRepository` | `approval_tickets.py` | `ApprovalTicket` |
| `ChunkRegistryRepository` | `chunk_registry.py` | `ChunkRecord`（可选导入） |
| `CollectionProfileBindingRepository` | `collection_profile_bindings.py` | `CollectionProfileBindingModel` |
| `CollectionRepository` | `collections.py` | `Collection` |
| `ConsumerIdempotencyRepository` | `consumer_idempotency.py` | `ConsumerIdempotency` |
| `DocumentPolicyRepository` | `document_policies.py` | `DocumentPolicy` |
| `DocumentRepository` | `documents.py` | `CanonicalMetadata` |
| `IndexBuildJobRepository` | `index_build_jobs.py` | `IndexBuildJob` |
| `IndexRegistryRepository` | `index_registry.py` | `IndexVersionEntry` (dataclass) |
| `IndexVersionRepository` | `index_versions.py` | `IndexVersionRecord` |
| `IndexedDocumentRepository` | `indexed_documents.py` | `IndexedDocument` |
| `IngestionRepository` | `ingestion.py` | `IngestionJob` |
| `IntakeJobRepository` | `intake_jobs.py` | `IntakeJob`（含乐观锁） |
| `JobRepository` | `jobs.py` | `JobInfo` |
| `MalwareScanResultRepository` | `malware_scan_results.py` | `MalwareScanResult` |
| `ObjectBlobRepository` | `object_blobs.py` | `ObjectBlob`（含 ref_count GC） |
| `OpsAuditLogRepository` | `ops_audit_log.py` | `OpsAuditLogEntry` |
| `OutboxEventRepository` | `outbox_events.py` | `OutboxEvent` |
| `ParseSnapshotRepository` | `parse_snapshots.py` | `ParseSnapshotRecord` |
| `ParserProfileRepository` | `parser_profiles.py` | `ParserProfileModel` |
| `PrincipalProfileRepository` | `principal_profiles.py` | `PrincipalProfile` |
| `PublishedDocumentRepository` | `published_documents.py` | `PublishedDocument` |
| `PublishedDocumentLifecycleAuditRepository` | `published_document_lifecycle_audit.py` | `PublishedDocumentLifecycleAudit` |
| `PublishJobRepository` | `publish_jobs.py` | `PublishJob` |
| `ReindexJobRepository` | `reindex_jobs.py` | `ReindexJob` |
| `RetrievalProfileRepository` | `retrieval_profiles.py` | `RetrievalProfile` |
| `RetrievalProfileAdminRepository` | `retrieval_profiles_admin.py` | `RetrievalProfileAdminModel` |
| `RunTraceRepository` | `run_audit.py` | `RunTraceEntry` |
| `RunStepRepository` | `run_audit.py` | `RunStepEntry` |
| `TraceArtifactRepository` | `run_audit.py` | `TraceArtifactEntry` |
| `SourceFileRepository` | `source_files.py` | `SourceFile` |
| `StageAttemptRepository` | `stage_attempts.py` | `StageAttempt` |
| `StageResultRepository` | `stage_results.py` | `StageResult` |
| `StageTaskRepository` | `stage_tasks.py` | `StageTask` |
| `TenantRepository` | `tenants.py` | `Tenant` |
| `UploadSessionRepository` | `upload_sessions.py` | `UploadSession` |

## Outbox 事件类型（`EventPublisher` 便捷方法）

| 方法 | 发布的事件类型 |
|------|----------------|
| `publish(event_type, payload, ...)` | 通用 |
| `publish_stage_task_requested(...)` | `STAGE_TASK_REQUESTED` |
| `publish_stage_completed(...)` | `STAGE_COMPLETED` |
| `publish_approval_requested(...)` | `APPROVAL_REQUESTED` |
| `publish_publish_completed(...)` | `PUBLISH_COMPLETED` |
| `publish_file_ready(...)` | `FILE_READY` |

## 种子数据 (`seed.py`)

| 函数 | 说明 |
|------|------|
| `seed()` | 完整开发数据集 |
| `seed_minimal_for_tests()` | 仅 tenant + collection |
| `seed_dev_dataset()` | 演示用完整数据集 |
