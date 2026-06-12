# 后端实现完成度 & 验收启动计划

> **目的**：对照 API Contract 检查完成度，规划文档更新、Playwright E2E、Smoke Test、全项目启动验收。

---

## 1. API Contract 实现状态对照表

对照 `docs/superpowers/plans/2026-06-13-backend-api-contract.md` 逐一检查。

### 1.1 认证与元数据

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 1 | `GET /workbench/auth/me` | 用户信息 + roles + collections | `auth/routes.py` — 已实现, display_name 已补齐 | ✅ |
| 2 | `GET /workbench/health` | `{service, status}` | `main.py` line 85 — 已实现 | ✅ |
| 3 | `GET /workbench/health/all` | 5 services aggregated | `health/routes.py` — 已实现 | ✅ |

### 1.2 知识库集合

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 4 | `GET /workbench/collections` | list + tenant_id filter | `collections/routes.py` — 已实现 | ✅ |
| 5 | `POST /workbench/collections` | create | `collections/routes.py` — 已实现 | ✅ |
| 6 | `PATCH /workbench/collections/:id` | update | `collections/routes.py` — Agent 2 新增 | ✅ |
| 7 | `DELETE /workbench/collections/:id` | delete | `collections/routes.py` — Agent 2 新增 | ✅ |
| 8 | `GET /workbench/collections/:id` | detail + stats | `collections/routes.py` — Agent 2 新增 | ✅ |
| 9 | `GET /workbench/collections/:id/documents` | list docs in collection | ❌ **缺失** — frontend 未调用 | ⚠️ P3 |

### 1.3 上传与任务

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 10 | `POST /workbench/uploads` | create upload session | `upload_sessions/routes.py` — 已实现 | ✅ |
| 11 | `GET /workbench/uploads` | list uploads | `upload_sessions/routes.py` — 已实现 | ✅ |
| 12 | `GET /workbench/uploads/:id` | get upload | `upload_sessions/routes.py` — 已实现 | ✅ |
| 13 | `DELETE /workbench/uploads/:id` | delete upload | `upload_sessions/routes.py` — 已实现 | ✅ |
| 14 | `POST /workbench/uploads/:id/content` | upload file content | `upload_sessions/routes.py` — 已实现 | ✅ |
| 15 | `GET /workbench/tasks` | list tasks | `task_projection/routes.py` — 已实现 | ✅ |
| 16 | `GET /workbench/tasks/:id` | get task | `task_projection/routes.py` — 已实现 | ✅ |
| 17 | `POST /workbench/tasks/:id/cancel` | cancel task | `task_projection/routes.py` — Agent 1 新增 | ✅ |
| 18 | `POST /workbench/tasks/:id/recover` | recover stuck task | `task_projection/routes.py` — 已实现 | ✅ |

### 1.4 工单与复核

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 19 | `GET /workbench/tickets` | list tickets | `tickets/routes.py` — 已实现 | ✅ |
| 20 | `GET /workbench/tickets/:id` | get ticket detail | `tickets/routes.py` — 已实现 | ✅ |
| 21 | `POST /workbench/tickets/:id/decide` | approve/reject/return | `tickets/routes.py` — 已实现 | ✅ |
| 22 | `GET /workbench/tickets/:id/agent-review` | agent review findings | `tickets/routes.py` — 已实现 | ✅ |
| 23 | `GET /workbench/tickets/:id/workspace` | workspace detail | `workspace/routes.py` — 已实现 | ✅ |
| 24 | `POST /workbench/tickets/:id/transfer` | transfer ticket | `tickets/transfer_routes.py` — Agent 1 新增 | ✅ |
| 25 | `GET /workbench/tickets/:id/comments` | list comments | `tickets/comments_routes.py` — Agent 1 新增 | ✅ |
| 26 | `POST /workbench/tickets/:id/comments` | create comment | `tickets/comments_routes.py` — Agent 1 新增 | ✅ |
| 27 | `PATCH /workbench/comments/:id` | update comment | `tickets/comments_routes.py` — Agent 1 新增 | ✅ |
| 28 | `DELETE /workbench/comments/:id` | delete comment | `tickets/comments_routes.py` — Agent 1 新增 | ✅ |

### 1.5 Chunk 操作

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 29 | `GET /workbench/parse-snapshots/:id` | get snapshot | `parse_snapshot/routes.py` — 已实现 | ✅ |
| 30 | `GET /workbench/parse-snapshots/:id/chunks` | list chunks | `parse_snapshot/routes.py` — 已实现 | ✅ |
| 31 | `GET /workbench/parse-snapshots/:id/source` | source blob | `parse_snapshot/routes.py` — 已实现 | ✅ |
| 32 | `GET /workbench/chunks/:evidence_id` | get chunk | `chunks/routes.py` — 已实现 | ✅ |
| 33 | `PATCH /workbench/chunks/:evidence_id` | update chunk | `chunks/routes.py` — 已实现 | ✅ |
| 34 | `POST /workbench/parse-snapshots/:id/chunk-edits` | create draft edit | `chunk_edits/routes.py` — 已实现 | ✅ |
| 35 | `GET /workbench/parse-snapshots/:id/chunk-edits` | list draft edits | `chunk_edits/routes.py` — 已实现 | ✅ |
| 36 | `PUT /workbench/chunk-edits/:id` | update draft edit | `chunk_edits/routes.py` — 已实现 | ✅ |
| 37 | `DELETE /workbench/chunk-edits/:id` | delete draft edit | `chunk_edits/routes.py` — 已实现 | ✅ |
| 38 | `POST /workbench/chunk-edits/:id/submit` | submit to indexing | `chunk_edits/routes.py` — 已实现 | ✅ |

### 1.6 文档库与生命周期

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 39 | `GET /workbench/documents` | list documents | `projections/routes.py` — 已实现 | ✅ |
| 40 | `GET /workbench/documents/:id` | get document | `projections/routes.py` — 已实现 | ✅ |
| 41 | `GET /workbench/documents/:id/workspace` | doc workspace | `documents/routes.py` — 已实现 | ✅ |
| 42 | `POST /workbench/documents/:id/archive` | archive | `documents/routes.py` — 已实现 | ✅ |
| 43 | `POST /workbench/documents/:id/retract` | retract | `documents/routes.py` — 已实现 | ✅ |
| 44 | `POST /workbench/documents/:id/reindex` | reindex | `documents/routes.py` — 已实现 | ✅ |
| 45 | `POST /workbench/documents/batch/archive` | batch archive | `documents/routes.py` — 已实现 | ✅ |
| 46 | `POST /workbench/documents/batch/retract` | batch retract | `documents/routes.py` — 已实现 | ✅ |
| 47 | `POST /workbench/documents/batch/reindex` | batch reindex | `documents/routes.py` — 已实现 | ✅ |
| 48 | `POST /workbench/documents/:id/share` | share link | `documents/routes.py` — Agent 2 新增 | ✅ |

### 1.7 源文件预览

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 49 | `GET /workbench/source-files/:id/content` | file metadata | `source_files/routes.py` — 已实现 | ✅ |
| 50 | `GET /workbench/source-files/:id/preview` | preview metadata | `source_files/routes.py` — 已实现 | ✅ |
| 51 | `GET /workbench/source-files/:id/preview/content` | preview binary | `source_files/routes.py` — 已实现 | ✅ |

### 1.8 检索验证

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 52 | `POST /workbench/retrieve` | retrieve | `commands/retrieval.py` — 已实现 | ✅ |
| 53 | `GET /workbench/query-runs` | list history | `commands/retrieval.py` — 已实现 | ✅ |
| 54 | `GET /workbench/query-runs/:id` | get run detail | `commands/retrieval.py` — 已实现 | ✅ |

### 1.9 通知

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 55 | `GET /workbench/notifications` | list | `notifications/routes.py` — Agent 3 新增 | ✅ |
| 56 | `PATCH /workbench/notifications/:id/read` | mark read | `notifications/routes.py` — Agent 3 新增 | ✅ |
| 57 | `POST /workbench/notifications/read-all` | read all | `notifications/routes.py` — Agent 3 新增 | ✅ |
| 58 | `GET /workbench/notifications/unread-count` | unread count | `notifications/routes.py` — Agent 3 新增 | ✅ |

### 1.10 系统管理

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 59 | `GET /workbench/retrieval-profiles` | list | `retrieval_profiles/routes.py` — 已实现 | ✅ |
| 60 | `POST /workbench/retrieval-profiles` | create | `retrieval_profiles/routes.py` — Agent 3 新增 | ✅ |
| 61 | `GET /workbench/retrieval-profiles/:id` | detail | `retrieval_profiles/routes.py` — Agent 3 新增 | ✅ |
| 62 | `PATCH /workbench/retrieval-profiles/:id` | update | `retrieval_profiles/routes.py` — Agent 3 新增 | ✅ |
| 63 | `DELETE /workbench/retrieval-profiles/:id` | delete | `retrieval_profiles/routes.py` — Agent 3 新增 | ✅ |
| 64 | `POST /workbench/retrieval-profiles/:id/publish` | publish | `retrieval_profiles/routes.py` — Agent 3 新增 | ✅ |
| 65 | `POST /workbench/retrieval-profiles/:id/clone` | clone | `retrieval_profiles/routes.py` — Agent 3 新增 | ✅ |
| 66 | `GET /workbench/parser-profiles` | list | `parser_selection/routes.py` — 已实现 | ✅ |
| 67 | `POST /workbench/parser-profiles` | create | `parser_selection/routes.py` — Agent 3 新增 | ✅ |
| 68 | `GET /workbench/parser-profiles/:id` | detail | `parser_selection/routes.py` — Agent 3 新增 | ✅ |
| 69 | `PATCH /workbench/parser-profiles/:id` | update | `parser_selection/routes.py` — Agent 3 新增 | ✅ |
| 70 | `DELETE /workbench/parser-profiles/:id` | delete | `parser_selection/routes.py` — Agent 3 新增 | ✅ |
| 71 | `POST /workbench/parser-profiles/:id/publish` | publish | `parser_selection/routes.py` — Agent 3 新增 | ✅ |
| 72 | `POST /workbench/parser-profiles/:id/clone` | clone | `parser_selection/routes.py` — Agent 3 新增 | ✅ |
| 73 | `GET /workbench/api-keys` | list | `api_keys/routes.py` — Agent 3 新增 | ✅ |
| 74 | `POST /workbench/api-keys` | create | `api_keys/routes.py` — Agent 3 新增 | ✅ |
| 75 | `GET /workbench/api-keys/:id` | detail | `api_keys/routes.py` — Agent 3 新增 | ✅ |
| 76 | `PATCH /workbench/api-keys/:id` | update | `api_keys/routes.py` — Agent 3 新增 | ✅ |
| 77 | `DELETE /workbench/api-keys/:id` | delete | `api_keys/routes.py` — Agent 3 新增 | ✅ |
| 78 | `GET /workbench/api-keys/:id/usage` | usage stats | `api_keys/routes.py` — Agent 3 新增 | ✅ |
| 79 | `GET /workbench/audit-logs` | list | `audit/routes.py` — Agent 3 新增 | ✅ |
| 80 | `POST /workbench/audit-logs/export` | export | `audit/routes.py` — Agent 3 新增 | ✅ |

### 1.11 仪表盘 & 回收站

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 81 | `GET /workbench/dashboard` | dashboard stats | `dashboard/routes.py` — Agent 2 新增 | ✅ |
| 82 | `GET /workbench/trash` | list trash | `trash/routes.py` — Agent 2 新增 | ✅ |
| 83 | `POST /workbench/trash/:id/restore` | restore | `trash/routes.py` — Agent 2 新增 | ✅ |
| 84 | `DELETE /workbench/trash/:id` | permanent delete | `trash/routes.py` — Agent 2 新增 | ✅ |

### 1.12 事件

| # | 端点 | Contract | 实现 | 状态 |
|---|------|----------|------|------|
| 85 | `POST /internal/events/{service}` | event ingestion | `events/__init__.py` — 已实现 | ✅ |

### 1.13 汇总

| 类别 | 总计 | 已实现 | 缺失 |
|------|------|--------|------|
| workbench-api 端点 | 85 | 84 | 1 |
| 下游内部端点 | ~50 (admin/indexing/intake/approval/publishing) | ~48 | 少量 |
| 测试覆盖 (workbench) | 145 tests | 144 pass | 1 pre-existing env fail |

**唯一缺失**: `GET /workbench/collections/:id/documents` — P3, 前端未直接调用, 集合详情页通过 `listDocuments({collection_id})` 绕过。

---

## 2. 文档同步更新

需更新的文档：

| 文档 | 需要修改 | 工作量 |
|------|----------|--------|
| `docs/superpowers/plans/2026-06-13-backend-api-contract.md` | 补充 14 个新端点和错误码 | 小 |
| `docs/superpowers/plans/2026-06-13-backend-test-spec.md` | 补充评论/转让/DELETE/通知等测试用例 | 中 |
| `services/workbench-api/api.md` | 同步补充所有新增端点 | 中 |
| `apps/web/需求.md` | 第 13 章标记状态更新 | 小 |

---

## 3. Playwright E2E 测试编写计划

### 现状
- `apps/web/e2e/workbench.spec.ts` — 18 个 test()（navigation, collections, settings, review）
- `apps/web/e2e/documents.spec.ts` — 2 个 test()
- `apps/web/e2e/review-workspace.spec.ts` — 1 个 test()
- **总计**: 21 tests（已覆盖导航、集合选择、设置、基本复核）
- **配置**: `apps/web/playwright.config.ts` — chromium, 串行, port 3000, 自动启动 `npm run dev`

### 新增 Playwright 测试清单

```typescript
// apps/web/e2e/full-flow.spec.ts — 全链路端到端（新增, ~15 tests）
describe("集合页完整流程", () => {
  test("COL-001: 骨架屏→卡片网格加载")       // 加载状态→数据渲染
  test("COL-005: 选择集合→Toast→Header 同步")  // 集合选择交互
  test("COL-009~015: 创建集合弹窗")             // 创建+校验+列表刷新
  test("COL-017~019: 编辑集合")                 // 编辑弹窗→预填充→保存
  test("集合删除确认弹窗")                       // 删除 dialog
});

describe("上传页完整流程", () => {
  test("E2E-UPL-001: 未选集合禁止上传")          // 拦截+Toast
  test("E2E-UPL-003: 文件状态流转展示")           // 卡片排队→上传中→解析中
  test("上传取消按钮")                            // 取消上传→状态变更
  test("统计面板展示")                            // 5 个指标卡片
});

describe("复核队列完整流程", () => {
  test("E2E-REV-001: 工单列表加载")              // 列表渲染
  test("筛选器(集合/状态)")                       // 下拉筛选
  test("E2E-REV-002: 点击卡片跳转")              // 路由跳转
});

describe("复核详情完整流程", () => {
  test("E2E-RVD-001: 三 Tab 切换")               // Source/Draft/Agent
  test("评论区展示和创建")                         // 评论交互
  test("Decision Cockpit 决策按钮")               // Approve/Reject/Return
});

describe("文档库完整流程", () => {
  test("E2E-DOC-001: 文档列表加载")              // 列表+筛选
  test("文档筛选器(7个)")                         // 搜索/状态/类型等
  test("文档详情页 Tab")                          // Source/Chunks/Agent
});

describe("检索验证完整流程", () => {
  test("E2E-RET-001: 未选集合禁用检索")            // 前置校验
  test("检索结果展示")                             // evidence_items 卡片
  test("检索历史")                                 // query-runs 列表
});

describe("仪表盘", () => {
  test("DASH-001: 首页加载→统计+快捷操作")          // dashboard 渲染
  test("最近工单列表")                              // ticket 跳转
});

describe("通知中心", () => {
  test("NTF-001: 铃铛→未读数→面板打开")             // notification 交互
  test("标记已读/全部已读")                         // 状态变更
});

describe("系统管理页面", () => {
  test("审计日志列表+筛选+导出")                     // audit log 页面
  test("API 密钥CRUD")                              // api key 交互
  test("检索配置管理")                               // profiles 页面
});
```

### 目录结构
```
apps/web/e2e/
├── workbench.spec.ts          # 原有 ~18 tests（保留）
├── documents.spec.ts          # 原有 ~2 tests（保留）
├── review-workspace.spec.ts   # 原有 ~1 test（保留）
├── full-flow.spec.ts          # 新增 ~35 tests（全链路覆盖）
└── admin.spec.ts              # 新增 ~10 tests（系统管理页）
```

### 依赖
- Playwright 需要后端运行（workbench-api + admin + downstream）
- 使用 `webServer` 配置 `start-backend.sh` 启动后端（或用 `reuseExistingServer` 手动启动）

---

## 4. Smoke Test 更新计划

### 现状
- `services/smoke_tests/test_intake_real_chain.py` — 1 test（in-process, 全链路上传→published）
- `services/smoke_tests/test_deployment_smoke.py` — 5 tests（deployment 模式, health + upload + status + projection + stuck）
- **总计**: 6 tests

### 新增 Smoke Tests

| 测试 | 模式 | 说明 |
|------|------|------|
| `test_workbench_endpoints.py::test_all_endpoints_respond` | in-process | 自动注册所有 router，验证每个 endpoint 至少返回正确 HTTP 状态码（204/200/400/401/404 等，取决于是否需要 auth） |
| `test_workbench_endpoints.py::test_cancel_and_ticket_flow` | in-process | 上传→取消→验证无工单生成 |
| `test_workbench_endpoints.py::test_decision_flow` | in-process | 上传→审批→验证文档入库 |
| `test_workbench_endpoints.py::test_comment_and_transfer` | in-process | 创建工单→评论→转让 |
| `test_workbench_endpoints.py::test_collection_crud` | in-process | 集合创建→编辑→删除 |
| `test_workbench_endpoints.py::test_api_key_and_audit_crud` | in-process | API key 创建→吊销→审计日志验证 |

### 文件结构
```
services/smoke_tests/
├── conftest.py                    # 已有（工具函数 + fixtures）
├── test_deployment_smoke.py       # 已有 5 tests
├── test_intake_real_chain.py      # 已有 1 test
├── test_workbench_endpoints.py    # 新增 ~6 tests（in-process, 无外部依赖）
└── api.md                         # 已有（需同步更新）
```

---

## 5. 全项目启动 & 人工验收流程

### 启动顺序

```bash
# 1. 启动后端服务（6 个核心）
cd services/workbench-api && uvicorn workbench_api.main:app --port 18083 --reload
cd services/admin && uvicorn admin_service.main:app --port 18084 --reload
cd services/indexing && uvicorn indexing_service.main:app --port 18080 --reload
# + document-service, ingestion-worker, approval-service

# 2. 启动前端
cd apps/web && npm run dev
# → http://localhost:3000
```

### 人工验收点击流程

按端到端验收文档 `docs/Frontend Acceptance/99-端到端核心流程验收.md`：

| 步骤 | 页面 | 验证点 |
|------|------|--------|
| 1 | `/collections` | 骨架屏→网格加载, 选择集合→Header 同步, 创建→编辑→删除 |
| 2 | `/upload` | 拖拽上传, 文件卡片状态流转, 取消, 统计面板 |
| 3 | `/review` | 工单列表, 筛选器, 点击跳转 |
| 4 | `/review/[taskId]` | 三 Tab 切换, Comment 创建, Decision Approve/Reject/Return |
| 5 | `/documents` | 文档列表, 筛选器, 归档/撤回 |
| 6 | `/documents/[docId]` | Source/Chunks/Agent Tab, 分享链接 |
| 7 | `/retrieval` | 检索, 结果展示, 历史记录 |
| 8 | `/settings` | JWT 配置, 权限范围, API Keys, 审计日志 |
| 9 | 全局 | 通知中心, 命令面板 (Cmd+K), 健康指示灯 |

---

## 6. 执行优先级建议

| 优先级 | 任务 | 预估时间 |
|--------|------|----------|
| P0 | 编写并运行 Playwright E2E ~45 tests（覆盖整套人工验收流程） | 2-3h |
| P0 | 全项目启动 + 人工点击验收 | 1h |
| P1 | 新增 6 个 in-process smoke tests | 1h |
| P1 | 文档同步更新（3 个文档） | 30min |
| P2 | `GET /collections/:id/documents` 端点 | 15min |
