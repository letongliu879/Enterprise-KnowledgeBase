import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

import HelpPage from "./page";

describe("HelpPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders help page sections", () => {
    render(<HelpPage />);
    expect(screen.getByText("帮助中心")).toBeInTheDocument();
    expect(screen.getByText("快捷键")).toBeInTheDocument();
    expect(screen.getByText("常见问题")).toBeInTheDocument();
  });

  it("filters faqs by search query", async () => {
    const user = userEvent.setup();
    render(<HelpPage />);

    const input = screen.getByPlaceholderText("搜索常见问题、功能...");
    await user.type(input, "回收站");

    await waitFor(() => {
      expect(screen.getByText("删除的文档还能恢复吗？")).toBeInTheDocument();
    });

    expect(screen.queryByText("如何上传文档到知识库？")).not.toBeInTheDocument();
  });
});
