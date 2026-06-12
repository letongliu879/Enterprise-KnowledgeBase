# workbench-api 接口契约

## 认证
- 所有 `/workbench/*` 路由要求 `Authorization: Bearer <JWT>`
- `/internal/events/*` 继续要求对应的 `X-Service-Key`

## 角色
- `uploader`: 上传文件、查看上传任务、查看文档与原文/解析结果
- `chunk_editor`: 管理 draft edits、提交已发布 chunk revision
- `reviewer`: 查看并决策 review ticket
- `knowledge_admin` / `platform_admin`: 文档生命周期动作 `archive / retract / reindex`

## Inbound API

### Auth
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/auth/me` | 当前用户信息 |
| GET | `/workbench/health` | workbench 健康检查 |
| GET | `/workbench/health/all` | 下游聚合健康检查 |

### Upload
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/workbench/uploads` | 创建上传会话 |
| GET | `/workbench/uploads` | 当前用户上传列表 |
| GET | `/workbench/uploads/{upload_id}` | 单上传会话详情 |
| DELETE | `/workbench/uploads/{upload_id}` | 删除上传会话 |
| POST | `/workbench/uploads/{upload_id}/content` | 上传文件内容 |

`POST /workbench/uploads`
```json
{
  "collection_id": "col_default",
  "filename": "demo.docx",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "size_bytes": 1024,
  "selected_parser_profile_id": "optional",
  "parser_override_json": {},
  "access_scope_json": {}
}
```

### Parse Snapshot / Chunks
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/parse-snapshots/{parse_snapshot_id}` | ParseSnapshot 详情 |
| GET | `/workbench/parse-snapshots/{parse_snapshot_id}/chunks` | ParseSnapshot chunk 列表 |
| GET | `/workbench/chunks/{evidence_id}` | 单 chunk 详情 |
| PATCH | `/workbench/chunks/{evidence_id}` | 已发布 chunk revision |

### Draft Chunk Edits
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/workbench/parse-snapshots/{parse_snapshot_id}/chunk-edits` | 创建 draft edit |
| GET | `/workbench/parse-snapshots/{parse_snapshot_id}/chunk-edits` | draft edit 列表 |
| PUT | `/workbench/chunk-edits/{chunk_edit_id}` | 更新 draft edit |
| DELETE | `/workbench/chunk-edits/{chunk_edit_id}` | 删除 draft edit |
| POST | `/workbench/chunk-edits/{chunk_edit_id}/submit` | 提交到 indexing |

### Review
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/tickets` | 复核工单列表 |
| GET | `/workbench/tickets/{ticket_id}` | 工单详情 |
| GET | `/workbench/tickets/{ticket_id}/agent-review` | AgentReview 结果 |
| POST | `/workbench/tickets/{ticket_id}/decide` | Approve / Reject / Return |
| GET | `/workbench/tickets/{ticket_id}/workspace` | ticket 视角工作台 |
| POST | `/workbench/tickets/{ticket_id}/transfer` | Transfer ticket to another user |
| GET | `/workbench/tickets/{ticket_id}/comments` | List ticket comments |
| POST | `/workbench/tickets/{ticket_id}/comments` | Create comment |

### Comments
| 方法 | 路径 | 说明 |
|------|------|------|
| PATCH | `/workbench/comments/{comment_id}` | Edit own comment |
| DELETE | `/workbench/comments/{comment_id}` | Delete own comment |

### Task Projection
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/tasks` | 上传链路聚合任务列表 |
| GET | `/workbench/tasks/{upload_id}` | 单任务详情 |
| POST | `/workbench/tasks/{upload_id}/recover` | 手动恢复 stuck task |
| POST | `/workbench/tasks/{upload_id}/cancel` | Cancel in-progress upload |

### Notifications
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/notifications` | List notifications |
| PATCH | `/workbench/notifications/{id}/read` | Mark one read |
| POST | `/workbench/notifications/read-all` | Mark all read |
| GET | `/workbench/notifications/unread-count` | Unread count |

### Documents
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/documents` | 文档投影列表 |
| GET | `/workbench/documents/{doc_id}` | 单文档投影详情 |
| GET | `/workbench/documents/{doc_id}/workspace` | 文档视角工作台 |
| POST | `/workbench/documents/{doc_id}/archive` | 单文档归档 |
| POST | `/workbench/documents/{doc_id}/retract` | 单文档撤回 |
| POST | `/workbench/documents/{doc_id}/reindex` | 单文档重建索引 |
| POST | `/workbench/documents/{doc_id}/share` | Generate share link |
| POST | `/workbench/documents/batch/archive` | 批量归档 |
| POST | `/workbench/documents/batch/retract` | 批量撤回 |
| POST | `/workbench/documents/batch/reindex` | 批量重建索引 |

`GET /workbench/documents` 查询参数
```text
collection_id?
document_state?
status?          # legacy alias
offset?
limit?
order_by?
order_dir?
```

单文档生命周期请求
```json
{
  "reason": "manual cleanup",
  "index_profile_id": "ragflow"
}
```

批量生命周期请求
```json
{
  "doc_ids": ["doc_001", "doc_002"],
  "reason": "refresh after parser upgrade",
  "index_profile_id": "ragflow"
}
```

批量生命周期响应
```json
{
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "items": [
    {
      "doc_id": "doc_001",
      "success": true,
      "previous_state": "PUBLISHED",
      "new_state": "REINDEXING",
      "job_id": "idx_job_001"
    },
    {
      "doc_id": "doc_002",
      "success": false,
      "error_code": "CONFLICT",
      "error_message": "Document does not have a parse snapshot and cannot be reindexed"
    }
  ]
}
```

### Source Preview
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/source-files/{source_file_id}/content` | 原文件下载元数据 |
| GET | `/workbench/source-files/{source_file_id}/preview` | 原文预览元数据 |
| GET | `/workbench/source-files/{source_file_id}/preview/content` | 原文预览内容流 |

### Retrieval
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/workbench/retrieve` | 检索验证 |
| GET | `/workbench/query-runs` | 检索历史 |
| GET | `/workbench/query-runs/{query_run_id}` | 单次检索详情 |

### Dashboard
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/dashboard` | Aggregated dashboard stats |

### Trash
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/trash` | List trashed documents |
| POST | `/workbench/trash/{doc_id}/restore` | Restore from trash |
| DELETE | `/workbench/trash/{doc_id}` | Permanently delete |

### Collections / Profiles Proxy
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench/collections` | admin collection 列表代理 |
| POST | `/workbench/collections` | 创建 collection |
| GET | `/workbench/collections/{id}` | collection 详情 |
| PATCH | `/workbench/collections/{id}` | 更新 collection |
| DELETE | `/workbench/collections/{id}` | 删除 collection |
| GET | `/workbench/retrieval-profiles` | retrieval profile 列表 |
| POST | `/workbench/retrieval-profiles` | 创建 profile |
| GET | `/workbench/retrieval-profiles/{id}` | profile 详情 |
| PATCH | `/workbench/retrieval-profiles/{id}` | 更新 profile |
| DELETE | `/workbench/retrieval-profiles/{id}` | 删除 profile |
| POST | `/workbench/retrieval-profiles/{id}/publish` | 发布 profile |
| POST | `/workbench/retrieval-profiles/{id}/clone` | 克隆 profile |
| GET | `/workbench/parser-profiles` | parser profile 列表 |
| POST | `/workbench/parser-profiles` | 创建 profile |
| GET | `/workbench/parser-profiles/{id}` | profile 详情 |
| PATCH | `/workbench/parser-profiles/{id}` | 更新 profile |
| DELETE | `/workbench/parser-profiles/{id}` | 删除 profile |
| POST | `/workbench/parser-profiles/{id}/publish` | 发布 profile |
| POST | `/workbench/parser-profiles/{id}/clone` | 克隆 profile |
| GET | `/workbench/api-keys` | API key 列表 |
| POST | `/workbench/api-keys` | 创建 API key |
| GET | `/workbench/api-keys/{id}` | API key 详情 |
| PATCH | `/workbench/api-keys/{id}` | 更新 API key |
| DELETE | `/workbench/api-keys/{id}` | 删除 API key |
| GET | `/workbench/api-keys/{id}/usage` | API key 用量 |
| GET | `/workbench/audit-logs` | 审计日志列表 |
| POST | `/workbench/audit-logs/export` | 审计日志导出 |
| GET | `/workbench/dashboard` | 仪表盘 |
| GET | `/workbench/trash` | 回收站列表 |
| POST | `/workbench/trash/{id}/restore` | 恢复文档 |
| DELETE | `/workbench/trash/{id}` | 永久删除 |

### Events
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/internal/events/{service}` | intake / approval / indexing 事件写入投影 |

## Outbound API
- `DocumentServiceClient -> POST /upload`
- `IntakeClient -> /internal/source-files/*`, `/internal/intake-jobs/*`, `/internal/published-documents/*`
- `IndexingClient -> /internal/parse-previews`, `/internal/parse-snapshots/*`, `/internal/chunks/*`
- `ApprovalClient -> /internal/tickets/*`
- `AccessClient -> POST /v1/retrieve`
- `AdminClient -> /admin/collections*`, `/admin/retrieval-profiles*`, `/admin/documents/{final_doc_id}/{archive|retract|reindex}`

## 错误码
| 代码 | HTTP | 说明 |
|------|------|------|
| `DOWNSTREAM_NOT_IMPLEMENTED` | 501 | 下游接口未实现 |
| `DOWNSTREAM_UNAVAILABLE` | 503 | 下游不可达或超时 |
| `CONFLICT` | 409 | 资源状态冲突或本地上下文不足 |
| `UNAUTHORIZED` | 401 | JWT 缺失或无效 |
| `FORBIDDEN` | 403 | 角色或 collection 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `BAD_REQUEST` | 400 | 请求参数错误 |

## 行为说明
- `GET /workbench/documents/{doc_id}/workspace` 是文档管理页的主详情接口
- 文档生命周期动作只暴露 `doc_id`，workbench 内部再解析 `final_doc_id / collection_id / tenant_id / parse_snapshot_id`
- 文档生命周期动作仍然是 admin-only，并且只对“已发布且可管理”的文档开放
- `archive` / `retract` 使用稳定幂等键
- `reindex` 每次请求都生成新的幂等键，允许同一文档被重复重建
- 批量动作采用 best-effort，逐条返回结果，不做 all-or-nothing
- `/workbench/documents` 的 ticket/task 摘要字段通过批量 projection 查找补齐，不能退化成逐文档 fan-out
- `Source` 只消费 source preview，`Parsed text` 来自 ParseSnapshot `preview_text`
- workbench 不直接写 source file、ticket、published document、indexed chunk，也不直写 OpenSearch/Qdrant
