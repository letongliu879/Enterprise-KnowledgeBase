import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ApiSnippetDialog } from "./api-snippet-dialog";

describe("ApiSnippetDialog", () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    query: "test query",
    collectionId: "col-123",
    retrievalProfileId: "profile-456",
    tokenBudget: 2000,
  };

  it("renders when open", () => {
    render(<ApiSnippetDialog {...defaultProps} />);
    expect(screen.getByText("API 代码片段")).toBeInTheDocument();
  });

  it("shows cURL snippet by default", () => {
    render(<ApiSnippetDialog {...defaultProps} />);
    expect(screen.getByText(/curl/)).toBeInTheDocument();
    expect(screen.getByText(/collection_id/)).toBeInTheDocument();
    expect(screen.getByText(/col-123/)).toBeInTheDocument();
  });

  it("switches to Python SDK tab", async () => {
    render(<ApiSnippetDialog {...defaultProps} />);
    await userEvent.click(screen.getByRole("tab", { name: /python/i }));
    expect(screen.getByText(/httpx/)).toBeInTheDocument();
    expect(screen.getByText(/col-123/)).toBeInTheDocument();
  });

  it("calls onClose when close button clicked", async () => {
    const onClose = vi.fn();
    render(<ApiSnippetDialog {...defaultProps} onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: /关闭/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows copy success feedback", async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    render(<ApiSnippetDialog {...defaultProps} />);
    await userEvent.click(screen.getByRole("button", { name: /复制/i }));
    expect(screen.getByText(/已复制/)).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    const { container } = render(<ApiSnippetDialog {...defaultProps} open={false} />);
    expect(container.textContent).not.toContain("API 代码片段");
  });
});
