# 企业知识库工作台

Next.js App Router 前端，用于企业知识库治理与检索上下文验证。这是一个**治理型知识入库与检索验证工作台** —— 非问答生成机器人。

## 技术栈

- **Next.js 16** (App Router, 静态预渲染)
- **React 19 + TypeScript** (零 `unknown` 类型策略)
- **Tailwind CSS v4**
- **shadcn/ui** (Button, Card, Badge, Select, Tabs, Dialog, Skeleton, Dropdown 等)
- **TanStack Query v5** 服务端状态管理
- **Zustand** + persist 中间件客户端状态
- **Framer Motion** 页面过渡与动画
- **Playwright** 真实点击 E2E 测试
- **react-pdf-highlighter** PDF 文本高亮与定位

## 页面

| 路由 | 功能 |
|---|---|
| `/upload` | 批量文件上传 — 拖拽上传、集合/权限范围校验、真实文件字节传输 |
| `/review` | 人工复核队列 — 代理拦截待人工审批的文档列表 |
| `/review/[taskId]` | 复核详情 — 原文预览、Chunk 草稿编辑、AgentReview 发现、批准/驳回/退回决策 |
| `/workbench/[ticketId]` | 工作台详情 — 与 `/review/[taskId]` 共享组件，用于已发布文档的 chunk 管理 |
| `/documents` | 文档库 — 已发布文档列表，基于 SQL projection 查询 |
| `/documents/[docId]` | 文档详情 — 原文预览 + 发布后 chunk 直接编辑（post-publish 模式） |
| `/retrieval` | 检索验证 — 标准查询 + Token 预算、证据片段带评分展示（仅调 workbench-api） |
| `/collections` | 知识库集合管理 — 创建、列表、选择用于上传 |
| `/settings` | 演示认证令牌 (JWT/API 密钥) 和权限范围编辑器 |

## 后端集成

前端连接 **2 个后端服务**。业务数据（上传、复核、文档库、检索）**全部通过 `workbench-api` 代理**，浏览器不直接接触下游服务：

| 服务 | 基础地址 | 认证方式 | 用途 |
|---|---|---|---|
| workbench-api | `NEXT_PUBLIC_WORKBENCH_API_URL` | Bearer JWT | 上传、复核、任务、文档库、检索代理（唯一业务 BFF） |
| admin | `NEXT_PUBLIC_ADMIN_API_URL` | Bearer JWT | 集合管理、检索配置（**待迁移**：应通过 workbench-api 代理） |

### 核心架构原则

- **前端永不直连下游服务**：检索、文档管理、chunk 编辑全部通过 `workbench-api` 代理
- **列表页读 SQL projection**：`/review` 和 `/documents` 只查询 workbench SQL projection，不做实时 fan-out
- **详情页 workspace 聚合**：`/workbench/[ticketId]` 由 workbench-api 并发聚合多个下游视图

### 文件上传架构

文件上传采用两阶段闭环：

1. **元数据阶段**: `POST /workbench/uploads` — 创建上传会话（集合 ID、文件名、MIME 类型、大小、`access_scope_json`）
2. **字节阶段**: `POST /workbench/uploads/{upload_id}/content` — 发送实际文件字节（multipart/form-data）

字节阶段会再次随 multipart 发送 `access_scope_json`，workbench-api 将 `scope_type=internal/external` 映射为 document-service 的 `visibility=INTERNAL/EXTERNAL`。随后 workbench-api 将文件字节转发至 document-service `POST /upload`，后者执行：
- 文件落盘与 SHA256 计算
- 重复内容检测
- 创建 source_file 记录
- 恶意软件扫描

如果 document-service 不可用，workbench-api 返回 HTTP 501，前端显示**后端能力缺口**提示。

### 检索代理

`/retrieval` 页面**只调 `workbench-api`**：

```
POST /workbench/retrieve
```

workbench-api 验证集合权限后，使用服务端 credentials 调用 access service，前端不接触 X-API-Key。

### Chunk 编辑双模式

| 模式 | 路由 | API | 状态 |
|---|---|---|---|
| **Pre-publish** | `/review/[taskId]` (Drafts tab) | `POST /workbench/parse-snapshots/{id}/chunk-edits` → draft → `POST /workbench/parse-snapshots/{id}/submit` | Draft / Submitted |
| **Post-publish** | `/documents/[docId]` | `PATCH /workbench/chunks/{evidence_id}` | Direct revision |

两种模式均通过 workbench-api 转发至 indexing service，workbench **不直接写入** OpenSearch/Qdrant。

## 目录结构

```
src/
├── app/                          # Next.js App Router
│   ├── upload/
│   ├── review/
│   │   └── [taskId]/
│   ├── workbench/
│   │   └── [ticketId]/           # 与 review/[taskId] 共享组件
│   ├── documents/
│   │   └── [docId]/
│   ├── retrieval/
│   ├── collections/
│   └── settings/
├── features/workbench/           # Workbench 业务模块
│   ├── types/                    # 严格 TypeScript 类型（零 unknown）
│   │   ├── chunk.ts              # ChunkView, ChunkEditData, ChunkEditItem
│   │   ├── finding.ts            # Finding, FindingSeverity, AgentReviewResponse
│   │   └── document.ts           # DocumentProjectionItem
│   ├── components/
│   │   ├── chunk-editor/         # ChunkEditorWorkbench + ChunkEditModal
│   │   └── agent-review/         # AgentReviewPanel + FindingCard
│   └── pages/
│       └── ticket-detail.tsx     # 共享的 TicketDetailPage 组件
├── components/
│   ├── document-workbench/
│   │   └── document-viewer.tsx   # 原文预览（PDF/HTML/Text/图片）
│   └── layout/
│       └── app-shell.tsx         # 侧边栏 + 顶部栏导航
├── lib/
│   ├── api/
│   │   ├── client.ts             # API 客户端（adminApi, workbenchApi）
│   │   ├── types.ts              # 共享 API 类型
│   │   └── errors.ts             # BackendGapError, ApiClientError
│   └── status.ts                 # 状态格式化工具
```

## 环境变量

```bash
# API 端点（必需）
NEXT_PUBLIC_ADMIN_API_URL=http://localhost:18084
NEXT_PUBLIC_WORKBENCH_API_URL=http://localhost:18083

# 可选：预填充演示凭证
NEXT_PUBLIC_DEMO_JWT_TOKEN=eyJ...
NEXT_PUBLIC_DEMO_API_KEY=demo-key
```

## 本地运行

```bash
npm install
npm run dev
```

`apps/web` uses `npm` as its package manager. Do not run `pnpm` in this directory or add pnpm lock/workspace files.

打开 http://localhost:3000。应用将 `/` 重定向至 `/upload`。

## 构建

```bash
npm run build
```

TypeScript 严格模式启用，零 `unknown` 类型。构建失败时检查：
- `features/workbench/types/` 中的类型定义
- API 客户端返回类型的泛型参数

## 测试

### E2E (Playwright)

测试针对真实开发服务器和真实 UI 运行。即使后端离线也能通过（验证加载状态、空状态和骨架屏）。

```bash
# 运行所有 E2E 测试
npx playwright test

# UI 模式运行
npx playwright test --ui

# 生成 HTML 报告
npx playwright show-report
```

截图保存至 `e2e/screenshots/` 用于视觉验证。

## 设计模式

### 后端缺口处理

当后端 API 返回 HTTP 501 或未实现时，API 客户端抛出 `BackendGapError`。页面捕获此错误并渲染 `<BackendGap>` 组件，明确展示缺失的端点 —— 绝不静默失败或模拟成功。

### 标准线字段

检索侧统一使用标准线字段：
- `query`（而非 `query_text`）
- `token_budget`（而非 `max_context_tokens`）
- `evidence_items`（而非 `result_chunks`）
- `doc_id`, `evidence_id`, `content`

### 认证模型

演示/操作员认证模式：用户在设置中粘贴 JWT 令牌和 API 密钥。无 OAuth 流程。令牌通过 Zustand 持久化到 `localStorage`。生产部署应替换为真实身份提供商。

**注意**：`localStorage` 在不同浏览器间不共享。如果你在 VS Code 内部浏览器中已登录，切换到外部浏览器（Chrome/Edge）时需要**重新配置 token**：

1. 访问 `http://localhost:3000/settings`
2. 在"演示认证令牌"中粘贴 `.env.local` 中的 `NEXT_PUBLIC_DEMO_TOKEN`
3. 刷新页面

或者重启 `npm run dev`，外部浏览器首次访问时会自动读取 `.env.local` 中的 demo token。

### 状态管理

- **服务端状态**: TanStack Query（缓存、轮询、重试）
- **客户端状态**: Zustand (`currentCollectionId`, `accessScope`, `demoToken`, `demoApiKey`)
- **后端健康**: 应用 shell 顶部栏每 30 秒轮询

### 错误边界

全局 `ErrorBoundary` 组件包裹应用，捕获渲染错误并展示用户友好的错误页面（含刷新按钮）。

### Chunk 编辑状态流

```
Pre-publish (review page):
  Draft → Submit → workbench-api → indexing service → 等待审批

Post-publish (documents page):
  Edit → Save → workbench-api → indexing service → 直接 revision
```

两种模式均通过 `ChunkEditModal` 组件实现，通过 `mode: "pre-publish" | "post-publish"` prop 区分 UI 颜色（橙/蓝）和按钮文案（Draft+Submit / Save）。

## 已完成的架构改造

- ✅ **Part A**: workbench-api 作为 BFF + SQL Projection Store + 下游事件适配（65 个后端测试通过）
- ✅ **Part B**: RAGFlow 文档/chunk 工作台能力迁移至 `features/workbench/`
- ✅ **检索代理**: `/retrieval` 不再直连 access service
- ✅ **文档库**: `/documents` 列表页读 SQL projection
- ✅ **Chunk 编辑**: Pre-publish (Draft/Submit) 和 Post-publish (直接 Save) 双模式
