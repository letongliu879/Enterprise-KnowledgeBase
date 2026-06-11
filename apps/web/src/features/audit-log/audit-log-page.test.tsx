import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    listAuditLogs: vi.fn(),
    exportAuditLogs: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import { toast } from "sonner";
import { AuditLogPage } from "./audit-log-page";

const api = workbenchApi as any;

// ── Helpers ──────────────────────────────────────────────────────────────

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function mockAuditLogsResponse(overrides?: Record<string, unknown>) {
  return {
    items: [
      {
        log_id: "log-001",
        operator_id: "user-001",
        operator_email: "admin@example.com",
        operation_type: "upload",
        target_type: "document",
        target_id: "doc-001",
        collection_id: "coll-001",
        timestamp: "2024-06-10T12:00:00Z",
        ip_address: "192.168.1.1",
        details: { filename: "document.pdf", mime_type: "application/pdf" },
        before_snapshot: undefined,
        after_snapshot: { doc_id: "doc-001", state: "active" },
      },
      {
        log_id: "log-002",
        operator_id: "user-002",
        operator_email: "reviewer@example.com",
        operation_type: "approve",
        target_type: "ticket",
        target_id: "ticket-001",
        collection_id: "coll-001",
        timestamp: "2024-06-10T13:00:00Z",
        ip_address: "192.168.1.2",
        details: { decision: "APPROVE", reason: "Looks good" },
        before_snapshot: { status: "pending_review" },
        after_snapshot: { status: "approved" },
      },
      {
        log_id: "log-003",
        operator_id: "user-001",
        operator_email: "admin@example.com",
        operation_type: "edit_chunk",
        target_type: "chunk",
        target_id: "ev-001",
        collection_id: "coll-001",
        timestamp: "2024-06-10T14:00:00Z",
        ip_address: "192.168.1.1",
        details: { edit_reason: "Fixed typo" },
        before_snapshot: { content: "Old content" },
        after_snapshot: { content: "Updated content" },
      },
    ],
    total: 3,
    page: 1,
    page_size: 20,
    ...overrides,
  };
}

function mockAuditLogsEmptyResponse() {
  return { items: [], total: 0, page: 1, page_size: 20 };
}

function mockAuditLogsBoundaryResponse() {
  return {
    items: [
      {
        log_id: "log-boundary",
        operator_id: "user-boundary",
        operator_email: "a".repeat(520) + "@example.com",
        operation_type: "reindex",
        target_type: "document",
        target_id: "doc-boundary",
        collection_id: "coll-boundary",
        timestamp: "2099-12-31T23:59:59Z",
        ip_address: "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        details: {
          nested: { a: { b: { c: { d: { e: "deep", data: "x".repeat(5000) } } } } },
        },
        before_snapshot: { old: "x".repeat(5000) },
        after_snapshot: { new: "y".repeat(5000) },
      },
    ],
    total: 999999,
    page: 1,
    page_size: 20,
  };
}

function mockExportAuditLogsResponse(overrides?: Record<string, unknown>) {
  return {
    download_url: "/api/workbench/audit-logs/export/download?file=audit-logs-2024-06-10.csv",
    ...overrides,
  };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("AuditLogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("renders skeleton while audit logs are loading", async () => {
      vi.mocked(api.listAuditLogs).mockImplementation(() => new Promise(() => {}));

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId("audit-log-skeleton")).toBeInTheDocument();
      });
    });
  });

  // ── Success State - Normal Data ────────────────────────────────────────

  describe("Success State - Normal Data", () => {
    it("renders audit log list with operator emails", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      expect(screen.getByText("reviewer@example.com")).toBeInTheDocument();
    });

    it("renders operation type badges for each log entry", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("upload")).toBeInTheDocument();
      });

      expect(screen.getByText("approve")).toBeInTheDocument();
      expect(screen.getByText("edit_chunk")).toBeInTheDocument();
    });

    it("renders target type and target id for each log entry", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("doc-001")).toBeInTheDocument();
      });

      expect(screen.getByText("ticket-001")).toBeInTheDocument();
      expect(screen.getByText("ev-001")).toBeInTheDocument();
    });

    it("renders formatted timestamps for each log entry", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/2024/)).toBeInTheDocument();
      });
    });

    it("renders IP addresses for each log entry", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("192.168.1.1")).toBeInTheDocument();
      });

      expect(screen.getByText("192.168.1.2")).toBeInTheDocument();
    });

    it("renders correct number of log rows", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        const rows = screen.getAllByTestId("audit-log-row");
        expect(rows.length).toBe(3);
      });
    });
  });

  // ── Filter ─────────────────────────────────────────────────────────────

  describe("Filter", () => {
    it("selecting operation type triggers API refresh with operation_type param", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce(mockAuditLogsResponse() as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          items: [mockAuditLogsResponse().items[0]],
          total: 1,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const operationTypeSelect = screen.getByLabelText(/操作类型/i);
      await user.selectOptions(operationTypeSelect, "upload");

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(2);
      });

      expect(api.listAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({ operation_type: "upload" })
      );
    });

    it("selecting time range triggers API refresh with from_date and to_date params", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce(mockAuditLogsResponse() as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          items: [mockAuditLogsResponse().items[0]],
          total: 1,
        } as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const fromDateInput = screen.getByLabelText(/开始时间/i);
      const toDateInput = screen.getByLabelText(/结束时间/i);
      // Use input event which React controlled inputs respond to reliably
      fireEvent.input(fromDateInput, { target: { value: "2024-06-01" } });
      fireEvent.input(toDateInput, { target: { value: "2024-06-30" } });

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenLastCalledWith(
          expect.objectContaining({
            from_date: "2024-06-01",
            to_date: "2024-06-30",
          })
        );
      });
    });

    it("entering document ID triggers API refresh with target_id param", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce(mockAuditLogsResponse() as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          items: [mockAuditLogsResponse().items[0]],
          total: 1,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const docIdInput = screen.getByLabelText(/文档 ID/i);
      await user.type(docIdInput, "doc-001");

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(2);
      });

      expect(api.listAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({ target_id: "doc-001" })
      );
    });

    it("selecting collection triggers API refresh with collection_id param", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce(mockAuditLogsResponse() as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          items: [mockAuditLogsResponse().items[0]],
          total: 1,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const collectionSelect = screen.getByLabelText(/集合/i);
      await user.selectOptions(collectionSelect, "coll-001");

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(2);
      });

      expect(api.listAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({ collection_id: "coll-001" })
      );
    });

    it("entering operator ID triggers API refresh with operator_id param", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce(mockAuditLogsResponse() as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          items: [mockAuditLogsResponse().items[0]],
          total: 1,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const operatorInput = screen.getByLabelText(/操作人/i);
      await user.type(operatorInput, "user-001");

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(2);
      });

      expect(api.listAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({ operator_id: "user-001" })
      );
    });

    it("combining multiple filters triggers API with all params", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce(mockAuditLogsResponse() as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          items: [],
          total: 0,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const operationTypeSelect = screen.getByLabelText(/操作类型/i);
      await user.selectOptions(operationTypeSelect, "upload");

      const fromDateInput = screen.getByLabelText(/开始时间/i);
      fireEvent.input(fromDateInput, { target: { value: "2024-06-01" } });

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenLastCalledWith(
          expect.objectContaining({
            operation_type: "upload",
            from_date: "2024-06-01",
          })
        );
      });
    });
  });

  // ── Pagination ─────────────────────────────────────────────────────────

  describe("Pagination", () => {
    it("clicking next page triggers API with incremented page param", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 1,
          page_size: 20,
        } as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 2,
          page_size: 20,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const nextBtn = screen.getByRole("button", { name: /下一页/i });
      await user.click(nextBtn);

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(2);
      });

      expect(api.listAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2 })
      );
    });

    it("clicking previous page triggers API with decremented page param", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 1,
          page_size: 20,
        } as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 3,
          page_size: 20,
        } as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 2,
          page_size: 20,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      // Navigate to page 3 first
      const page3Btn = screen.getByRole("button", { name: "3" });
      await user.click(page3Btn);

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(2);
      });

      // Then click previous
      const prevBtn = screen.getByRole("button", { name: /上一页/i });
      await user.click(prevBtn);

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(3);
      });

      expect(api.listAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2 })
      );
    });

    it("clicking a specific page number triggers API with that page param", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 1,
          page_size: 20,
        } as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 3,
          page_size: 20,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const pageBtn = screen.getByRole("button", { name: "3" });
      await user.click(pageBtn);

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(2);
      });

      expect(api.listAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 3 })
      );
    });

    it("page size change triggers API with new page_size param", async () => {
      vi.mocked(api.listAuditLogs)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 1,
          page_size: 20,
        } as any)
        .mockResolvedValueOnce({
          ...mockAuditLogsResponse(),
          total: 100,
          page: 1,
          page_size: 50,
        } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const pageSizeSelect = screen.getByLabelText(/每页条数/i);
      await user.selectOptions(pageSizeSelect, "50");

      await waitFor(() => {
        expect(api.listAuditLogs).toHaveBeenCalledTimes(2);
      });

      expect(api.listAuditLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_size: 50 })
      );
    });
  });

  // ── Export ─────────────────────────────────────────────────────────────

  describe("Export", () => {
    it("clicking export button calls exportAuditLogs with default format", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);
      vi.mocked(api.exportAuditLogs).mockResolvedValue(mockExportAuditLogsResponse() as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const exportBtn = screen.getByRole("button", { name: /导出/i });
      await user.click(exportBtn);

      await waitFor(() => {
        expect(api.exportAuditLogs).toHaveBeenCalledTimes(1);
      });

      expect(api.exportAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ format: "csv" })
      );
    });

    it("clicking export with excel format calls exportAuditLogs with excel", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);
      vi.mocked(api.exportAuditLogs).mockResolvedValue(mockExportAuditLogsResponse() as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const formatSelect = screen.getByLabelText(/导出格式/i);
      await user.selectOptions(formatSelect, "excel");

      const exportBtn = screen.getByRole("button", { name: /导出/i });
      await user.click(exportBtn);

      await waitFor(() => {
        expect(api.exportAuditLogs).toHaveBeenCalledTimes(1);
      });

      expect(api.exportAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ format: "excel" })
      );
    });

    it("successful export shows toast success message", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);
      vi.mocked(api.exportAuditLogs).mockResolvedValue(mockExportAuditLogsResponse() as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const exportBtn = screen.getByRole("button", { name: /导出/i });
      await user.click(exportBtn);

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });
    });

    it("export failure shows toast error message", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsResponse() as any);
      vi.mocked(api.exportAuditLogs).mockRejectedValue(new Error("Export failed"));

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("admin@example.com")).toBeInTheDocument();
      });

      const exportBtn = screen.getByRole("button", { name: /导出/i });
      await user.click(exportBtn);

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalled();
      });
    });
  });

  // ── Empty State ────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows EmptyState with '暂无审计日志' when no logs", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsEmptyResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无审计日志/)).toBeInTheDocument();
      });
    });

    it("does not render log rows when empty", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsEmptyResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无审计日志/)).toBeInTheDocument();
      });

      expect(screen.queryByTestId("audit-log-row")).not.toBeInTheDocument();
    });
  });

  // ── Error State ────────────────────────────────────────────────────────

  describe("Error State", () => {
    it("shows Alert with '加载审计日志失败' when list API fails", async () => {
      vi.mocked(api.listAuditLogs).mockRejectedValue(new Error("Network error"));

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toBeInTheDocument();
        expect(alert).toHaveTextContent(/加载审计日志失败/);
      });
    });

    it("does not render skeleton after error", async () => {
      vi.mocked(api.listAuditLogs).mockRejectedValue(new Error("Network error"));

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(screen.queryByTestId("audit-log-skeleton")).not.toBeInTheDocument();
    });

    it("does not render log rows after error", async () => {
      vi.mocked(api.listAuditLogs).mockRejectedValue(new Error("Network error"));

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(screen.queryByTestId("audit-log-row")).not.toBeInTheDocument();
    });
  });

  // ── Boundary State ─────────────────────────────────────────────────────

  describe("Boundary State", () => {
    it("renders log with very long operator_email without crashing", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsBoundaryResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520) + "@example.com")).toBeInTheDocument();
      });
    });

    it("renders log with very large details object without crashing", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsBoundaryResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("log-boundary")).toBeInTheDocument();
      });
    });

    it("renders log with special operation type without crashing", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue({
        ...mockAuditLogsBoundaryResponse(),
        items: [
          {
            ...mockAuditLogsBoundaryResponse().items[0],
            operation_type: "delete",
          },
        ],
      } as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("delete")).toBeInTheDocument();
      });
    });

    it("renders log with IPv6 address", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsBoundaryResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("2001:0db8:85a3:0000:0000:8a2e:0370:7334")).toBeInTheDocument();
      });
    });

    it("renders log with future timestamp", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsBoundaryResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        // The UTC timestamp 2099-12-31T23:59:59Z may convert to 2100 in local time (+8 TZ)
        const row = screen.getByTestId("audit-log-row");
        expect(row.innerHTML).toMatch(/2099|2100/);
      });
    });

    it("handles very large total count in pagination", async () => {
      vi.mocked(api.listAuditLogs).mockResolvedValue(mockAuditLogsBoundaryResponse() as any);

      const Wrapper = createWrapper();
      render(<AuditLogPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/999999/)).toBeInTheDocument();
      });
    });
  });
});
