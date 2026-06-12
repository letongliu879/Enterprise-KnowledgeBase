---
name: spec-to-test
description: Convert acceptance/specification documents into comprehensive test suites (vitest + @testing-library/react)
---

# spec-to-test — 验收文档 → 测试套件

将验收文档（PRD、验收规范、Checklist）系统性地转换为高质量 Vitest 测试套件。编码了完整的测试设计方法论，确保每一条验收条件都是可执行、可追溯、可验证的。

## When to use

- 用户说 "根据验收文档写测试"
- 需要为新功能生成测试套件
- 用户给出了验收 checkpoints（`[B]` 标记、编号规则等）
- 需要在 3-Agent 工作流中扮演 Agent A（Test Author）
- 需要对现有测试进行补充或审计

## Principles

### 1. 逐点映射，双向追溯

```
验收文档                          测试用例
SHE-033: 无凭证 → "SHE-033: 无 JWT 无 API Key 时 isAuthenticated 为 false"
SHE-004: 面包屑 → "SHE-004: /upload → 首页 > 批量入库"
```

- 每个测试用例名以验收点编号开头
- 验收文档没写的不测，验收文档写了但模糊的拆成多个具体用例
- 在测试文件顶部注释注明覆盖的验收点范围

### 2. 三层测试结构

| 层 | 验收文档对应部分 | 作用 |
|---|---|---|
| **Happy Path** | 主流程、正常输入 | 验证核心功能按预期工作 |
| **Boundary** | 边界值、极限情况 | 验证系统在边缘条件下的行为 |
| **Exception** | 错误处理、空状态、后门 | 验证系统在异常输入/状态下的降级 |

### 3. 状态空间穷举

- 识别组件/模块的**独立状态变量**
- 写出所有组合（或关键组合）
- 每个组合至少一个用例

例如 `useAuthGuard` 有 JWT/API Key 两个独立变量 → 4 种状态全部覆盖。

### 4. 先写断言「应该怎样」，不看实现

- 从验收文档推导期望行为
- 跑测试暴露实际行为 vs 期望行为的差异
- **这是发现 bug 的关键步骤**——如果先看实现再写测试，会无意识地适配实现而非验收文档

### 5. 目录对齐

```
hooks/          → renderHook + store state 注入
components/     → DOM 渲染，screen.getByText/role
features/*/     → 已有测试文件追加新 describe block
pages/          → Page Object 测试
```

任何人打开测试文件，目录路径已暗示测试策略。

### 6. 不做什么

- **不 mock 不需要的东西** — 只测当前模块的逻辑，不测依赖方
- **不测框架行为** — 不测 React Router `<Link>` 跳转、不测 zustand 内部
- **不测 UI 像素** — 颜色、大小、间距交给 visual regression 工具
- **不测框架边界** — 不测 React 的渲染机制

## Project-specific patterns

### React hooks

```ts
// 必须用 renderHook
import { renderHook } from "@testing-library/react";
const { result } = renderHook(() => useMyHook());
expect(result.current.value).toBe(expected);
```

### Zustand store state

```ts
import { useAppStore } from "@/lib/store";

beforeEach(() => {
  useAppStore.setState({ key: null });
});
```

### localStorage mock

如果导入的模块在 evaluate 时引用 `window.localStorage`，mock 必须在 `vi.hoisted()` 中：

```ts
vi.hoisted(() => {
  const store: Record<string, string> = {};
  Object.defineProperty(window, "localStorage", {
    value: { getItem, setItem, removeItem },
    writable: true, configurable: true,
  });
});
import { useAppStore } from "@/lib/store";
```

### Component tests

- `render(<Component />)`
- `screen.getByRole()`, `screen.getByText()`, `screen.getByLabelText()`
- a11y: `aria-label`, `role`, keyboard nav via `userEvent.tab()`
- `<BackendGap>` on 501/404 per project convention

## 3-Agent workflow

当在以下工作流中扮演 Agent A（Test Author）时：

### Input
- 验收文档（`.md`）中的验收点清单
- 已知的 baseline 规则（如 `00-全局可用性基线.md`）
- 项目约定的目录结构和测试框架配置

### Output
- **只输出测试文件**（`.test.ts` / `.test.tsx`）
- 不修改实现代码
- 不 mock 未在验收文档中指定的后门

### Self-check
- 每个验收点至少一个正向用例
- 边界条件有独立用例
- 异常路径有覆盖
- 测试文件名与实现文件对齐
- `npx vitest run <path>` 能通过语法/导入检查（但不要求全部通过 —— 实现可能尚未完成）

## Few-shot examples

### Example 1: Hook — 状态空间穷举

**验收文档摘录：**
```
SHE-033: 认证守卫
- 无 JWT 无 API Key → isAuthenticated=false, tokenMissing=true, message="引导文案"
- 3 段 JWT → isAuthenticated=true
- 非 3 段 → hasJwtToken=false
- 有 API Key → isAuthenticated=true, hasApiKey=true
- 两者都有 → isAuthenticated=true，message=null
```

**测试代码：**
```ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";

// localStorage mock before module evaluation
vi.hoisted(() => {
  const store: Record<string, string> = {};
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => { store[key] = value; },
      removeItem: (key: string) => { delete store[key]; },
    },
    writable: true, configurable: true,
  });
});

import { useAuthGuard } from "./use-auth-guard";
import { useAppStore } from "@/lib/store";

describe("useAuthGuard", () => {
  beforeEach(() => {
    useAppStore.setState({ demoToken: null, demoApiKey: null });
  });

  // ── Happy Path ──
  it("SHE-033: 无 JWT 无 API Key 时 isAuthenticated 为 false", () => {
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.tokenMissing).toBe(true);
  });

  it("3 段 JWT 时 isAuthenticated 为 true", () => {
    useAppStore.setState({ demoToken: "header.payload.sig" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.hasJwtToken).toBe(true);
  });

  it("API Key 存在时 isAuthenticated 为 true", () => {
    useAppStore.setState({ demoApiKey: "ak_test_123" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.hasApiKey).toBe(true);
  });

  // ── State space: JWT + API Key 组合 ──
  it("JWT 和 API Key 同时存在时 isAuthenticated 为 true", () => {
    useAppStore.setState({ demoToken: "h.p.s", demoApiKey: "key-123" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.hasJwtToken).toBe(true);
    expect(result.current.hasApiKey).toBe(true);
  });

  // ── Boundary ──
  it("非 3 段字符串不被视为有效 JWT", () => {
    useAppStore.setState({ demoToken: "invalid-token" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.hasJwtToken).toBe(false);
  });

  // ── Exception: 消息文案 ──
  it("SHE-033: 无凭证时 message 为引导文案", () => {
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.message).toBe("请先配置 JWT 令牌或 API 密钥");
  });

  it("有 API Key 无 JWT 时提示缺少 JWT", () => {
    useAppStore.setState({ demoApiKey: "ak_xxx" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.message).toBe("缺少 JWT 令牌，部分功能可能受限");
  });

  it("完全认证时 message 为 null", () => {
    useAppStore.setState({ demoToken: "h.p.s", demoApiKey: "ak_xxx" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.message).toBeNull();
  });
});
```

---

### Example 2: Hook — 时间相关测试

**验收文档摘录：**
```
SHE-034: Loading Timeout
- isLoading=false → timedOut=false
- isLoading=true 且在 timeoutMs 内完成 → timedOut=false
- isLoading=true 超过 timeoutMs → timedOut=true
- reset() 清除 timedOut 状态
- 自定义 timeoutMs 生效
```

**测试代码：**
```ts
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLoadingTimeout } from "./use-loading-timeout";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.restoreAllTimers());

describe("useLoadingTimeout", () => {
  // ── Happy Path ──
  it("isLoading=false 时 timedOut 为 false", () => {
    const { result } = renderHook(() => useLoadingTimeout(false));
    expect(result.current.timedOut).toBe(false);
  });

  it("isLoading=true 且在 timeoutMs 内完成时不触发 timedOut", () => {
    const { result, rerender } = renderHook(
      ({ isLoading }) => useLoadingTimeout(isLoading),
      { initialProps: { isLoading: true } }
    );
    act(() => { vi.advanceTimersByTime(2000); });
    rerender({ isLoading: false });
    expect(result.current.timedOut).toBe(false);
  });

  // ── Boundary: 超时 ──
  it("isLoading=true 超过 timeoutMs 后 timedOut 为 true", () => {
    const { result } = renderHook(() => useLoadingTimeout(true, 3000));
    act(() => { vi.advanceTimersByTime(2999); });
    expect(result.current.timedOut).toBe(false);
    act(() => { vi.advanceTimersByTime(1); });
    expect(result.current.timedOut).toBe(true);
  });

  // ── Exception: reset ──
  it("reset() 清除 timedOut 状态", () => {
    const { result } = renderHook(() => useLoadingTimeout(true, 100));
    act(() => { vi.advanceTimersByTime(200); });
    expect(result.current.timedOut).toBe(true);
    act(() => { result.current.reset(); });
    expect(result.current.timedOut).toBe(false);
  });

  // ── Custom timeout ──
  it("自定义 timeoutMs 生效", () => {
    const { result } = renderHook(() => useLoadingTimeout(true, 5000));
    act(() => { vi.advanceTimersByTime(4000); });
    expect(result.current.timedOut).toBe(false);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(result.current.timedOut).toBe(true);
  });
});
```

---

### Example 3: Component — 静态路由 + 动态段识别

**验收文档摘录：**
```
SHE-004: 面包屑导航
- /upload → 首页 > 批量入库
- /documents → 首页 > 文档库
- /documents/:uuid → 首页 > 文档库 > 文档 详情
- /review/:hex20 → 首页 > 人工复核 > 工单 详情
- /collections/:numeric → 首页 > 集合 > 集合 详情
- 未知段 → 原文显示
- 根路径 → null
- 最后一段非链接（span），中间段为链接
```

**测试代码：**
```ts
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Breadcrumb } from "./breadcrumb";
import { MemoryRouter } from "react-router-dom";

// 辅助：用 MemoryRouter 设置当前路径
function renderAt(pathname: string) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <Breadcrumb />
    </MemoryRouter>
  );
}

describe("Breadcrumb - 已知路由标签", () => {
  it("SHE-004: /upload → 首页 > 批量入库", () => {
    renderAt("/upload");
    expect(screen.getByText("批量入库")).toBeInTheDocument();
    expect(screen.getByText("首页")).toBeInTheDocument();
  });

  it("/documents → 显示'文档库'", () => {
    renderAt("/documents");
    expect(screen.getByText("文档库")).toBeInTheDocument();
  });

  it("首页带有 Home 图标和正确 href", () => {
    renderAt("/upload");
    expect(screen.getByRole("link", { name: /首页/i })).toHaveAttribute("href", "/");
  });
});

describe("Breadcrumb - 动态段识别", () => {
  it("UUID 段显示父段前缀'文档 详情'", () => {
    renderAt("/documents/550e8400-e29b-41d4-a716-446655440000");
    expect(screen.getByText("文档 详情")).toBeInTheDocument();
  });

  it("20 位以上 hex 段显示为'工单 详情'", () => {
    renderAt("/review/a1b2c3d4e5f6a7b8c9d0e1f2");
    expect(screen.getByText("工单 详情")).toBeInTheDocument();
  });

  it("纯数字 6 位以上段显示动态前缀'上传 详情'", () => {
    renderAt("/upload/1234567");
    expect(screen.getByText("上传 详情")).toBeInTheDocument();
  });
});

describe("Breadcrumb - 边界与路径", () => {
  it("根路径返回 null", () => {
    const { container } = renderAt("/");
    expect(container.innerHTML).toBe("");
  });

  it("最后一段非链接（span），中间段为链接", () => {
    renderAt("/documents/abc-123");
    const links = screen.getAllByRole("link");
    expect(links.length).toBe(2);  // 首页 + 文档库
    const spans = screen.getAllByText("abc-123");
    expect(spans[0].tagName).toBe("SPAN");  // 最后一段不是链接
  });

  it("Breadcrumb 带有 aria-label", () => {
    renderAt("/documents");
    expect(screen.getByLabelText("面包屑导航")).toBeInTheDocument();
  });
});
```

---

### Example 4: Component — 受控模式 + 键盘导航 + a11y

**验收文档摘录：**
```
SHE-010: 命令面板
- open={true} 时渲染面板
- open={false} 时不渲染
- 搜索过滤列表项
- 上下箭头导航，Enter 选择
- Escape 关闭
- aria-activedescendant 指向当前项
```

**测试代码：**
```ts
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommandPalette } from "./command-palette";

describe("CommandPalette - 受控模式", () => {
  it("open=true 时渲染面板", () => {
    render(<CommandPalette open={true} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("open=false 时不渲染", () => {
    const { container } = render(<CommandPalette open={false} onClose={vi.fn()} />);
    expect(container.innerHTML).toBe("");
  });
});

describe("CommandPalette - 搜索过滤", () => {
  it("输入查询过滤列表", async () => {
    render(<CommandPalette open={true} onClose={vi.fn()} />);
    const input = screen.getByPlaceholderText("搜索...");
    await userEvent.type(input, "上传");
    expect(screen.getByText("批量入库")).toBeInTheDocument();
    expect(screen.queryByText("文档库")).not.toBeInTheDocument();
  });
});

describe("CommandPalette - a11y & 键盘导航", () => {
  it("上下箭头移动高亮，Enter 选中", async () => {
    const onClose = vi.fn();
    render(<CommandPalette open={true} onClose={onClose} />);
    const input = screen.getByPlaceholderText("搜索...");
    await userEvent.type(input, "上传");
    await userEvent.keyboard("{ArrowDown}");
    await userEvent.keyboard("{Enter}");
    expect(onClose).toHaveBeenCalled();
  });

  it("Escape 关闭面板", async () => {
    const onClose = vi.fn();
    render(<CommandPalette open={true} onClose={onClose} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("aria-activedescendant 指向当前选项", async () => {
    render(<CommandPalette open={true} onClose={vi.fn()} />);
    const input = screen.getByRole("combobox");
    await userEvent.keyboard("{ArrowDown}");
    expect(input.getAttribute("aria-activedescendant")).toBeTruthy();
  });
});
```

---

### Example 5: 往已有测试文件追加

**场景：** `notification-center.test.tsx` 已有初始渲染和面板交互测试，需追加 retry button 和 a11y 测试。

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 在文件底部追加新的 describe block，不修改已有测试
describe("NotificationCenter - 重试机制", () => {
  it("失败通知显示重试按钮", () => {
    render(<NotificationCenter notifications={failedNotifications} />);
    expect(screen.getByRole("button", { name: /重试/i })).toBeInTheDocument();
  });

  it("点击重试调用 onRetry", async () => {
    const onRetry = vi.fn();
    render(
      <NotificationCenter
        notifications={failedNotifications}
        onRetry={onRetry}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /重试/i }));
    expect(onRetry).toHaveBeenCalledWith("notif-1");
  });
});

describe("NotificationCenter - a11y", () => {
  it("通知列表有 role=log", () => {
    render(<NotificationCenter notifications={[/*...*/]} />);
    expect(screen.getByRole("log")).toBeInTheDocument();
  });

  it("每条通知有 aria-live=polite", () => {
    render(<NotificationCenter notifications={[/*...*/]} />);
    const items = screen.getAllByRole("listitem");
    items.forEach(item => {
      expect(item).toHaveAttribute("aria-live", "polite");
    });
  });
});
```
