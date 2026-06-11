import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ────────────────────────────────────────────────────────────────

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, className, onClick }: any) => (
    <a href={href} className={className} onClick={onClick}>{children}</a>
  ),
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
import HomePage from "./page";

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

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("HomePage (Dashboard)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("renders skeletons while data is loading", async () => {
      vi.mocked(workbenchApi.getDashboard).mockImplementation(
        () => new Promise(() => {})
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      expect(screen.getByText(/早上好|下午好|晚上好/)).toBeInTheDocument();
      const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  // ── Success State ──────────────────────────────────────────────────────

  describe("Success State - Normal Data", () => {
    it("renders welcome header with greeting and date", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/早上好|下午好|晚上好/)).toBeInTheDocument();
      });

      expect(
        screen.getByText(/欢迎来到 Knowledge Workbench/)
      ).toBeInTheDocument();
    });

    it("renders 6 quick action cards", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("上传文档")).toBeInTheDocument();
      });

      expect(screen.getByText("复核队列")).toBeInTheDocument();
      expect(screen.getByText("文档库")).toBeInTheDocument();
      expect(screen.getByText("检索验证")).toBeInTheDocument();
      expect(screen.getByText("知识库集合")).toBeInTheDocument();
      expect(screen.getByText("系统设置")).toBeInTheDocument();
    });

    it("renders 4 stat cards with correct values", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("12")).toBeInTheDocument();
      });

      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("147")).toBeInTheDocument();
      expect(screen.getByText("8%")).toBeInTheDocument();
    });

    it("renders recent tickets list with filenames", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("report.docx")).toBeInTheDocument();
      expect(screen.getByText("slides.pptx")).toBeInTheDocument();
    });

    it("renders announcement banner", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/欢迎使用 Knowledge Workbench/)).toBeInTheDocument();
      });
    });

    it("renders '查看全部' link for tickets", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("查看全部")).toBeInTheDocument();
      });
    });
  });

  // ── Quick Actions ──────────────────────────────────────────────────────

  describe("Quick Actions", () => {
    it("quick action cards have correct hrefs", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardResponse() as any
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("上传文档")).toBeInTheDocument();
      });

      const links = screen.getAllByRole("link");
      const hrefs = links.map((l) => l.getAttribute("href"));
      expect(hrefs).toContain("/upload");
      expect(hrefs).toContain("/review");
      expect(hrefs).toContain("/documents");
      expect(hrefs).toContain("/retrieval");
      expect(hrefs).toContain("/collections");
      expect(hrefs).toContain("/settings");
    });
  });

  // ── Empty State ────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows EmptyState when total_documents is 0", async () => {
      vi.mocked(workbenchApi.getDashboard).mockResolvedValue(
        mockDashboardEmptyResponse() as any
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无数据/)).toBeInTheDocument();
      });
    });
  });

  // ── Error State ────────────────────────────────────────────────────────

  describe("Error State", () => {
    it("shows Alert with '加载仪表盘数据失败' when API fails", async () => {
      vi.mocked(workbenchApi.getDashboard).mockRejectedValue(
        new Error("Network error")
      );

      const Wrapper = createWrapper();
      render(<HomePage />, { wrapper: Wrapper });

      await waitFor(() => {
        const alerts = screen.queryAllByRole("alert");
        const errorAlert = alerts.find((a) =>
          a.textContent?.includes("加载仪表盘数据失败")
        );
        expect(errorAlert).toBeTruthy();
      });
    });
  });
});
