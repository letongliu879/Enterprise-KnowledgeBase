# documents 对外接口契约

## 导出的公共符号

| 符号 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `DocumentService` | class | `document_domain.py:77` | 文档领域服务（上传/扫描/源文件生命周期） |
| `ScanAdapter` | Protocol | `document_domain.py:52` | 扫描引擎接口：`scan(storage_key) -> MalwareScanResult` |
| `NoOpScanAdapter` | class | `document_domain.py:60` | No-op 实现，始终返回 CLEAN |
| `object_id_from_hash` | function | `document_domain.py:410` | 从 content_hash 生成 ObjectBlob ID |

## DocumentService API

### Upload Session 操作

| 方法 | 签名 | 说明 |
|------|------|------|
| `create_upload_session` | `(source, user_id, trace_id, expected_size, expected_sha256, upload_id?) -> UploadSession` | 创建 ACTIVE upload session |
| `complete_upload_session` | `(upload_id, received_size) -> UploadSession\|None` | 标记 COMPLETED |

### Object Blob 操作

| 方法 | 签名 | 说明 |
|------|------|------|
| `get_or_create_object_blob` | `(content_hash, storage_key, size_bytes) -> ObjectBlob` | 去重创建（dedup by hash） |
| `link_object_ref` | `(object_id) -> bool` | 增加 ref_count |
| `unlink_object_ref` | `(object_id) -> bool` | 减少 ref_count |
| `gc_object_blob` | `(object_id) -> bool` | ref_count==0 时物理删除 |

### Source File 操作

| 方法 | 签名 | 说明 |
|------|------|------|
| `create_source_file` | `(collection_id, object_id, content_hash, ...) -> SourceFile` | 创建含 dedup 检查的源文件 |
| `claim_source_file` | `(source_file_id, job_id) -> bool` | 申领给 intake job |
| `mark_consumed` | `(source_file_id, job_id) -> bool` | 标记 CONSUMED |
| `mark_cleanable` | `(source_file_id, job_id) -> bool` | 标记 CLEANABLE（GC 候选） |
| `gc_source_file` | `(source_file_id) -> bool` | 清理 + 释放 blob ref |
| `release_claim` | `(source_file_id) -> bool` | 释放回 READY |

### 扫描

| 方法 | 签名 | 说明 |
|------|------|------|
| `start_scan` | `(source_file_id) -> SourceFile\|None` | 标记 SCANNING |
| `complete_scan` | `(source_file_id) -> SourceFile\|None` | 执行扫描，转 READY/FAILED，发 FILE_READY 事件 |

### 去重

| 方法 | 签名 | 说明 |
|------|------|------|
| `dedup_check` | `(content_hash, collection_id, document_repo) -> tuple[bool, str\|None]` | 两级去重检查 |

## 依赖的外部契约（from reality_rag_contracts）

| 类型 | 用途 |
|------|------|
| `UploadSession` / `UploadSessionStatus` | 上传会话 |
| `ObjectBlob` / `ObjectBlobStatus` | 二进制对象存储 |
| `SourceFile` / `SourceFileState` | 源文件生命周期 |
| `MalwareScanResult` / `ScanVerdict` | 扫描结果 |
| `EventType.FILE_READY` | 源文件就绪事件 |

## ID 命名约定

| ID | 前缀 | 示例 |
|----|------|------|
| Upload ID | `upl_` | `upl_a1b2c3d4e5f6` |
| Source File ID | `src_` | `src_f6e5d4c3b2a1` |
| Scan Result ID | `scan_` | `scan_a1b2c3d4...` |
| Object Blob ID | `obj_sha256_` | `obj_sha256_e3b0c442...` |

## 依赖的 Repository（from reality_rag_persistence）

| Repository | 用途 |
|------------|------|
| `UploadSessionRepository` | Upload session 持久化 |
| `ObjectBlobRepository` | Object blob + ref_count |
| `SourceFileRepository` | Source file 状态管理 |
| `CollectionRepository` | Collection 查询（获取 tenant_id） |
| `MalwareScanResultRepository` | 扫描结果 |
| `EventPublisher` | 事务性 outbox 事件发送 |
