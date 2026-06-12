import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockPush = vi.fn();
const mockOnOpenChange = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    listDocuments: vi.fn().mockResolvedValue({ items: [] }),
    listTickets: vi.fn().mockResolvedValue({ items: [] }),
    listCollections: vi.fn().mockResolvedValue({ items: [] }),
  },
}));

import { CommandPalette } from "./command-palette";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("CommandPalette - 受控模式", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("SHE-017: open=false 时不渲染", () => {
    const Wrapper = createWrapper();
    const { container } = render(
      <CommandPalette open={false} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    expect(container.innerHTML).toBe("");
  });

  it("SHE-017: open=true 时渲染搜索面板", async () => {
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索文档、工单、集合或页面...")).toBeInTheDocument();
    });
  });

  it("SHE-017: 点击遮罩层调用 onOpenChange(false)", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("dialog"));
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it("SHE-017: 关闭按钮调用 onOpenChange(false)", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByLabelText("关闭搜索")).toBeInTheDocument();
    });
    await user.click(screen.getByLabelText("关闭搜索"));
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });
});

describe("CommandPalette - 搜索结果", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("SHE-015: 空查询时显示 7 个静态页面", async () => {
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByText("批量入库")).toBeInTheDocument();
    });
    expect(screen.getByText("人工复核")).toBeInTheDocument();
    expect(screen.getByText("文档库")).toBeInTheDocument();
    expect(screen.getByText("检索验证")).toBeInTheDocument();
    expect(screen.getByText("知识库集合")).toBeInTheDocument();
    expect(screen.getByText("回收站")).toBeInTheDocument();
    expect(screen.getByText("帮助中心")).toBeInTheDocument();
  });

  it("SHE-016: 键盘 Enter 跳转到选中项", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索文档、工单、集合或页面...")).toBeInTheDocument();
    });
    const input = screen.getByRole("searchbox");
    await user.type(input, "{Enter}");
    expect(mockPush).toHaveBeenCalled();
  });

  it("SHE-016: 键盘 ArrowDown/ArrowUp 切换高亮选项", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索文档、工单、集合或页面...")).toBeInTheDocument();
    });
    const input = screen.getByRole("searchbox");
    const getSelected = () =>
      screen.getAllByRole("option").findIndex((o) => o.getAttribute("aria-selected") === "true");
    const firstSelected = getSelected();
    await user.keyboard("{ArrowDown}");
    expect(getSelected()).not.toBe(firstSelected);
  });

  it("SHE-016: Escape 关闭面板", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索文档、工单、集合或页面...")).toBeInTheDocument();
    });
    await user.keyboard("{Escape}");
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it("SHE-038: 输入带查询时页面列表仍显示（不隐藏）", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索文档、工单、集合或页面...")).toBeInTheDocument();
    });
    const input = screen.getByRole("searchbox");
    await user.type(input, "文");
    await waitFor(() => {
      expect(screen.getByText("批量入库")).toBeInTheDocument();
    });
  });

  it("SHE-039: 可清空搜索重新看到默认页面列表", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索文档、工单、集合或页面...")).toBeInTheDocument();
    });
    const input = screen.getByRole("searchbox");
    await user.type(input, "不存在的关键词");
    expect(input).toHaveValue("不存在的关键词");
    await user.clear(input);
    await waitFor(() => {
      expect(screen.getByText("批量入库")).toBeInTheDocument();
    });
  });
});

describe("CommandPalette - 无障碍", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("SHE-017: 遮罩层有 role='dialog' 和 aria-label", async () => {
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveAttribute("aria-modal", "true");
      expect(dialog).toHaveAttribute("aria-label", "全局搜索");
    });
  });

  it("SHE-017: 搜索输入框有 role='searchbox' 和 aria-label", async () => {
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      const searchbox = screen.getByRole("searchbox");
      expect(searchbox).toHaveAttribute("aria-label", "搜索关键词");
    });
  });

  it("SHE-017: 关闭按钮有 aria-label", async () => {
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getByLabelText("关闭搜索")).toBeInTheDocument();
    });
  });

  it("SHE-017: 结果列表有 role='listbox' 和 aria-label", async () => {
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      const listbox = screen.getByRole("listbox");
      expect(listbox).toHaveAttribute("aria-label", "搜索结果");
    });
  });

  it("SHE-017: 每个结果项有 role='option' 和 aria-selected", async () => {
    const Wrapper = createWrapper();
    render(
      <CommandPalette open={true} onOpenChange={mockOnOpenChange} />,
      { wrapper: Wrapper }
    );
    await waitFor(() => {
      expect(screen.getAllByRole("option").length).toBeGreaterThan(0);
    });
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");
  });
});

describe("CommandPalette - 非受控模式", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("SHE-017: 无 props 时可独立工作（初始关闭）", () => {
    const Wrapper = createWrapper();
    const { container } = render(<CommandPalette />, { wrapper: Wrapper });
    expect(container.innerHTML).toBe("");
  });

  it("SHE-014: 不受控模式下 Cmd+K 可打开面板", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<CommandPalette />, { wrapper: Wrapper });

    await user.keyboard("{Meta>}k{/Meta}");

    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索文档、工单、集合或页面...")).toBeInTheDocument();
    });
  });

  it("SHE-014: 不受控模式下 Ctrl+K 可打开面板", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<CommandPalette />, { wrapper: Wrapper });

    await user.keyboard("{Control>}k{/Control}");

    await waitFor(() => {
      expect(screen.getByPlaceholderText("搜索文档、工单、集合或页面...")).toBeInTheDocument();
    });
  });
});

describe("CommandPalette - 移动端", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("SHE-041: 移动端弹窗内容区有响应式宽度类", async () => {
    const Wrapper = createWrapper();
    render(<CommandPalette open={true} onOpenChange={mockOnOpenChange} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const innerWrapper = document.querySelector(".mx-auto");
    expect(innerWrapper?.className).toMatch(/max-w/);
  });
});
