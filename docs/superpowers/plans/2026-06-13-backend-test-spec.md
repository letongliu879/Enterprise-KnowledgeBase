# Backend API Test Specification

> Based on `docs/superpowers/plans/2026-06-13-backend-api-contract.md`
> Covers: normal flow, error flow, permissions, data consistency, boundary conditions

---

## 1. 认证与元数据

### 1.1 `GET /workbench/auth/me`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| AUTH-001 | 正常 | 有效 JWT → 用户信息 | 200 + `{ user_id, email, display_name, roles, tenant_id, allowed_collections }` |
| AUTH-002 | 正常 | allowed_collections 非空 | 列表包含至少一条 |
| AUTH-ERR-001 | 异常 | 无 Authorization header | 401 UNAUTHORIZED |
| AUTH-ERR-002 | 异常 | 过期 JWT | 401 UNAUTHORIZED |
| AUTH-ERR-003 | 异常 | 非法 token 格式 | 401 UNAUTHORIZED |
| AUTH-ERR-004 | 异常 | 认证服务未部署 | 501 NOT_IMPLEMENTED |

### 1.2 `GET /workbench/health/all`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| HLTH-001 | 正常 | 全部服务 UP | `all_healthy: true`, 5 个服务均 ok |
| HLTH-002 | 正常 | 某服务 degraded | `all_healthy: false`, 对应 status = "degraded" |
| HLTH-003 | 异常 | 某服务超时 | 仍返回其他服务, 超时服务标记 timeout |

---

## 2. 知识库集合

### 2.1 `GET /workbench/collections`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| COL-001 | 正常 | 租户有 3 个集合 | `total: 3`, items 字段完整 |
| COL-002 | 正常 | 空租户 | `items: [], total: 0` |
| COL-003 | 权限 | 多租户隔离 | 只返回本租户集合 |
| COL-ERR-001 | 异常 | 空 tenant_id | 400 INVALID_INPUT |

### 2.2 `POST /workbench/collections`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| COL-CRT-001 | 正常 | 完整参数创建 | 201 + `{ collection_id }` |
| COL-CRT-002 | 正常 | 最小参数 | 201 |
| COL-CRT-003 | 一致 | 创建后查询列表 | 新集合出现在列表 |
| COL-CRT-ERR-001 | 异常 | 集合 ID 重复 | 409 CONFLICT |
| COL-CRT-ERR-002 | 异常 | 缺少 tenant_id | 400 INVALID_INPUT |
| COL-CRT-ERR-003 | 权限 | 操作员操作 | 403 FORBIDDEN |

### 2.3 `DELETE /workbench/collections/:id`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| COL-DEL-001 | 一致 | 删除后查询列表 | 列表不再包含该集合 |
| COL-DEL-ERR-001 | 异常 | 集合下有文档 | 409 HAS_ACTIVE_DOCUMENTS |
| COL-DEL-ERR-002 | 异常 | 集合不存在 | 404 NOT_FOUND |
| COL-DEL-ERR-003 | 权限 | 操作员 | 403 FORBIDDEN |

### 2.4 `GET /workbench/collections/:id`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| COL-STAT-001 | 正常 | 有 10 个文档的集合 | `stats.doc_count = 10` |
| COL-STAT-002 | 边界 | 空集合 | `stats.doc_count = 0, avg_chunks_per_doc = 0` |

---

## 3. 上传与任务

### 3.1 `POST /workbench/uploads`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| UPL-001 | 正常 | 有效集合 + 权限范围 | 200 + `status: "uploading"` |
| UPL-ERR-001 | 异常 | 不支持 mime_type | 400 INVALID_INPUT |
| UPL-ERR-002 | 边界 | >500MB | 400 FILE_TOO_LARGE |
| UPL-ERR-003 | 异常 | 集合不存在 | 404 NOT_FOUND |

### 3.2 `POST /workbench/uploads/:id/content`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| UPL-CONT-001 | 正常 | 上传 PDF | 200 + `status: "uploaded"` |
| UPL-CONT-002 | 状态 | 上传后等待 5s | `uploading → uploaded → parsing` |
| UPL-CONT-ERR-001 | 异常 | 不存在的 upload_id | 404 NOT_FOUND |
| UPL-CONT-ERR-002 | 异常 | 重复上传 | 409 UPLOAD_ALREADY_HAS_CONTENT |

### 3.3 `POST /workbench/tasks/:id/cancel`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| CANCEL-001 | 正常 | 取消 uploading | 200 + `status: "cancelled"` |
| CANCEL-002 | 一致 | 取消后查询 | 状态为 `cancelled` |
| CANCEL-ERR-001 | 异常 | 取消已完成的 | 409 TASK_ALREADY_FINAL |
| CANCEL-ERR-002 | 异常 | 不存在的任务 | 404 NOT_FOUND |

---

## 4. 工单与复核

### 4.1 `GET /workbench/tickets`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| TKT-001 | 正常 | 10 个工单 | `total: 10` |
| TKT-002 | 正常 | 按集合筛选 | 只返回该集合 |
| TKT-003 | 正常 | 按状态筛选 | 匹配状态 |
| TKT-004 | 正常 | 分页 page_size=2 | 返回 2 条 + `total: 10` |

### 4.2 `POST /workbench/tickets/:id/decide`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| DEC-001 | 正常 | Approve | `status: "approved"` |
| DEC-002 | 正常 | Reject | `status: "rejected"` |
| DEC-003 | 正常 | Return | `status: "returned"` |
| DEC-004 | 一致 | Approve 后文档入库 | 文档出现于文档库 |
| DEC-005 | 一致 | 决策原因保存 | decision_reason = 传入值 |
| DEC-ERR-001 | 异常 | 重复审批 | 409 ALREADY_DECIDED |
| DEC-ERR-002 | 异常 | decision_request_id 重用 | 409 DECISION_REQUEST_ID_CONFLICT |
| DEC-ERR-003 | 权限 | 操作员 | 403 FORBIDDEN |
| DEC-ERR-004 | 异常 | 工单不存在 | 404 NOT_FOUND |

### 4.3 `POST /workbench/tickets/:id/transfer`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| TRF-001 | 正常 | 转让给有效用户 | 200 + assignee_user_id 更新 |
| TRF-002 | 一致 | 受让人可见 | 工单出现在受让人列表 |
| TRF-ERR-001 | 异常 | 转让给自己 | 400 SELF_TRANSFER |
| TRF-ERR-002 | 异常 | 受让人不存在 | 404 ASSIGNEE_NOT_FOUND |

### 4.4 `GET /workbench/tickets/:id/workspace`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| WSP-001 | 正常 | 完整工单 | 所有字段 + `degraded_parts: []` |
| WSP-002 | 边界 | 无 parse_snapshot | parse_snapshot = null, degraded_parts 含 "parse_snapshot" |
| WSP-003 | 权限 | 操作员 | `can_decide_ticket = false` |
| WSP-004 | 权限 | 管理员 | `can_decide_ticket = true` |
| WSP-ERR-001 | 异常 | 工单不存在 | 404 NOT_FOUND |

### 4.5 `GET /workbench/documents/:id/workspace`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| DOC-WSP-001 | 正常 | 有关联工单 | ticket 字段非空 |
| DOC-WSP-002 | 边界 | 无关联工单 | ticket = null |

---

## 5. 工单评论

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| CMT-001 | 正常 | 创建评论 | 201 + TicketComment |
| CMT-002 | 一致 | 创建后列表包含 | GET 包含新评论 |
| CMT-003 | 正常 | 编辑自己评论 | PATCH 成功 |
| CMT-004 | 正常 | 删除自己评论 | 204 |
| CMT-ERR-001 | 权限 | 编辑他人评论 | 403 FORBIDDEN |
| CMT-ERR-002 | 异常 | 空内容 | 400 INVALID_INPUT |
| CMT-ERR-003 | 异常 | 工单不存在 | 404 NOT_FOUND |

---

## 6. 文档库与生命周期

### 6.1 `GET /workbench/documents`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| DOC-LST-001 | 正常 | 50 个文档 | `total: 50` |
| DOC-LST-002 | 正常 | 按状态筛选 archived | 只返回 archived |
| DOC-LST-003 | 正常 | 按复核状态筛选 | 匹配关联工单状态 |
| DOC-LST-004 | 边界 | 300 个文档 | `total: 300` 但 items ≤ 200 |
| DOC-LST-005 | 正常 | 倒序 | 最新的在前 |

### 6.2 生命周期

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| LC-001 | 正常 | Archive | `new_state: "archived"` |
| LC-002 | 一致 | Archive 后文档库 | 状态 = archived |
| LC-003 | 一致 | Archive 后检索 | 检索结果不包含该文档 |
| LC-004 | 正常 | Retract | `new_state: "retracted"` |
| LC-005 | 正常 | Reindex | `job_id` 非空 |
| LC-006 | 正常 | 批量 Archive | `succeeded: 2, failed: 0` |
| LC-007 | 边界 | 批量部分失败 | `succeeded: 1, failed: 1`, 失败项有 error_message |
| LC-ERR-001 | 异常 | 重复归档 | 409 ALREADY_ARCHIVED |
| LC-ERR-002 | 权限 | 操作员 | 403 FORBIDDEN |

### 6.3 `POST /workbench/documents/:id/share`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| SHR-001 | 正常 | 生成分享链接 | 200 + `share_url` 合法 URL |
| SHR-002 | 正常 | 7 天过期 | expires_at = 7 天后 |
| SHR-ERR-001 | 异常 | 文档不存在 | 404 NOT_FOUND |

---

## 7. 检索验证

### 7.1 `POST /workbench/retrieve`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| RET-001 | 正常 | 标准检索 | 200 + evidence_items 非空 |
| RET-002 | 正常 | Token 预算约束 | `token_budget_used ≤ budget` |
| RET-003 | 边界 | 空结果 | 200 + `evidence_items: []` |
| RET-004 | 正常 | 检索耗时 | `latency_ms > 0` |
| RET-005 | 正常 | debug=basic | 含 score |
| RET-006 | 正常 | debug=full | 含 why_selected |
| RET-ERR-001 | 异常 | 无 collection_id | 400 MISSING_COLLECTION |
| RET-ERR-002 | 异常 | 无 profile | 400 MISSING_RETRIEVAL_PROFILE |
| RET-ERR-003 | 异常 | 空查询 | 400 EMPTY_QUERY |
| RET-ERR-004 | 异常 | 检索服务离线 | 503 RETRIEVAL_SERVICE_UNAVAILABLE |

### 7.2 `GET /workbench/query-runs`

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| QRY-001 | 正常 | 5 次检索历史 | `total: 5`, 最新在前 |

---

## 8. 通知

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| NTF-001 | 正常 | 3 条未读 | `unread_count: 3` |
| NTF-002 | 正常 | 标记已读 1 条 | unread_count 减 1 |
| NTF-003 | 正常 | 全部标记已读 | unread_count = 0 |
| NTF-004 | 边界 | 空 | `items: [], total: 0` |

---

## 9. 系统管理

### 9.1 检索/解析配置 CRUD

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| RP-001 | 正常 | 创建 draft | 201 + `state: "draft"` |
| RP-002 | 正常 | 发布 draft | `state: "published"` |
| RP-003 | 正常 | 克隆已发布 | 新配置 state = "draft" |
| RP-004 | 权限 | 操作员创建 | 403 FORBIDDEN |

### 9.2 API 密钥

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| AK-001 | 正常 | 创建返回完整密钥 | `full_key` 非空 |
| AK-002 | 正常 | 吊销 | `state: "revoked"` |
| AK-003 | 正常 | 用量统计 | `total_requests > 0`, `daily_stats` 非空 |

### 9.3 审计日志

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| AL-001 | 正常 | 筛选 approve 类型 | 只返回 approve |
| AL-002 | 正常 | 日期范围 | 只返回范围内 |
| AL-003 | 正常 | 分页 page_size=10 | 最多 10 条 |
| AL-004 | 正常 | CSV 导出 | download_url |
| AL-005 | 正常 | Excel 导出 | download_url |

### 9.4 仪表盘

| # | 类型 | 场景 | 预期 |
|---|------|------|------|
| DASH-001 | 正常 | 有数据 | 4 个统计非 0 |
| DASH-002 | 边界 | 全新系统 | 4 个统计 = 0 |

---

## 10. 跨 API 数据一致性

| # | 场景 | 操作步骤 | 预期 |
|---|------|---------|------|
| CONS-001 | 上传→工单 | 上传 PDF → 等待解析 | tasks 状态 = reviewing, tickets 出现新工单 |
| CONS-002 | 审批→入库 | Approve 工单 | documents 出现该文档, status = approved |
| CONS-003 | 驳回不入库 | Reject 工单 | documents 不出现该文档 |
| CONS-004 | 归档→检索 | Archive → 检索 | 检索结果不包含该文档 |
| CONS-005 | 取消→无工单 | Cancel 任务 | tickets 无新工单 |
| SYNC-001 | 集合选择同步 | 选择集合 → 上传 | 上传接口 collection_id 正确 |
| SYNC-002 | 审批后队列 | Approve → 查队列 | 工单不再 pending |
| SYNC-003 | 审批后文档库 | Approve → 查文档库 | 文档出现在列表 |

---

## 11. 并发与性能

### 11.1 并发

| # | 场景 | 操作 | 预期 |
|---|------|------|------|
| CONC-001 | 并发上传 | 5 个同时 | 成功 3 个, 其他排队/429 |
| CONC-002 | 并发审批 | 2 个同时 Approve | 1 成功, 1 得到 409 ALREADY_DECIDED |
| CONC-003 | 并发创建集合 | 10 个同时 | 全部成功且 ID 唯一 |

### 11.2 性能基线

| 端点 | 负载 | P50 | P95 | P99 |
|------|------|-----|-----|-----|
| `workspace` 聚合 | 100 QPS | < 1s | < 3s | < 5s |
| `retrieve` | 200 QPS | < 500ms | < 2s | < 5s |
| `tickets` 列表 | 300 QPS | < 200ms | < 500ms | < 1s |
| `documents` 列表 | 300 QPS | < 200ms | < 500ms | < 1s |
| `health/all` | 500 QPS | < 100ms | < 300ms | < 1s |
| `collections` 列表 | 500 QPS | < 100ms | < 200ms | < 500ms |
