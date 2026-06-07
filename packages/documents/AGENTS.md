# documents — 文档领域服务

## 定位
documents 是文档生命周期管理（上传 → 扫描 → 源文件生命周期）的共享领域逻辑库。从 `ingestion-worker` 抽取而来，`ingestion-worker` 和 `document-service` 都依赖此包。

**不做的事**：不写文档内容/治理/索引状态、不推进 `intake_job_state`、不管理 index 相关操作。

## 边界原则
- `DocumentService` 只负责 `UploadSession` / `ObjectBlob` / `SourceFile` 的领域逻辑
- 对象删除必须先检查 `ref_count`（通过 `ObjectBlobRepository`）
- 源文件的物理删除走两级：`CLEANABLE → CLEANED → ref_count=0 → GC`
- 扫描引擎通过 `ScanAdapter` Protocol 注入（生产用真实引擎，测试用 `NoOpScanAdapter`）
- 事件通过 `EventPublisher`（事务性 outbox）发送，非直接消息队列
- SQLAlchemy `Session` 由外部注入，documents 自身不管理

## 核心数据流
```
create_upload_session → complete_upload_session
    ↓
get_or_create_object_blob (dedup by content_hash)
    ↓
create_source_file (2-level dedup: published hash + active source_file)
    ↓
start_scan → complete_scan (ScanAdapter) → FILE_READY event
    ↓
claim_source_file → mark_consumed / mark_cleanable → gc_source_file → gc_object_blob
```

## 关键对象
- `DocumentService`：领域服务（`document_domain.py:77`），统筹 4 个 Repository + EventPublisher
- `ScanAdapter`：扫描引擎 Protocol（`document_domain.py:52`），`scan(storage_key) -> MalwareScanResult`
- `NoOpScanAdapter`：默认 no-op 实现，始终返回 CLEAN
- `object_id_from_hash()`：从 content_hash 生成稳定的 ObjectBlob ID（`document_domain.py:410`）
- ID 前缀：`upl_` (upload), `src_` (source file), `scan_` (scan), `obj_sha256_` (blob)

## 约束
- 不得在包外创建 `UploadSession` / `ObjectBlob` / `SourceFile` —— 所有生命周期操作都通过 `DocumentService`
- 引用计数由 `link_object_ref` / `unlink_object_ref` 管理，禁止直接操作 `ref_count`
- `dedup_check()` 做两级去重：已发布的 final_doc 全文 hash 去重 + 同一 collection 内活跃的 source_file 去重
- `FILE_READY` 事件 payload 必须包含 `tenant_id`（从 collection 查找注入）
- 生产环境请注入真实的 `ScanAdapter` 实现，不要用 `NoOpScanAdapter`
