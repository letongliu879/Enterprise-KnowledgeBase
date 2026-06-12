# 前端未完成功能补全实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全企业知识库工作台前端所有未完成功能，均为功能增强类（非核心链路阻塞），按优先级分批交付。

**Architecture:** 每个功能独立开发，遵循现有代码模式（'use client' + Zustand + React Query + Framer Motion + Sonner Toast）。所有改动集中在 `apps/web/src/` 内，不影响后端。

**Tech Stack:** Next.js 16 App Router, React 19, Zustand, TanStack Query v5, Framer Motion, Sonner, Lucide React

---

## 文件结构概览

| 模块 | 现有文件 | 新增/修改文件 |
|------|---------|-------------|
| 工单转让 | `src/features/workbench/pages/ticket-detail.tsx` | 新增转让弹窗组件 + API |
| 上传任务取消 | `src/app/upload/page.tsx` | 修改上传状态管理 + 新增取消按钮 |
| 源文件并排对比 | `src/features/workbench/components/document-viewer/document-viewer.tsx` | 新增并排视图模式 |
| 审核报告导出 | `src/features/workbench/pages/ticket-detail.tsx` | 新增导出按钮 + 导出逻辑 |
| 并发编辑冲突提示 | `src/features/workbench/components/chunk-editor/` | 新增冲突检测 + 提示组件 |
| 工作台差异化 | `src/app/workbench/[ticketId]/page.tsx` | 新增草稿/预发布预览标识 |
| 集合删除 | `src/app/collections/page.tsx` | 新增删除按钮 + 确认弹窗 |
| 集合排序 | `src/app/collections/page.tsx` | 新增排序控件 |
| 集合权限配置 | `src/app/collections/[collectionId]/page.tsx` | 新增权限配置弹窗 |
| 文档批注/评论 | `src/app/documents/[docId]/page.tsx` | 补全已存在的Tab占位 |
| 版本历史对比 | 文档详情侧边栏 | 补全版本对比功能 |
| 全文搜索高亮增强 | `src/features/workbench/components/document-viewer/` | 增强搜索高亮 |
| API代码片段 | `src/app/retrieval/page.tsx` | 新增代码片段展示 |
| 检索参数预设 | `src/app/retrieval/page.tsx` | 新增预设保存/加载 |
| 文档标签系统 | `src/app/documents/page.tsx` | 新增标签管理 |

---

## 批次一：P1 核心增强（预计4个任务，2天）

### Task 1: 工单转让功能

**依赖:** 无

**Files:**
- Create: `src/features/workbench/components/ticket-transfer-dialog.tsx`
- Create: `src/features/workbench/components/ticket-transfer-dialog.test.tsx`
- Modify: `src/features/workbench/pages/ticket-detail.tsx`（右侧边栏插入转让入口）
- Modify: `src/lib/api/client.ts`（新增 transferTicket API 方法）

- [ ] **Step 1: 测试 API 方法**

```bash
# 确认 API 客户端文件位置
ls src/lib/api/client.ts
grep -n "class WorkbenchApi" src/lib/api/client.ts
```

Read `src/lib/api/client.ts` to understand existing API patterns.

- [ ] **Step 2: 写测试 — 转让弹窗组件**

```tsx
// test: ticket-transfer-dialog.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TicketTransferDialog } from "./ticket-transfer-dialog";

describe("TicketTransferDialog", () => {
  it("renders when open", () => {
    render(<TicketTransferDialog open onClose={vi.fn()} ticketId="ticket-123" onTransfer={vi.fn()} />);
    expect(screen.getByText("转让工单")).toBeInTheDocument();
  });

  it("requires assignee input before submit", () => {
    render(<TicketTransferDialog open onClose={vi.fn()} ticketId="ticket-123" onTransfer={vi.fn()} />);
    expect(screen.getByRole("button", { name: /确认转让/i })).toBeDisabled();
  });

  it("calls onTransfer with assignee on submit", async () => {
    const onTransfer = vi.fn();
    render(<TicketTransferDialog open onClose={vi.fn()} ticketId="ticket-123" onTransfer={onTransfer} />);
    await userEvent.type(screen.getByLabelText(/受让人/i), "user-456");
    await userEvent.click(screen.getByRole("button", { name: /确认转让/i }));
    expect(onTransfer).toHaveBeenCalledWith("ticket-123", "user-456");
  });
});
```

- [ ] **Step 3: 运行测试验证失败**

Run: `npx vitest run --reporter=verbose src/features/workbench/components/ticket-transfer-dialog.test.tsx`
Expected: FAIL (component not found)

- [ ] **Step 4: 创建转让弹窗组件**

```tsx
// src/features/workbench/components/ticket-transfer-dialog.tsx
"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface TicketTransferDialogProps {
  open: boolean;
  onClose: () => void;
  ticketId: string;
  onTransfer: (ticketId: string, assignee: string) => Promise<void>;
  isPending?: boolean;
}

export function TicketTransferDialog({ open, onClose, ticketId, onTransfer, isPending }: TicketTransferDialogProps) {
  const [assignee, setAssignee] = useState("");

  const handleSubmit = async () => {
    if (!assignee.trim()) return;
    await onTransfer(ticketId, assignee.trim());
    setAssignee("");
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>转让工单</DialogTitle>
          <DialogDescription>将工单转让给其他用户处理。输入目标用户的ID或邮箱。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="assignee">受让人</Label>
            <Input id="assignee" value={assignee} onChange={(e) => setAssignee(e.target.value)} placeholder="用户ID 或 邮箱" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={!assignee.trim() || isPending}>
            {isPending ? "转让中..." : "确认转让"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 5: 新增 API 方法**

Read `src/lib/api/client.ts` to find `WorkbenchApi` class, then add:
```ts
async transferTicket(ticketId: string, assignee: string): Promise<void> {
  await this.post(`/workbench/tickets/${ticketId}/transfer`, { assignee });
}
```

- [ ] **Step 6: 集成到工单详情页**

Read `src/features/workbench/pages/ticket-detail.tsx` to find the right insertion point, then add:
```tsx
import { TicketTransferDialog } from "../components/ticket-transfer-dialog";

// 在右侧边栏 System & Diagnostics 区域附近加入"转让工单"按钮
{hasPermission && (
  <>
    <Button variant="outline" size="sm" className="w-full" onClick={() => setTransferOpen(true)}>
      <ArrowRightFromLine className="mr-2 h-4 w-4" /> 转让工单
    </Button>
    <TicketTransferDialog
      open={transferOpen}
      onClose={() => setTransferOpen(false)}
      ticketId={ticketId}
      onTransfer={workbenchApi.transferTicket.bind(workbenchApi)}
    />
  </>
)}
```

- [ ] **Step 7: 运行所有测试**

Run: `npx vitest run --reporter=verbose src/features/workbench/components/ticket-transfer-dialog.test.tsx`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/features/workbench/components/ticket-transfer-dialog.tsx src/features/workbench/components/ticket-transfer-dialog.test.tsx src/features/workbench/pages/ticket-detail.tsx src/lib/api/client.ts
git commit -m "feat: add ticket transfer functionality with dialog and API"
```

---

### Task 2: 集合删除功能

**依赖:** 无

**Files:**
- Create: `src/features/collections/delete-collection-dialog.tsx`
- Create: `src/features/collections/delete-collection-dialog.test.tsx`
- Modify: `src/app/collections/page.tsx`（在卡片或操作栏添加删除按钮）
- Modify: `src/lib/api/client.ts`（新增 deleteCollection API）

- [ ] **Step 1: 写测试 — 删除确认弹窗**

```tsx
// test: delete-collection-dialog.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DeleteCollectionDialog } from "./delete-collection-dialog";

describe("DeleteCollectionDialog", () => {
  it("shows warning text when open", () => {
    render(<DeleteCollectionDialog open onClose={vi.fn()} collectionId="col-123" collectionName="Test" onConfirm={vi.fn()} />);
    expect(screen.getByText(/确定要删除集合/i)).toBeInTheDocument();
    expect(screen.getByText(/Test/)).toBeInTheDocument();
  });

  it("requires confirmation text input", () => {
    render(<DeleteCollectionDialog open onClose={vi.fn()} collectionId="col-123" collectionName="Test" onConfirm={vi.fn()} />);
    expect(screen.getByRole("button", { name: /确认删除/i })).toBeDisabled();
  });

  it("calls onConfirm with collectionId", async () => {
    const onConfirm = vi.fn();
    render(<DeleteCollectionDialog open onClose={vi.fn()} collectionId="col-123" collectionName="Test" onConfirm={onConfirm} />);
    await userEvent.type(screen.getByPlaceholderText(/输入集合名称以确认/i), "Test");
    await userEvent.click(screen.getByRole("button", { name: /确认删除/i }));
    expect(onConfirm).toHaveBeenCalledWith("col-123");
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

Run: `npx vitest run --reporter=verbose src/features/collections/delete-collection-dialog.test.tsx`
Expected: FAIL

- [ ] **Step 3: 创建删除确认弹窗组件**

```tsx
// src/features/collections/delete-collection-dialog.tsx
"use client";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface DeleteCollectionDialogProps {
  open: boolean;
  onClose: () => void;
  collectionId: string;
  collectionName: string;
  onConfirm: (collectionId: string) => Promise<void>;
  isPending?: boolean;
}

export function DeleteCollectionDialog({ open, onClose, collectionId, collectionName, onConfirm, isPending }: DeleteCollectionDialogProps) {
  const [confirmText, setConfirmText] = useState("");

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>删除集合</DialogTitle>
          <DialogDescription className="text-destructive">
            此操作不可撤销。集合 &ldquo;{collectionName}&rdquo; 及其所有文档将被永久删除。
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2 py-4">
          <Label htmlFor="confirm">输入 <strong>{collectionName}</strong> 以确认删除</Label>
          <Input id="confirm" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} placeholder="输入集合名称以确认" />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button variant="destructive" disabled={confirmText !== collectionName || isPending} onClick={async () => { await onConfirm(collectionId); setConfirmText(""); onClose(); }}>
            {isPending ? "删除中..." : "确认删除"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: 新增 API 方法**

Read `src/lib/api/client.ts`, add:
```ts
async deleteCollection(collectionId: string): Promise<void> {
  await this.delete(`/collections/${collectionId}`);
}
```

- [ ] **Step 5: 集成到集合页**

Read `src/app/collections/page.tsx`, find card action area, add:
```tsx
import { DeleteCollectionDialog } from "@/features/collections/delete-collection-dialog";

// 在卡片操作中添加删除按钮
<Button variant="ghost" size="sm" className="text-destructive" onClick={() => setDeleteTarget(c)}>
  <Trash2 className="h-4 w-4" />
</Button>

// 页面级别状态
const [deleteTarget, setDeleteTarget] = useState<Collection | null>(null);

// Dialog 组件
{deleteTarget && (
  <DeleteCollectionDialog open onClose={() => setDeleteTarget(null)} collectionId={deleteTarget.id} collectionName={deleteTarget.name} onConfirm={handleDelete} />
)}
```

- [ ] **Step 6: 运行测试**

Run: `npx vitest run --reporter=verbose src/features/collections/delete-collection-dialog.test.tsx`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/features/collections/delete-collection-dialog.tsx src/features/collections/delete-collection-dialog.test.tsx src/app/collections/page.tsx src/lib/api/client.ts
git commit -m "feat: add collection delete with confirmation dialog"
```

---

### Task 3: 集合排序功能

**依赖:** Task 2（涉及同一页面）

**Files:**
- Modify: `src/app/collections/page.tsx`（顶部新增排序控件）
- Modify: `src/components/sort-dropdown.tsx`（若需扩展）或直接用现有 Select

- [ ] **Step 1: 写测试 — 集合排序**

Read `src/app/collections/page.test.tsx` (if exists), or add test to verify sorting works:
```tsx
// 在 page.test.tsx 中补充分组测试  
describe("collections sorting", () => {
  it("sorts by name ascending by default", async () => {
    render(<CollectionsPage />);
    // ... waitFor 后验证顺序
  });
});
```

- [ ] **Step 2: 在集合页添加排序下拉**

在 `src/app/collections/page.tsx` 的 top bar 区域添加：
```tsx
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const [sortBy, setSortBy] = useState<"name" | "createdAt" | "updatedAt">("createdAt");

<Select value={sortBy} onValueChange={setSortBy}>
  <SelectTrigger className="w-[160px]">
    <SelectValue placeholder="排序" />
  </SelectTrigger>
  <SelectContent>
    <SelectItem value="createdAt">创建时间</SelectItem>
    <SelectItem value="name">名称</SelectItem>
    <SelectItem value="updatedAt">更新时间</SelectItem>
  </SelectContent>
</Select>

// 渲染列表前排序
const sortedCollections = [...collections].sort((a, b) => {
  if (sortBy === "name") return a.name.localeCompare(b.name);
  if (sortBy === "createdAt") return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
});
```

- [ ] **Step 3: 运行测试**

Run: `npx vitest run --reporter=verbose src/app/collections/page.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/app/collections/page.tsx
git commit -m "feat: add collection sorting by name/created/updated"
```

---

### Task 4: 上传任务取消功能

**依赖:** 无

**Files:**
- Modify: `src/app/upload/page.tsx`（为每个文件卡片添加取消按钮）
- Modify: `src/lib/api/client.ts`（新增 cancelUpload API）

- [ ] **Step 1: 写测试**

Read `src/app/upload/page.test.tsx` to find existing test structure:
```tsx
it("shows cancel button for queued/uploading files", () => {
  // ...
  expect(screen.getByRole("button", { name: /取消/i })).toBeInTheDocument();
});

it("removes file from list after cancel", async () => {
  // ...
});
```

- [ ] **Step 2: 实现取消功能**

在文件卡片上添加：
```tsx
<Button
  variant="ghost"
  size="sm"
  className="text-destructive"
  onClick={() => handleCancel(file.id)}
  disabled={file.status === "completed"}
>
  <X className="h-4 w-4 mr-1" /> 取消
</Button>
```

```ts
// 逻辑处理
const handleCancel = async (fileId: string) => {
  // 如果正在上传，调用 API 取消
  if (statusMap[fileId] === "uploading") {
    try {
      await workbenchApi.cancelUpload(fileId);
    } catch (e) {
      // API 501 时仅移除本地记录
    }
  }
  // 从列表移除
  setFiles((prev) => prev.filter((f) => f.id !== fileId));
};
```

- [ ] **Step 3: 在 API Client 新增**

```ts
async cancelUpload(fileId: string): Promise<void> {
  await this.post(`/tasks/${fileId}/cancel`);
}
```

- [ ] **Step 4: 运行测试**

Run: `npx vitest run --reporter=verbose src/app/upload/page.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app/upload/page.tsx src/lib/api/client.ts
git commit -m "feat: add upload task cancellation"
```

---

## 批次二：P2 体验增强（预计6个任务，3天）

### Task 5: 源文件 vs 解析结果并排对比

**依赖:** 无

**Files:**
- Modify: `src/features/workbench/components/document-viewer/document-viewer.tsx`（新增对比模式切换）

- [ ] **Step 1: Read existing DocumentViewer code**
- [ ] **Step 2: 添加并排视图模式**

```tsx
// 在 Toolbar 中添加切换按钮
<Toggle
  pressed={viewMode === "split"}
  onPressedChange={(v) => setViewMode(v ? "split" : "single")}
  aria-label="并排对比"
>
  <Columns className="h-4 w-4" />
</Toggle>

// 条件渲染 split/single 模式
{splitMode ? (
  <div className="grid grid-cols-2 gap-2 h-full">
    <div className="overflow-auto border-r">{/* Source */}</div>
    <div className="overflow-auto">{/* Parsed Text */}</div>
  </div>
) : (
  <div className="h-full">{/* Single view */}</div>
)}
```

- [ ] **Step 3: 运行相关测试**
- [ ] **Step 4: Commit**

---

### Task 6: 审核报告导出功能

**依赖:** 无

**Files:**
- Create: `src/features/workbench/utils/export-report.ts`
- Modify: `src/features/workbench/pages/ticket-detail.tsx`（添加导出按钮）

- [ ] **Step 1: 创建导出工具函数**
- [ ] **Step 2: 在工单详情页添加导出按钮**
- [ ] **Step 3: 测试**
- [ ] **Step 4: Commit**

---

### Task 7: 文档批注/评论 Tab 补全

**依赖:** 无

**Files:**
- Modify: `src/app/documents/[docId]/page.tsx`（将占位 Tab 替换为真实组件）
- Create: `src/features/documents/document-annotations.tsx`
- Create: `src/features/documents/document-annotations.test.tsx`

- [ ] **Step 1: Read existing document detail page to find the Tab placeholder**
- [ ] **Step 2: 创建批注组件**
- [ ] **Step 3: 集成到文档详情页 Tab**
- [ ] **Step 4: 测试 + Commit**

---

### Task 8: 集合权限配置弹窗

**依赖:** 无

**Files:**
- Create: `src/features/collections/collection-permissions-dialog.tsx`
- Modify: `src/app/collections/[collectionId]/page.tsx`

- [ ] **Step 1: 创建权限配置组件**
- [ ] **Step 2: 集成到集合详情页**
- [ ] **Step 3: 测试 + Commit**

---

### Task 9: API 代码片段展示（cURL / Python SDK）

**依赖:** 无

**Files:**
- Create: `src/features/retrieval/api-snippet-panel.tsx`
- Modify: `src/app/retrieval/page.tsx`

- [ ] **Step 1: 创建 API 代码片段生成组件**
- [ ] **Step 2: 集成到检索页结果区域**
- [ ] **Step 3: 测试 + Commit**

---

### Task 10: 检索参数预设

**依赖:** 无

**Files:**
- Create: `src/features/retrieval/retrieval-presets.ts`
- Modify: `src/app/retrieval/page.tsx`

- [ ] **Step 1: 创建预设存储逻辑（localStorage）**
- [ ] **Step 2: 添加保存/加载预设 UI**
- [ ] **Step 3: 测试 + Commit**

---

## 批次三：P2/P3 体验增强（可选，4个任务）

### Task 11: 并发编辑冲突提示
### Task 12: 版本历史对比补全
### Task 13: 全文搜索高亮增强
### Task 14: 文档标签系统

---

## 总依赖关系图

```
Task 1 (工单转让)       → 无依赖
Task 2 (集合删除)       → 无依赖
Task 3 (集合排序)       → 依赖 Task 2（同一文件，建议顺序执行）
Task 4 (上传取消)       → 无依赖
Task 5 (并排对比)       → 无依赖
Task 6 (审核导出)       → 无依赖
Task 7 (文档批注)       → 无依赖
Task 8 (权限配置)       → 无依赖
Task 9 (API代码片段)    → 无依赖
Task 10 (检索预设)      → 无依赖
```

所有 Task 1-10 之间**无跨任务依赖**，可并行开发。

---

## 各模块代码文件索引

| 功能 | 关键文件 | 测试文件 |
|------|---------|---------|
| 批量入库 | `src/app/upload/page.tsx` | `src/app/upload/page.test.tsx` |
| 复核队列 | `src/app/review/page.tsx` | `src/app/review/page.test.tsx` |
| 复核详情 | `src/features/workbench/pages/ticket-detail.tsx` | `src/features/workbench/pages/ticket-detail.test.tsx` |
| 文档库 | `src/app/documents/page.tsx` | `src/app/documents/page.test.tsx` |
| 文档详情 | `src/app/documents/[docId]/page.tsx` | `src/app/documents/[docId]/page.test.tsx` |
| 检索验证 | `src/app/retrieval/page.tsx` | `src/app/retrieval/page.test.tsx` |
| 集合 | `src/app/collections/page.tsx` | `src/app/collections/page.test.tsx` |
| 集合详情 | `src/app/collections/[collectionId]/page.tsx` | - |
| API Client | `src/lib/api/client.ts` | - |
| DocumentViewer | `src/features/workbench/components/document-viewer/document-viewer.tsx` | - |
| ChunkEditor | `src/features/workbench/components/chunk-editor/` | `chunk-editor.test.tsx` |
| AgentReview | `src/features/workbench/components/agent-review/` | - |
