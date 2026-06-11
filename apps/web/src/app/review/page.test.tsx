import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} data-testid="next-link" {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    me: vi.fn(),
    listCollections: vi.fn(),
    listTickets: vi.fn(),
  } as any,
}));

import { workbenchApi } from "@/lib/api/client";
import ReviewQueuePage from "./page";

// Cast the imported workbenchApi to include mocked methods for type-checking.
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

function mockMeResponse(overrides?: Record<string, unknown>) {
  return {
    user_id: "user-001",
    email: "admin@example.com",
    display_name: "Administrator",
    roles: ["knowledge_admin"],
    tenant_id: "tenant-001",
    allowed_collections: ["coll-001", "coll-002"],
    ...overrides,
  };
}

function mockCollectionsResponse(overrides?: Record<string, unknown>) {
  return {
    items: [
      {
        collection_id: "coll-001",
        tenant_id: "tenant-001",
        name: "Default Collection",
        description: "Primary knowledge base collection",
        lifecycle_state: "active",
        authority_level: 1,
        access_policy: { public: false },
        default_parser_profile_id: "parser-default",
        default_retrieval_profile_id: "retrieval-default",
        default_approval_policy_id: "approval-default",
        created_by: "user-001",
        created_at: "2024-01-01T00:00:00Z",
        updated_by: "user-001",
        updated_at: "2024-06-01T00:00:00Z",
      },
      {
        collection_id: "coll-002",
        tenant_id: "tenant-001",
        name: "Secondary Collection",
        description: "Secondary knowledge base collection",
        lifecycle_state: "active",
        authority_level: 1,
        access_policy: { public: false },
        default_parser_profile_id: "parser-default",
        default_retrieval_profile_id: "retrieval-default",
        default_approval_policy_id: "approval-default",
        created_by: "user-001",
        created_at: "2024-01-01T00:00:00Z",
        updated_by: "user-001",
        updated_at: "2024-06-01T00:00:00Z",
      },
    ],
    total: 2,
    ...overrides,
  };
}

function mockTicketItem(overrides?: Record<string, unknown>) {
  return {
    ticket_id: "ticket-001",
    collection_id: "coll-001",
    status: "pending",
    title: "Review document.pdf",
    filename: "document.pdf",
    priority: "high",
    assignee_user_id: "user-001",
    doc_id: "doc-001",
    source_file_id: "sf-001",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function mockListTicketsResponse(overrides?: Record<string, unknown>) {
  return {
    items: [
      mockTicketItem(),
      mockTicketItem({
        ticket_id: "ticket-002",
        collection_id: "coll-002",
        status: "approved",
        filename: "report.docx",
        title: "Review report.docx",
        doc_id: "doc-002",
        updated_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      }),
      mockTicketItem({
        ticket_id: "ticket-003",
        collection_id: "coll-001",
        status: "rejected",
        filename: "slides.pptx",
        title: "Review slides.pptx",
        doc_id: "doc-003",
        updated_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      }),
      mockTicketItem({
        ticket_id: "ticket-004",
        collection_id: "coll-002",
        status: "returned",
        filename: "notes.txt",
        title: "Review notes.txt",
        doc_id: "doc-004",
        updated_at: new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString(),
      }),
    ],
    total: 4,
    ...overrides,
  };
}

function mockListTicketsEmptyResponse() {
  return { items: [], total: 0 };
}

function mockListTicketsBoundaryResponse() {
  return {
    items: [
      mockTicketItem({
        ticket_id: "ticket-boundary",
        filename: "a".repeat(520),
        title: "",
        doc_id: "doc-boundary",
        status: "pending_review",
      }),
    ],
    total: 1,
  };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("ReviewQueuePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.me).mockResolvedValue(mockMeResponse());
    vi.mocked(api.listCollections).mockResolvedValue(mockCollectionsResponse());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("renders 4 skeleton cards while tickets are loading", async () => {
      vi.mocked(api.listTickets).mockImplementation(() => new Promise(() => {}));

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
        expect(skeletons.length).toBeGreaterThanOrEqual(4);
      });
    });
  });

  // ── Success State - Normal Data ────────────────────────────────────────

  describe("Success State - Normal Data", () => {
    it("renders page title and subtitle", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("人工复核队列")).toBeInTheDocument();
      });

      expect(
        screen.getByText(/自动入库代理拦截的文档会在这里等待人工复核/)
      ).toBeInTheDocument();
    });

    it("renders tickets with filename as display title", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("report.docx")).toBeInTheDocument();
      expect(screen.getByText("slides.pptx")).toBeInTheDocument();
      expect(screen.getByText("notes.txt")).toBeInTheDocument();
    });

    it("falls back to title when filename is missing", async () => {
      vi.mocked(api.listTickets).mockResolvedValue({
        items: [
          mockTicketItem({
            ticket_id: "ticket-fallback",
            filename: "",
            title: "Fallback Title",
          }),
        ],
        total: 1,
      });

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Fallback Title")).toBeInTheDocument();
      });
    });

    it("falls back to doc_id when filename and title are missing", async () => {
      vi.mocked(api.listTickets).mockResolvedValue({
        items: [
          mockTicketItem({
            ticket_id: "ticket-doc-fallback",
            filename: "",
            title: "",
            doc_id: "doc-fallback-123",
          }),
        ],
        total: 1,
      });

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("doc-fallback-123")).toBeInTheDocument();
      });
    });

    it("shows status badges for all ticket statuses", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      // Status labels should appear at least once each (as badges)
      expect(screen.getAllByText("待复核").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("已批准").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("已拒绝").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("已退回").length).toBeGreaterThanOrEqual(1);
    });

    it("shows collection_id badges", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getAllByText("coll-001").length).toBeGreaterThanOrEqual(2);
      });

      expect(screen.getAllByText("coll-002").length).toBeGreaterThanOrEqual(2);
    });

    it("shows ticket_id in monospace", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("ticket-001")).toBeInTheDocument();
      });

      expect(screen.getByText("ticket-002")).toBeInTheDocument();
    });

    it("shows relative time for tickets", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const Wrapper = createWrapper();
      const { container } = render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      // Each ticket row has a relative-time span with a title attribute
      const timeElements = container.querySelectorAll("span[title]");
      const hasRelativeTime = Array.from(timeElements).some((el) =>
        /刚刚|分钟前|小时前|天前|\d{4}\/\d{1,2}\/\d{1,2}/.test(el.textContent || "")
      );
      expect(hasRelativeTime).toBe(true);
    });

    it("renders pulse animation for pending status", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const Wrapper = createWrapper();
      const { container } = render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      // Pending status badge should contain an animate-ping element
      const pingElements = container.querySelectorAll(".animate-ping");
      expect(pingElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ── Collection Filter ──────────────────────────────────────────────────

  describe("Collection Filter", () => {
    it("filters tickets when selecting a collection", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      // Open collection select
      const collectionTrigger = screen.getAllByRole("combobox")[0];
      await user.click(collectionTrigger);

      // Wait for popup to open and select coll-001
      await waitFor(() => {
        expect(screen.getByText("Default Collection")).toBeInTheDocument();
      });

      const option = screen.getByText("Default Collection");
      await user.click(option);

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
        expect(screen.queryByText("report.docx")).not.toBeInTheDocument();
      });
    });
  });

  // ── Status Filter ──────────────────────────────────────────────────────

  describe("Status Filter", () => {
    it("filters tickets when selecting a status", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      // Open status select (second combobox)
      const statusTrigger = screen.getAllByRole("combobox")[1];
      await user.click(statusTrigger);

      // Wait for popup and select 已批准 (APPROVED) from the dropdown options
      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const options = screen.getAllByRole("option");
      const approvedOption = options.find((opt) => opt.textContent?.includes("已批准"));
      expect(approvedOption).toBeDefined();
      await user.click(approvedOption!);

      await waitFor(() => {
        expect(screen.queryByText("document.pdf")).not.toBeInTheDocument();
        expect(screen.getByText("report.docx")).toBeInTheDocument();
        expect(screen.queryByText("slides.pptx")).not.toBeInTheDocument();
      });
    });
  });

  // ── Clear Filters ──────────────────────────────────────────────────────

  describe("Clear Filters", () => {
    it("shows clear filters button when a filter is active", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.queryByRole("button", { name: /清除筛选/i })).not.toBeInTheDocument();

      const statusTrigger = screen.getAllByRole("combobox")[1];
      await user.click(statusTrigger);

      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const pendingOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("待复核")
      );
      expect(pendingOption).toBeDefined();
      await user.click(pendingOption!);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /清除筛选/i })).toBeInTheDocument();
      });
    });

    it("clears both filters when clicking clear button", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      // Apply collection filter
      const collectionTrigger = screen.getAllByRole("combobox")[0];
      await user.click(collectionTrigger);

      await waitFor(() => {
        expect(screen.getByText("Default Collection")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Default Collection"));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /清除筛选/i })).toBeInTheDocument();
      });

      // Click clear filters
      await user.click(screen.getByRole("button", { name: /清除筛选/i }));

      await waitFor(() => {
        expect(screen.queryByRole("button", { name: /清除筛选/i })).not.toBeInTheDocument();
        expect(screen.getByText("report.docx")).toBeInTheDocument();
      });
    });
  });

  // ── Empty State ────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows empty state when no tickets exist", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsEmptyResponse());

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("恭喜，队列已清空")).toBeInTheDocument();
      });

      expect(
        screen.getByText(/当前没有待复核的工单/)
      ).toBeInTheDocument();
    });

    it("shows empty state when filters match no tickets", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const collectionTrigger = screen.getAllByRole("combobox")[0];
      await user.click(collectionTrigger);

      await waitFor(() => {
        expect(screen.getByText("Default Collection")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Default Collection"));

      const statusTrigger = screen.getAllByRole("combobox")[1];
      await user.click(statusTrigger);

      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const returnedOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("已退回")
      );
      expect(returnedOption).toBeDefined();
      await user.click(returnedOption!);

      await waitFor(() => {
        expect(screen.getByText("恭喜，队列已清空")).toBeInTheDocument();
      });
    });
  });

  // ── Error State ────────────────────────────────────────────────────────

  describe("Error State", () => {
    it("shows error message when tickets API fails", async () => {
      vi.mocked(api.listTickets).mockRejectedValue(new Error("Network error"));

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/Network error/)).toBeInTheDocument();
      });
    });

    it("does not render skeleton after error", async () => {
      vi.mocked(api.listTickets).mockRejectedValue(new Error("Network error"));

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/Network error/)).toBeInTheDocument();
      });

      expect(document.querySelector('[data-slot="skeleton"]')).not.toBeInTheDocument();
    });

    it("shows BackendGap when API returns 501", async () => {
      const { BackendGapError } = await import("@/lib/api/errors");
      vi.mocked(api.listTickets).mockRejectedValue(
        new BackendGapError("GET /workbench/tickets", "/api/workbench/tickets", "Not implemented")
      );

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/后端能力缺口/)).toBeInTheDocument();
      });
    });
  });

  // ── Navigation ─────────────────────────────────────────────────────────

  describe("Navigation", () => {
    it("renders links to /review/{ticket_id} for each ticket", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsResponse());

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const links = screen.getAllByTestId("next-link");
      const hrefs = links.map((link) => link.getAttribute("href"));

      expect(hrefs).toContain("/review/ticket-001");
      expect(hrefs).toContain("/review/ticket-002");
      expect(hrefs).toContain("/review/ticket-003");
      expect(hrefs).toContain("/review/ticket-004");
    });
  });

  // ── Boundary State ─────────────────────────────────────────────────────

  describe("Boundary State", () => {
    it("renders ticket with very long filename without crashing", async () => {
      vi.mocked(api.listTickets).mockResolvedValue(mockListTicketsBoundaryResponse());

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });
    });

    it("renders ticket with missing fields without crashing", async () => {
      vi.mocked(api.listTickets).mockResolvedValue({
        items: [
          {
            ticket_id: "ticket-minimal",
            collection_id: "coll-001",
            status: "pending",
            created_at: "2024-01-01T00:00:00Z",
            updated_at: null,
          },
        ],
        total: 1,
      });

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getAllByText("ticket-minimal").length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getAllByText("coll-001").length).toBeGreaterThanOrEqual(1);
    });

    it("renders many tickets without crashing", async () => {
      const manyTickets = Array.from({ length: 50 }, (_, i) =>
        mockTicketItem({
          ticket_id: `ticket-${String(i).padStart(3, "0")}`,
          filename: `file-${i}.pdf`,
          status: i % 4 === 0 ? "pending_review" : i % 4 === 1 ? "approved" : i % 4 === 2 ? "rejected" : "returned",
        })
      );

      vi.mocked(api.listTickets).mockResolvedValue({
        items: manyTickets,
        total: 50,
      });

      const Wrapper = createWrapper();
      render(<ReviewQueuePage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("file-0.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("file-49.pdf")).toBeInTheDocument();
    });
  });
});
