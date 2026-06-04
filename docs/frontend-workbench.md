# Frontend Workbench

**Status:** MVP Complete (2026-06)  
**Location:** `apps/web/`  
**Framework:** Next.js 16 App Router

---

## 1. 概述

`apps/web` 是唯一的前端入口，同时承载文档工作台和管理控制面功能。

它不是问答机器人，不提供答案生成。核心能力：

- 批量文件上传（collection + access-scope 控制）
- Agent 审核队列与人工审批
- 审核详情（chunk 预览、ParseSnapshot、决策操作）
- 工作台聚合（ticket + task + agent-review + chunk-edits + source-file）
- 文档库（已发布文档列表与详情）
- 检索验证（canonical wire fields，仅调 workbench-api）
- 集合管理
- 后端健康监控

---

## 2. 技术栈

| 层级 | 技术 |
|---|---|
| Framework | Next.js 16.2.6 (App Router) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 |
| Components | shadcn/ui (18 个组件) |
| Server State | TanStack Query v5 |
| Client State | Zustand v5 + persist |
| Animation | Framer Motion |
| E2E Testing | Playwright |
| Package Manager | npm（严禁 pnpm）|

---

## 3. 页面结构

```
apps/web/src/app/
  page.tsx              首页，重定向至 /upload
  upload/page.tsx       批量上传（拖拽，collection + scope 必填）
  review/page.tsx       Agent 审核队列
  review/[taskId]/      审核详情 + 决策（APPROVE/REJECT/RETURN）
  workbench/[ticketId]/ 工作台详情（Workspace 聚合视图）
  documents/[docId]/    文档详情 + Post-publish chunk 编辑
  retrieval/page.tsx    检索验证（canonical fields）
  collections/page.tsx  集合列表 + 创建
  settings/page.tsx     Auth token + access scope 配置
```

**注意**：架构文档早期版本规划了独立的 `apps/admin-console/` 和 `apps/workbench-ui/`，实际未拆分，全部功能集中在 `apps/web`。

---

## 4. 后端集成

### 4.1 API 路由代理

`next.config.ts` 中配置 rewrite 规则：

| 前端路径 | 目标服务 | 认证 |
|---|---|---|
| `/api/admin/*` | admin | Bearer JWT |
| `/api/workbench/*` | workbench-api | Bearer JWT |
| `/api/access/*` | access | X-API-Key |
| `/api/retrieval/*` | retrieval | 无 |

### 4.2 API Client

`src/lib/api/client.ts` 提供 `fetch` 的 typed wrapper：

| Client | 基础地址 | 认证 | 用途 |
|--------|---------|------|------|
| `adminApi` | `/api/admin` | Bearer JWT | 集合管理、健康检查、认证 |
| `workbenchApi` | `/api/workbench` | Bearer JWT | 上传、任务、工单、快照、检索代理 |
| `accessApi` | `/api/access` | X-API-Key | 检索（备用直连路径） |
| `retrievalApi` | `/api/retrieval` | 无 | 检索健康检查（debug） |

- admin/workbench 注入 `Authorization: Bearer <token>`
- access 注入 `X-API-Key: <key>`
- HTTP 501 抛出 `BackendGapError` —— UI 显示 `<BackendGap>` 组件，不崩溃、不静默失败
- 其他 HTTP 错误抛出 `ApiClientError`

### 4.3 Backend Gap 模式

后端未实现时（HTTP 501），UI 显式展示 `<BackendGap>` 卡片，让运维人员看到缺口。这是系统纪律，不可改为模拟成功或静默失败。

### 4.4 核心架构原则

- **前端永不直连下游服务**：检索、文档管理、chunk 编辑全部通过 `workbench-api` 代理
- **列表页读 SQL projection**：`/review` 和 `/documents` 只查询 workbench SQL projection，不做实时 fan-out
- **详情页 workspace 聚合**：`/workbench/[ticketId]` 由 workbench-api 并发聚合多个下游视图

---

## 5. 状态管理

### 5.1 Server State（TanStack Query）

- Collections list、Tickets list、Ticket detail、Workspace detail
- Agent review artifact、Parse snapshot + chunks
- Upload tasks、Backend health（每 30s 轮询）
- Documents list、Document detail（projection 查询）

### 5.2 Client State（Zustand，持久化到 localStorage）

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

---

## 6. 认证模型

**Demo/operator 模式** —— 无 OAuth 登录流。用户在 Settings 粘贴凭证：

- JWT token → `Authorization: Bearer`（admin / workbench）
- API key → `X-API-Key`（access）

生产环境应替换为真实 IdP（Keycloak、Auth0 等）和 JWKS endpoint。

---

## 7. 测试

### E2E（Playwright）

`e2e/workbench.spec.ts`：

- 导航、集合、设置、上传、审核、检索页面
- 设计为后端离线时也能通过（验证骨架、空状态、静态文本）
- 全页面截图用于视觉回归

```bash
cd apps/web
npm run build
npx playwright test
```

### Build 验证

- TypeScript check: pass
- Static prerender: 8 routes
- No eslint or type errors

---

## 8. Canonical Wire Compliance

检索页面只使用 canonical fields：

| Canonical | Deprecated |
|---|---|
| `query` | `query_text` |
| `token_budget` | `max_context_tokens` |
| `evidence_items` | `result_chunks` |
| `doc_id` | `final_doc_id` |
| `evidence_id` | `chunk_id` |
| `content` | `display_text` |

UI 和 API client types 中不出现 deprecated fields。

---

## 9. Chunk 编辑双模式

| 模式 | 路由 | API | 状态 |
|------|------|-----|------|
| **Pre-publish** | `/review/[taskId]` | `POST /workbench/parse-snapshots/{id}/chunk-edits` → draft → submit | Draft / Submitted |
| **Post-publish** | `/documents/[docId]` | `PATCH /workbench/chunks/{evidence_id}` | Direct revision |

两种模式均通过 workbench-api 转发至 indexing service，前端不直接写入 OpenSearch/Qdrant。

---

## 10. 详细设计

见 `apps/web/web.md`。
