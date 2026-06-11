import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ────────────────────────────────────────────────────────────────

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    getDashboard: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import { DashboardPage } from "./dashboard-page";

// ── Helpers ──────────────────────────────────────────────────────────────

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function mockDashboardResponse(overrides?: Record<string, unknown>) {
  return {
    stats: {
      today_uploads: 12,
      pending_review_count: 3,
      total_documents: 147,
      stale_ratio: 0.08,
    },
    recent_tickets: [
      {
        ticket_id: "ticket-001",
        collection_id: "coll-001",
        status: "pending_review",
        title: "Review document.pdf",
        filename: "document.pdf",
        priority: "high",
        assignee_user_id: "user-001",
        doc_id: "doc-001",
        source_file_id: "sf-001",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T01:00:00Z",
      },
      {
        ticket_id: "ticket-002",
        collection_id: "coll-001",
        status: "pending_review",
        title: "Review report.docx",
        filename: "report.docx",
        priority: "medium",
        assignee_user_id: "user-001",
        doc_id: "doc-002",
        source_file_id: "sf-002",
        created_at: "2024-01-02T00:00:00Z",
        updated_at: "2024-01-02T01:00:00Z",
      },
      {
        ticket_id: "ticket-003",
        collection_id: "coll-001",
        status: "pending_review",
        title: "Review slides.pptx",
        filename: "slides.pptx",
        priority: "low",
        assignee_user_id: "user-001",
        doc_id: "doc-003",
        source_file_id: "sf-003",
        created_at: "2024-01-03T00:00:00Z",
        updated_at: "2024-01-03T01:00:00Z",
      },
    ],
    ...overrides,
  };
}

function mockDashboardEmptyResponse() {
  return {
    stats: {
      today_uploads: 0,
      pending_review_count: 0,
      total_documents: 0,
      stale_ratio: 0,
    },
    recent_tickets: [],
  };
}

function mockDashboardBoundaryResponse() {
  return {
    stats: {
      today_uploads: 999999999,
      pending_review_count: 999999999,
      total_documents: 999999999,
      stale_ratio: 0.999999,
    },
    recent_tickets: [
      {
        ticket_id: "ticket-001",
        collection_id: "coll-001",
        status: "pending_review",
        title: "a".repeat(520),
        filename: "测试中文内容 🚀 日本語テキスト 🇯🇵 한국어 텍스트 🇰🇷 العربية 🌍",
        priority: "high",
        assignee_user_id: "user-001",
        doc_id: "doc-001",
        source_file_id: "sf-001",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T01:00:00Z",
      },
    ],
  };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("renders 4 skeleton cards while data is loading", async () => {
      // Never resolve to keep loading state
      vi.mocked(workbenchApi.getDashboard).mockImplementation(
        () => new Promise(() => {})
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      const skeletons = screen.getAllByTestId("stat-skeleton");
      expect(skeletons).toHaveLength(4);
    });
  });

  // ── Success State ──────────────────────────────────────────────────────

  describe("Success State - Normal Data", () => {
    it("renders 4 stat cards with correct values", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("12")).toBeInTheDocument();
      });

      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("147")).toBeInTheDocument();
      // stale_ratio 0.08 should be formatted as "8%"
      expect(screen.getByText("8%")).toBeInTheDocument();
    });

    it("renders recent tickets list with filenames", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("report.docx")).toBeInTheDocument();
      expect(screen.getByText("slides.pptx")).toBeInTheDocument();
    });

    it("formats stale_ratio as percentage", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse({
          stats: {
            today_uploads: 5,
            pending_review_count: 1,
            total_documents: 100,
            stale_ratio: 0.125,
          },
        }) as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("12.5%")).toBeInTheDocument();
      });
    });

    it("formats stale_ratio of 0 as 0%", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse({
          stats: {
            today_uploads: 5,
            pending_review_count: 1,
            total_documents: 100,
            stale_ratio: 0,
          },
        }) as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("0%")).toBeInTheDocument();
      });
    });

    it("formats stale_ratio of 1 as 100%", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse({
          stats: {
            today_uploads: 5,
            pending_review_count: 1,
            total_documents: 100,
            stale_ratio: 1,
          },
        }) as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("100%")).toBeInTheDocument();
      });
    });
  });

  // ── Action -> Effect Chain ─────────────────────────────────────────────

  describe("Action -> Effect Chain", () => {
    it("clicking a ticket card calls router.push with /review/:ticketId", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const ticketCard = screen
        .getByText("document.pdf")
        .closest("[data-testid='ticket-card']");
      expect(ticketCard).toBeTruthy();
      await user.click(ticketCard!);

      expect(mockPush).toHaveBeenCalledTimes(1);
      expect(mockPush).toHaveBeenCalledWith("/review/ticket-001");
    });

    it("clicking different tickets navigates to correct routes", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("report.docx")).toBeInTheDocument();
      });

      const ticketCard = screen
        .getByText("report.docx")
        .closest("[data-testid='ticket-card']");
      await user.click(ticketCard!);

      expect(mockPush).toHaveBeenCalledWith("/review/ticket-002");
    });
  });

  // ── Empty State ────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows EmptyState with '暂无数据' when total_documents is 0", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardEmptyResponse() as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无数据/)).toBeInTheDocument();
      });
    });

    it("does not render stat cards when total_documents is 0", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardEmptyResponse() as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无数据/)).toBeInTheDocument();
      });

      // Should not show any of the stat numbers
      expect(screen.queryByText("12")).not.toBeInTheDocument();
      expect(screen.queryByText("0")).not.toBeInTheDocument();
    });
  });

  // ── Error State ────────────────────────────────────────────────────────

  describe("Error State", () => {
    it("shows Alert with '加载仪表盘数据失败' when API fails", async () => {
      vi.mocked(workbenchApi.getDashboard).mockRejectedValue(
        new Error("Network error")
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toBeInTheDocument();
        expect(alert).toHaveTextContent(/加载仪表盘数据失败/);
      });
    });

    it("does not render skeletons after error is received", async () => {
      vi.mocked(workbenchApi.getDashboard).mockRejectedValue(
        new Error("Network error")
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(screen.queryAllByTestId("stat-skeleton")).toHaveLength(0);
    });
  });

  // ── Boundary State ─────────────────────────────────────────────────────

  describe("Boundary State", () => {
    it("formats large numbers with thousand separators", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryAllByText("999,999,999").length).toBeGreaterThanOrEqual(1);
      });
    });

    it("formats very high stale_ratio correctly", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        // 0.999999 should be formatted as ~100% or 99.9999%
        const staleText = screen.getByText(/99.9999%|100%/);
        expect(staleText).toBeInTheDocument();
      });
    });

    it("renders ticket with unicode filename without crashing", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(
          screen.getByText(/测试中文内容|🚀|日本語/)
        ).toBeInTheDocument();
      });
    });

    it("clicking ticket with boundary data navigates correctly", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardBoundaryResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DashboardPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId("ticket-card")).toBeInTheDocument();
      });

      const ticketCard = screen.getByTestId("ticket-card");
      await user.click(ticketCard);

      expect(mockPush).toHaveBeenCalledWith("/review/ticket-001");
    });
  });
});
