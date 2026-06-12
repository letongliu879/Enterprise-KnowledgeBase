import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TicketTransferDialog } from "./ticket-transfer";

const mockOnTransferred = vi.fn();
const mockOnOpenChange = vi.fn();

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

// Mock the workbenchApi
vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    me: vi.fn().mockResolvedValue({
      user_id: "user-001",
      tenant_id: "tenant-001",
    }),
    transferTicket: vi.fn().mockResolvedValue({ status: "updated" }),
  },
}));

describe("TicketTransferDialog - 工单转让弹窗", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("happy path: 打开弹窗显示标题和审核员列表", async () => {
    const Wrapper = createWrapper();
    render(
      <TicketTransferDialog
        ticketId="ticket-001"
        open={true}
        onOpenChange={mockOnOpenChange}
        onTransferred={mockOnTransferred}
      />,
      { wrapper: Wrapper }
    );

    expect(screen.getByText("转让工单")).toBeInTheDocument();
    expect(screen.getByText("选择审核员")).toBeInTheDocument();
    expect(screen.getByText("转让原因（可选）")).toBeInTheDocument();
  });

  it("边界: 未选择审核员时确认按钮禁用", async () => {
    const Wrapper = createWrapper();
    render(
      <TicketTransferDialog
        ticketId="ticket-001"
        open={true}
        onOpenChange={mockOnOpenChange}
        onTransferred={mockOnTransferred}
      />,
      { wrapper: Wrapper }
    );

    const confirmBtn = screen.getByText("确认转让").closest("button");
    expect(confirmBtn).toBeDisabled();
  });
});
