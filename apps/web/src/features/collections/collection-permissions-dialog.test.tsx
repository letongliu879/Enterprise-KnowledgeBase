import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CollectionPermissionsDialog } from "./collection-permissions-dialog";

describe("CollectionPermissionsDialog", () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    collectionId: "col-123",
    tenantId: "tenant-456",
  };

  it("renders when open", () => {
    render(<CollectionPermissionsDialog {...defaultProps} />);
    expect(screen.getByText("集合权限")).toBeInTheDocument();
  });

  it("displays collection info", () => {
    render(<CollectionPermissionsDialog {...defaultProps} />);
    expect(screen.getByText(/col-123/)).toBeInTheDocument();
    expect(screen.getByText(/tenant-456/)).toBeInTheDocument();
  });

  it("calls onClose when close button clicked", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const onClose = vi.fn();
    render(<CollectionPermissionsDialog {...defaultProps} onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: /关闭/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not render when closed", () => {
    const { container } = render(<CollectionPermissionsDialog {...defaultProps} open={false} />);
    expect(container.textContent).not.toContain("集合权限");
  });
});
