# Frontend Workbench

**Status:** MVP Complete (2026-05-29)  
**Location:** `apps/web/`  
**Framework:** Next.js 16 App Router

---

## 1. 概述

`apps/web` 是唯一的前端入口，同时承载文档工作台和管理控制面功能。

它不是问答机器人，不提供答案生成。核心能力：

- 批量文件上传（collection + access-scope 控制）
- Agent 审核队列与人工审批
- 审核详情（chunk 预览、ParseSnapshot、决策操作）
- 检索验证（canonical wire fields）
- 集合管理
- 后端健康监控

---

## 2. 技术栈

| 层级 | 技术 |
|---|---|
| Framework | Next.js 16 (App Router) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 |
| Components | shadcn/ui |
| Server State | TanStack Query v5 |
| Client State | Zustand + persist |
| Animation | Framer Motion |
| E2E Testing | Playwright |

---

## 3. 页面结构

```
apps/web/src/app/
  upload/page.tsx        批量上传（拖拽，collection + scope 必填）
  review/page.tsx        Agent 审核队列
  review/[taskId]/       审核详情 + 决策（APPROVE/REJECT/RETURN）
  retrieval/page.tsx     检索验证（canonical fields）
  collections/page.tsx   集合列表 + 创建
  settings/page.tsx      Auth token + access scope 配置
  documents/             文档浏览
  workbench/             工作台工单
```

**注意**：架构文档早期版本规划了独立的 `apps/admin-console/` 和 `apps/workbench-ui/`，实际未拆分，全部功能集中在 `apps/web`。

---

## 4. 后端集成

| 服务 | 环境变量 | 认证 | 用途 |
|---|---|---|---|
| admin | `NEXT_PUBLIC_ADMIN_API_URL` | Bearer JWT | 集合管理、健康检查 |
| workbench-api | `NEXT_PUBLIC_WORKBENCH_API_URL` | Bearer JWT | 上传、任务、工单、snapshots |
| access | `NEXT_PUBLIC_ACCESS_API_URL` | X-API-Key | 检索代理 |
| retrieval | `NEXT_PUBLIC_RETRIEVAL_API_URL` | 无 (caller-gated) | 直接检索 |

### API Client

`src/lib/api/client.ts` 提供 `fetch` 的 typed wrapper：

- admin/workbench 注入 `Authorization: Bearer <token>`
- access 注入 `X-API-Key: <key>`
- HTTP 501 抛出 `BackendGapError` —— UI 显示 `<BackendGap>` 组件，不崩溃、不静默失败
- 其他 HTTP 错误抛出 `ApiClientError`

### Backend Gap 模式

后端未实现时（HTTP 501），UI 显式展示 `<BackendGap>` 卡片，让运维人员看到缺口。这是系统纪律，不可改为模拟成功或静默失败。

---

## 5. 状态管理

### Server State（TanStack Query）

- Collections list、Tickets list、Ticket detail
- Agent review artifact、Parse snapshot + chunks
- Upload tasks、Backend health（每 30s 轮询）

### Client State（Zustand，持久化到 localStorage）

```ts
interface AppStore {
  currentCollectionId: string | null;
  accessScope: AccessScope | null;
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
- Static prerender: 8 routes（6 static, 1 dynamic `/review/[taskId]`）
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
