# apps/web 前端工作台设计

## 1. 定位

`apps/web` 是 **Enterprise KnowledgeBase 平台的唯一前端入口**，同时承载**文档处理工作台**与**管理控制面**功能。

核心原则：

- **不是问答机器人** — 不提供大模型答案生成
- **治理型知识入库与检索验证工作台** — 关注文档生命周期治理与检索上下文质量验证
- **前端永不直连下游服务** — 所有业务数据通过 `workbench-api` 代理
- **后端缺口可见** — HTTP 501 时前端显式展示 `<BackendGap>`，不静默失败

判定规则：

| 维度 | apps/web | 后端服务 |
|------|----------|----------|
| 职责 | UI 渲染、用户交互、状态管理、向后端代理发起请求 | 业务逻辑、数据持久化、索引、检索 |
| 数据真相 | 消费后端投影和视图 | 拥有各域事实源 |
| 认证 | 持有 JWT / API Key，注入请求头 | 验签、查 registry、做权限判断 |

## 2. 三方入口边界

平台最终态有三个入口，但前端合并在单一应用中：

| 入口 | 面向用户 | 核心场景 | 对应后端 |
|------|---------|---------|---------|
| `access` REST/MCP | 外部应用/AI Agent | 检索知识 | `services/access` |
| `apps/web` | 文档处理人员/业务人员/审批人员/管理员 | 上传、审批、检索验证、集合管理、配置管理 | `services/workbench-api` + `services/admin` |

注意：虽然早期架构规划了独立的 `apps/admin-console/` 和 `apps/workbench-ui/`，实际未拆分，全部功能集中在 `apps/web`。

## 3. 技术栈

- **Next.js 16.2.6** (App Router, 静态预渲染)
- **React 19.2.4 + TypeScript 5** (零 `unknown` 类型策略)
- **Tailwind CSS v4**
- **shadcn/ui** (Alert, Avatar, Badge, Button, Card, Dialog, Dropdown, Input, Label, Progress, ScrollArea, Select, Separator, Skeleton, Table, Tabs, Textarea, Tooltip)
- **TanStack Query v5** 服务端状态管理
- **Zustand v5** + persist 中间件客户端状态
- **Framer Motion** 页面过渡与动画
- **Playwright** 真实点击 E2E 测试
- **react-pdf-highlighter** PDF 文本高亮与定位
- **npm** 包管理器（注意：不使用 pnpm，避免混合包管理器状态）

## 4. 架构护栏

### 4.1 前端不拥有业务真相

- `apps/web` 只消费后端提供的投影、视图和聚合结果
- 不本地维护业务数据真相（如 ticket 状态、文档生命周期）
- 所有会改变下游事实的操作必须通过后端 API 代理

### 4.2 后端缺口处理（Backend Gap）

当后端 API 返回 HTTP 501 或未实现时：

- API 客户端抛出 `BackendGapError`
- 页面捕获此错误并渲染 `<BackendGap>` 组件
- 明确展示缺失的端点 —— **绝不静默失败或模拟成功**

这是系统纪律，不可改为模拟成功或静默失败。

### 4.3 标准线字段（Canonical Wire）

检索侧统一使用标准线字段，UI 和 API client types 中不出现 deprecated fields：

| Canonical | Deprecated |
|-----------|-----------|
| `query` | `query_text` |
| `token_budget` | `max_context_tokens` |
| `evidence_items` | `result_chunks` |
| `doc_id` | `final_doc_id` |
| `evidence_id` | `chunk_id` |
| `content` | `display_text` |

### 4.4 认证模型

演示/操作员认证模式：

- 用户在 Settings 中粘贴 JWT token 和 API Key
- 无 OAuth 登录流
- Token 通过 Zustand 持久化到 `localStorage`
- 生产部署应替换为真实身份提供商（Keycloak、Auth0 等）

注意：`localStorage` 在不同浏览器间不共享。切换到外部浏览器时需重新配置 token，或重启 `npm run dev` 读取 `.env.local` 中的 demo token。

## 5. 页面结构

```
src/app/
  page.tsx              # 首页，重定向至 /upload
  layout.tsx            # Root layout（Geist 字体、Providers、AppShell、ErrorBoundary）
  globals.css           # 全局样式
  upload/
    page.tsx            # 批量文件上传 — 拖拽上传、集合/权限范围校验、两阶段上传
  review/
    page.tsx            # 人工复核队列 — 代理拦截待人工审批的文档列表
    [taskId]/
      page.tsx          # 复核详情 — 原文预览、Chunk 草稿编辑、AgentReview 发现、决策
  workbench/
    [ticketId]/
      page.tsx          # 工作台详情 — 与 review/[taskId] 共享 TicketDetailPage 组件
  documents/
    [docId]/
      page.tsx          # 文档详情 — 原文预览 + 发布后 chunk 直接编辑（post-publish 模式）
  retrieval/
    page.tsx            # 检索验证 — 标准查询 + Token 预算、证据片段带评分展示
  collections/
    page.tsx            # 知识库集合管理 — 创建、列表
  settings/
    page.tsx            # 演示认证令牌 (JWT/API 密钥) 和权限范围编辑器
```

| 路由 | 功能 | 对应后端 |
|------|------|---------|
| `/upload` | 批量文件上传 | `workbench-api` |
| `/review` | 人工复核队列 | `workbench-api` |
| `/review/[taskId]` | 复核详情 + Pre-publish chunk 编辑 | `workbench-api` |
| `/workbench/[ticketId]` | 工作台详情 + Workspace 聚合 | `workbench-api` |
| `/documents/[docId]` | 文档详情 + Post-publish chunk 编辑 | `workbench-api` |
| `/retrieval` | 检索验证（仅调 workbench-api） | `workbench-api` |
| `/collections` | 知识库集合管理 | `admin` |
| `/settings` | 认证令牌与权限范围配置 | `admin` + `workbench-api` |

## 6. 后端集成

### 6.1 API 路由代理

`next.config.ts` 中配置了 rewrite 规则，将 `/api/*` 路径代理到后端服务：

| 前端路径 | 目标服务 | 实际后端路径 |
|---------|---------|------------|
| `/api/admin/health` | admin | `/health` |
| `/api/admin/:path*` | admin | `/admin/:path*` |
| `/api/workbench/:path*` | workbench-api | `/workbench/:path*` |
| `/api/access/:path*` | access | `/:path*` |
| `/api/retrieval/:path*` | retrieval | `/:path*` |

### 6.2 API Client

`src/lib/api/client.ts` 提供 typed fetch wrapper：

| Client | 基础地址 | 认证方式 | 用途 |
|--------|---------|---------|------|
| `adminApi` | `NEXT_PUBLIC_ADMIN_API_BASE_URL` / `/api/admin` | Bearer JWT | 集合管理、用户认证、健康检查 |
| `workbenchApi` | `NEXT_PUBLIC_WORKBENCH_API_BASE_URL` / `/api/workbench` | Bearer JWT | 上传、任务、工单、快照、检索代理 |
| `accessApi` | `NEXT_PUBLIC_ACCESS_API_BASE_URL` / `/api/access` | X-API-Key | 检索（备用直连路径） |
| `retrievalApi` | `NEXT_PUBLIC_RETRIEVAL_API_BASE_URL` / `/api/retrieval` | 无 | 检索健康检查（debug） |

### 6.3 核心架构原则

- **前端永不直连下游服务**：检索、文档管理、chunk 编辑全部通过 `workbench-api` 代理
- **列表页读 SQL projection**：`/review` 和 `/documents` 只查询 workbench SQL projection，不做实时 fan-out
- **详情页 workspace 聚合**：`/workbench/[ticketId]` 由 workbench-api 并发聚合多个下游视图

### 6.4 文件上传架构

两阶段闭环：

1. **元数据阶段**: `POST /workbench/uploads` — 创建上传会话（集合 ID、文件名、MIME 类型、大小、`access_scope_json`）
2. **字节阶段**: `POST /workbench/uploads/{upload_id}/content` — 发送实际文件字节（multipart/form-data）

字节阶段会再次随 multipart 发送 `access_scope_json`，workbench-api 将 `scope_type=internal/external` 映射为 document-service 的 `visibility=INTERNAL/EXTERNAL`。

### 6.5 检索代理

`/retrieval` 页面**只调 `workbench-api`**：

```
POST /workbench/retrieve
```

workbench-api 验证集合权限后，使用服务端 credentials 调用 access service，前端不接触 X-API-Key。

### 6.6 Chunk 编辑双模式

| 模式 | 路由 | API | 状态 |
|------|------|-----|------|
| **Pre-publish** | `/review/[taskId]` (Drafts tab) | `POST /workbench/parse-snapshots/{id}/chunk-edits` → draft → submit | Draft / Submitted |
| **Post-publish** | `/documents/[docId]` | `PATCH /workbench/chunks/{evidence_id}` | Direct revision |

两种模式均通过 workbench-api 转发至 indexing service，workbench **不直接写入** OpenSearch/Qdrant。

## 7. 状态管理

### 7.1 服务端状态（TanStack Query）

- Collections list、Tickets list、Ticket detail
- Agent review artifact、Parse snapshot + chunks
- Upload tasks、Backend health（每 30s 轮询）
- Documents list（projection 查询）

### 7.2 客户端状态（Zustand + persist → localStorage）

```ts
interface AppState {
  currentCollectionId: string | null;
  accessScope: {
    scope_type: "internal" | "external";
    department?: string;
    role?: string;
    user?: string;
    group?: string;
    agent_type_id?: string;
    api_key?: string;
    customer?: string;
    app?: string;
  } | null;
  demoToken: string | null;
  demoApiKey: string | null;
}
```

### 7.3 后端健康

应用 shell 顶部栏每 30 秒轮询 admin 和 workbench-api 的 `/health` 端点。

## 8. 目录结构

```
apps/web/
├── src/
│   ├── app/                          # Next.js App Router
│   │   ├── page.tsx                  # 重定向至 /upload
│   │   ├── layout.tsx                # Root layout
│   │   ├── upload/
│   │   │   └── page.tsx              # 批量上传页面
│   │   ├── review/
│   │   │   ├── page.tsx              # 复核队列
│   │   │   └── [taskId]/
│   │   │       └── page.tsx          # 复核详情
│   │   ├── workbench/
│   │   │   └── [ticketId]/
│   │   │       └── page.tsx          # 工作台详情
│   │   ├── documents/
│   │   │   └── [docId]/
│   │   │       └── page.tsx          # 文档详情
│   │   ├── retrieval/
│   │   │   └── page.tsx              # 检索验证
│   │   ├── collections/
│   │   │   └── page.tsx              # 集合管理
│   │   └── settings/
│   │       └── page.tsx              # 设置
│   ├── features/workbench/           # Workbench 业务模块
│   │   ├── types/                    # 严格 TypeScript 类型
│   │   │   ├── chunk.ts              # ChunkView, ChunkEditData, ChunkEditItem
│   │   │   ├── finding.ts            # Finding, FindingSeverity, AgentReviewResponse
│   │   │   └── document.ts           # DocumentProjectionItem
│   │   ├── components/
│   │   │   ├── chunk-editor/         # ChunkEditorWorkbench + ChunkEditModal
│   │   │   ├── agent-review/         # AgentReviewPanel + FindingCard
│   │   │   └── document-viewer/      # 文档预览组件
│   │   └── pages/
│   │       └── ticket-detail.tsx     # 共享的 TicketDetailPage 组件
│   ├── components/
│   │   ├── ui/                       # shadcn/ui 组件（18 个）
│   │   ├── layout/
│   │   │   └── app-shell.tsx         # 侧边栏 + 顶部栏导航
│   │   ├── document-workbench/
│   │   │   └── document-viewer.tsx   # 原文预览（PDF/HTML/Text/图片）
│   │   ├── backend-gap.tsx           # 后端缺口展示组件
│   │   ├── empty-state.tsx           # 空状态组件
│   │   ├── error-boundary.tsx        # 全局错误边界
│   │   └── providers.tsx             # TanStack Query + 其他 Providers
│   ├── mocks/                        # MSW v2 Mock Handlers（测试真理源）
│   │   ├── handlers.ts               # workbenchApi 全端点 factory 函数（正常/空/边界三种响应模式）
│   │   └── server.ts                 # MSW Node server 导出
│   └── lib/
│       ├── api/
│       │   ├── client.ts             # API 客户端（adminApi, workbenchApi, accessApi, retrievalApi）
│       │   ├── types.ts              # 共享 API 类型（零 unknown，canonical wire）
│       │   └── errors.ts             # BackendGapError, ApiClientError
│       ├── store.ts                  # Zustand store + persist
│       ├── status.ts                 # 状态格式化工具
│       └── utils.ts                  # 通用工具函数
├── e2e/
│   ├── workbench.spec.ts             # Playwright E2E 测试（18 个测试用例）
│   └── screenshots/                  # 视觉回归截图
├── public/                           # 静态资源
├── next.config.ts                    # Next.js 配置（含 rewrite 代理规则）
├── package.json                      # npm 依赖（注意：不使用 pnpm）
└── README.md                         # 开发者指南
```

## 9. 环境变量

```bash
# API 端点（必需）
NEXT_PUBLIC_ADMIN_API_URL=http://localhost:18084
NEXT_PUBLIC_WORKBENCH_API_URL=http://localhost:18083

# 可选：预填充演示凭证
NEXT_PUBLIC_DEMO_JWT_TOKEN=eyJ...
NEXT_PUBLIC_DEMO_API_KEY=demo-key
```

## 10. 测试

### 单元/集成测试基础设施（MSW v2）

`src/mocks/handlers.ts` 是**所有测试的契约层真理源**，覆盖 `workbenchApi` 全部 36 个端点：

- **健康检查**: `health`, `healthAll`
- **认证**: `me`
- **集合**: `listCollections`, `createCollection`
- **检索配置**: `listRetrievalProfiles`
- **上传**: `createUpload`, `uploadFileContent`, `listUploads`, `getUpload`
- **任务**: `listTasks`, `getTask`
- **工单**: `listTickets`, `getTicket`, `decideTicket`
- **Agent 审核**: `getAgentReview`
- **Chunk**: `getChunk`, `patchChunk`
- **解析快照**: `getParseSnapshot`, `getParseSnapshotChunks`, `listChunkEdits`
- **文档**: `listDocuments`, `getDocument`, `getDocumentWorkspace`
- **生命周期**: `archiveDocument`, `retractDocument`, `reindexDocument`
- **批量操作**: `batchArchiveDocuments`, `batchRetractDocuments`, `batchReindexDocuments`
- **源文件预览**: `getSourceFilePreview`, `getSourceFilePreviewBlob`
- **快照源文件**: `getParseSnapshotSourceBlob`
- **工作空间**: `getWorkspaceDetail`
- **检索**: `retrieve`

每个端点暴露三种 factory 函数：

| 模式 | 用途 | 特征 |
|------|------|------|
| `buildXxxResponse(overrides?)` | 正常数据 | 完整字段，符合 `types.ts` 定义，支持 `Partial` 覆盖 |
| `buildXxxEmptyResponse()` | 空数据 | `[]` 数组、`null` 值、空对象 |
| `buildXxxBoundaryResponse()` | 边界数据 | `>500` 字符超长字符串、`Unicode`（CJK + emoji）、嵌套深度 `>3` 层对象 |

**使用方式**：

```ts
import { server } from "@/mocks/server";
import { buildListTicketsEmptyResponse } from "@/mocks/handlers";

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// 测试中按需覆盖响应
server.use(
  http.get("*/api/workbench/tickets", () =>
    HttpResponse.json(buildListTicketsEmptyResponse())
  )
);
```

**注意**: `getSourceFilePreviewContentUrl` 仅为 URL 拼接工具函数，不发起 HTTP 请求，因此 mocks 层不为其提供独立 handler（blob 内容由 `getSourceFilePreviewBlob` handler 覆盖）。

### Vitest 单元/组件测试

`vitest` + `jsdom` + `@testing-library/react` 构成单元与组件测试层，与 MSW v2 互补：

- **纯逻辑测试**（无 DOM，最快）：`src/lib/*.test.ts`
- **组件测试**（有 DOM，需设计 mock）：`src/components/**/*.test.tsx`

**配置**（`vitest.config.ts`）：

```ts
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/tests/setup.ts"],
    globals: true,
    include: ["src/**/*.test.{ts,tsx}", "src/**/*.spec.{ts,tsx}"],
  },
});
```

**覆盖矩阵**：

| 模块 | 用例数 | 覆盖要点 |
|------|--------|----------|
| `lib/store.test.ts` | 13 | `currentCollectionId` / `accessScope` / `demoToken` / `demoApiKey` 的 set/get、null 清空、多次 set 覆盖、persist `partialize`（验证 localStorage 中不存 setter 函数） |
| `lib/api/errors.test.ts` | 19 | `ApiClientError` / `BackendGapError` 构造、`isBackendGap` / `isApiError` 类型守卫（正确类型返回 true、普通 Error / null / undefined / 对象返回 false）、`getErrorMessage`（Error / 子类 / 字符串 / 普通对象含 message/error/detail / null / undefined） |
| `lib/status.test.ts` | 26 | 4 个格式化函数 × 5 种输入（已知状态、未知字符串、null、undefined、空串） |
| `lib/utils.test.ts` | 7 | `cn` 冲突 class 覆盖、条件 class、无参数、重复去重 |
| `components/ui/badge.test.tsx` | 9 | 5 个 variant（secondary / destructive / success / warning / outline）、custom className、children 渲染 |
| `components/ui/card.test.tsx` | 7 | 默认渲染、`interactive` prop、`size=sm`、CardHeader + CardContent + CardFooter 组合 |
| `components/empty-state.test.tsx` | 6 | 纯 title、title+description、title+description+action、action 渲染为 button / link |
| `components/backend-gap.test.tsx` | 7 | feature 渲染、endpoint 渲染（含空串和特殊字符）、完整 Alert 组合 |
| `components/ui/alert.test.tsx` | 7 | 默认 variant、destructive variant、AlertTitle + AlertDescription 组合、含图标场景 |

**测试红线**（不可违反）：

- 不得修改 `src/` 下任何源代码
- 不得修改 `src/mocks/` 下任何文件
- 禁止 `vi.mock()` 被测试的模块自身（允许 mock 外部依赖如 `framer-motion`、`next/navigation`）
- 禁止 `.skip`、`.todo`、`.only`
- 禁止 mock 后不写断言（每个 `test` 至少一个 `expect`）

**运行**：

```bash
# 运行全部测试
npx vitest run

# watch 模式
npx vitest
```

### E2E (Playwright)

`e2e/workbench.spec.ts` 包含 18 个测试用例：

- 导航测试（首页重定向、侧边栏导航）
- 集合页面（列表、选择器）
- 设置与权限范围（认证 tab、权限 tab）
- 批量上传（缺少集合警告、拖拽区域、文件选择）
- 复核详情（页面导航）
- 复核队列（页面加载）
- 检索验证（标准字段、按钮存在）
- 视觉截图（upload、collections、review、retrieval、settings）

测试设计为后端离线时也能通过（验证加载状态、空状态和骨架屏）。

```bash
# 运行所有 E2E 测试
npx playwright test

# UI 模式运行
npx playwright test --ui

# 生成 HTML 报告
npx playwright show-report
```

### Build 验证

- TypeScript check: pass
- Static prerender: 8 routes
- No eslint or type errors

## 11. 与 workbench-api 的关系

```
apps/web
  -> /api/workbench/*  -> workbench-api (Bearer JWT)
     -> 上传、复核、任务、文档、检索代理
  -> /api/admin/*     -> admin (Bearer JWT)
     -> 集合管理、认证、健康检查
```

- 前端不直接调用 document-service、indexing、retrieval、access
- 所有业务数据请求通过 workbench-api 代理
- workbench-api 返回的统一错误码（`DOWNSTREAM_UNAVAILABLE`、`OP_TIMEOUT`、`CONFLICT`）由前端 `ApiClientError` 捕获

## 12. 与 services/admin 的关系

```
admin-console  ->  apps/web (/collections, /settings)  ->  admin  ->  管理全局配置
```

- `/collections` 页面调 admin `/admin/collections` 管理集合
- `/settings` 页面配置 JWT token 和 API Key
- 早期规划中 admin 功能应通过 workbench-api 代理，当前仍为直连（待迁移）

## 13. Agent 实施约束

### 13.1 包管理器约束

`apps/web` 使用 **npm** 作为唯一包管理器。禁止：

- 在 `apps/web` 目录内运行 `pnpm` 命令
- 引入 `pnpm-lock.yaml` 或 `pnpm-workspace.yaml`
- 混合 npm/pnpm 依赖布局

违反此约束会导致 Next.js/Turbopack 编译不稳定甚至 OOM（参见 `docs/incident-log.md`）。

### 13.2 TypeScript 约束

- 零 `unknown` 类型策略
- API 返回类型必须使用泛型参数明确指定
- `features/workbench/types/` 中的类型定义必须与后端契约一致

### 13.3 API 调用约束

- 所有业务请求必须通过 `workbenchApi` 或 `adminApi` client
- 禁止在前端直接构造对 document-service、indexing、retrieval、access 的请求
- HTTP 501 必须抛 `BackendGapError`，由 `<BackendGap>` 组件展示

### 13.4 状态管理约束

- 服务端状态用 TanStack Query（缓存、轮询、重试）
- 客户端状态用 Zustand + persist
- 不将业务数据真相持久化到 localStorage（只持久化配置类状态）

## 14. 实现记录

### 14.1 已完成的交付

- ✅ Next.js 16 + React 19 + TypeScript 5 迁移完成
- ✅ App Router 8 个路由页面
- ✅ shadcn/ui 18 个组件集成
- ✅ TanStack Query + Zustand 状态管理
- ✅ API Client（adminApi、workbenchApi、accessApi、retrievalApi）
- ✅ BackendGap 错误处理模式
- ✅ 文件上传两阶段闭环
- ✅ Chunk 编辑双模式（pre-publish / post-publish）
- ✅ 检索验证页面（canonical wire）
- ✅ Playwright E2E 18/18 PASS
- ✅ Framer Motion 页面过渡动画
- ✅ ErrorBoundary 全局错误捕获
- ✅ MSW v2 Mock Handlers（`src/mocks/handlers.ts` + `server.ts`）— 36 端点全覆盖，三种响应模式

### 14.2 待补齐

- OAuth/IdP SSO 集成（当前为演示 token 模式）
- admin 功能通过 workbench-api 代理（当前部分直连 admin）
- 文档库列表页（`/documents` 独立列表页）
- 更完整的文档预览（PDF 高亮、多格式支持）
