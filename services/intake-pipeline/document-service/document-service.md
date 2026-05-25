# document-service 模块设计

> 规范性状态：子服务历史设计文档，非最终架构入口。
>
> 本文只能用于理解 `document-service` 的历史职责和旧实现意图。最终 intake-pipeline 边界、发布事实源、生命周期、manual review 退场规则以 [docs/上游机制移植总览.md](/E:/AI/My-Project/Reality-RAG/docs/上游机制移植总览.md) 和 [../intake-pipeline.md](/E:/AI/My-Project/Reality-RAG/services/intake-pipeline/intake-pipeline.md) 为准。
>
> `document-service` 不拥有 `published_documents`、`documents`、`document_policies` 或 indexing 任务；不得被实现为发布状态 owner、人工审核旁路或索引触发器。涉及已发布文档管理时，它只能作为命令入口或文件事实源协作者，状态变更必须进入 publishing domain。

## 定位

文件接收与本地文档管理服务。唯一职责：把外部文件接进来、存到本地、管起来，让下游只关心 "file_id"，不用管文件从哪来、存在哪。

## 为什么独立

| 职责 | document-service | ingestion-worker |
|------|------------------|------------------|
| 协议对接 | HTTP upload / CLI / 未来 S3 webhook | 不关心 |
| 文件命名 | uuid + 防冲突 | 不关心 |
| 磁盘管理 | 监控空间、过期清理、目录结构 | 不关心 |
| 文件生命周期 | 上传→就绪→处理中→可清理 | 只读 "处理中" 的文件 |
| 技术流水线 | ❌ | ✅ |

**关键解耦**：ingestion-worker 的输入从 "本地路径字符串" 变成 "document-service 的 file_id"。文件实际在哪、怎么上传的、会不会被清理，由 document-service 全权负责。

## 输入 → 内部 → 输出

### 输入

| 类型 | 内容 |
|------|------|
| **HTTP 上传** | `POST /upload` multipart/form-data，带 collection_id |
| **CLI 推送** | `rag-cli push ./本地文件.pdf --collection finance` |
| **管理指令** | 查询文件状态、删除、重命名、批量清理 |
| **环境配置** | `DOCUMENT_STAGING_DIR`（默认系统 temp）、`MAX_FILE_SIZE`、`RETENTION_HOURS` |

**Upload 接口：**

```python
POST /upload
Content-Type: multipart/form-data

collection_id=finance
file=<二进制内容>

Response: { "file_id": "doc-a1b2c3d4", "status": "ready" }
```

### 内部

**三层职责：**

```
[接收层]
  HTTP / CLI 请求
       │
       ▼
[存储层]  
  生成 file_id (uuid)
  按 collection 分目录落盘：{staging_dir}/{collection_id}/{file_id}-{original_name}
  记录元数据到本地 SQLite/PostgreSQL
       │
       ▼
[管理层]
  维护 file 记录：id, path, original_name, size, collection_id, 
                 status (ready | processing | ingested | failed), 
                 uploaded_at, expires_at
  定时任务：清理过期的、标记 orphaned 的
```

**文件状态机：**

```
UPLOADED → READY → PROCESSING → INGESTED → CLEANABLE
              │         │           │
              │         └── 由 ingestion-worker 回写
              └── 落盘完成即可处理
```

**清理策略：**
- 默认 24h 后自动删除（可配置 `RETENTION_HOURS`）
- ingestion-worker 成功后会通知 document-service 标记 `INGESTED`，可提前清理
- 磁盘空间低于阈值时，优先清理已 `INGESTED` 和 `FAILED` 的文件

### 输出

| 类型 | 内容 |
|------|------|
| **file_id 引用** | 给 ingestion-worker 的输入，如 `doc-a1b2c3d4` |
| **文件读取** | 内部 API：`GET /internal/files/{file_id}/path` 返回本地绝对路径（仅限内网服务调用）|
| **文件流** | 内部 API：`GET /internal/files/{file_id}/stream` 返回文件句柄/bytes |
| **状态查询** | `GET /files/{file_id}` 返回元数据、当前状态、过期时间 |

## 和 ingestion-worker 的协作

**之前（错）：**
```
运维人员 → scp 到服务器 /data/uploads/合同.pdf
         → 调 ingestion-worker: POST /convert { source_file_path: "/data/uploads/合同.pdf" }
         → worker 读这个绝对路径（可能不存在、没权限、被清理）
```

**之后（对）：**
```
运维人员 → 调 document-service: POST /upload (上传文件)
         ← 拿到 file_id: "doc-abc123"
         
         → 调 ingestion-worker: POST /convert { file_id: "doc-abc123", collection_id: "finance" }
         → worker 调 document-service: GET /internal/files/doc-abc123/path
         ← 拿到 /staging/finance/doc-abc123-合同.pdf
         → worker 处理文件
         → worker 回写 document-service: PATCH /internal/files/doc-abc123/status { status: "INGESTED" }
         → document-service 按需清理
```

**或者由调度器驱动（推荐）：**
```
document-service 收到上传后，直接通知调度器/ingestion-worker：
  POST /internal/ingestion/jobs
  { "file_id": "doc-abc123", "collection_id": "finance", "local_path": "..." }
运维人员只需要上传，不需要手动触发 ingestion。
```

## 模块边界

| 责任 | document-service | ingestion-worker | 运维人员 |
|------|------------------|------------------|---------|
| 文件从哪来 | 接收并落盘 | 不关心 | 上传 |
| file_id 怎么生成 | ✅ UUID | ❌ | 不关心 |
| 存在哪个目录 | ✅ 自己管 | ❌ | 不关心 |
| 什么时候清理 | ✅ 按策略 | ❌ | 不关心 |
| 文件转 Markdown | ❌ | ✅ | 不关心 |
| 质量评分 | ❌ | ✅ | 不关心 |
| 审核决策 | ❌ | ❌（给 approval-service） | 拍板 |

## 接口设计（核心）

```python
# 对外：上传
POST   /upload                          → { file_id, status, expires_at }
GET    /files/{file_id}                 → 元数据
DELETE /files/{file_id}                 → 手动删除（权限校验）

# 对内：供 ingestion-worker 调用
GET    /internal/files/{file_id}/path   → { local_path }  （服务间调用，带 auth）
PATCH  /internal/files/{file_id}/status → 更新状态
GET    /internal/files?status=READY     → 批量获取待处理文件（调度器轮询用）
```

## 一句话

> **document-service 是文件进入系统的「码头」。所有文件先到这里登记、入库（本地 staging）、拿到统一编号 file_id，下游只认编号不认路径。上传协议、存储位置、生命周期管理，全部封死在模块内部。**
