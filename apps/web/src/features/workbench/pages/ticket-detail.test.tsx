import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TicketDetailPage } from "./ticket-detail";
import { workbenchApi } from "@/lib/api/client";
import { ApiClientError, BackendGapError } from "@/lib/api/errors";
import {
  buildWorkspaceDetailResponse,
  buildWorkspaceDetailEmptyResponse,
  buildWorkspaceDetailBoundaryResponse,
  buildDecideTicketResponse,
} from "@/mocks/handlers";
import { toast } from "sonner";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    getWorkspaceDetail: vi.fn(),
    decideTicket: vi.fn(),
  },
  WORKBENCH_BASE: "/api/workbench",
}));

vi.mock("@/features/workbench/components/chunk-editor", () => ({
  ChunkEditorWorkbench: () => <div data-testid="chunk-editor-mock" />,
}));

vi.mock("@/components/document-workbench/document-viewer", () => ({
  DocumentViewer: () => <div data-testid="document-viewer-mock" />,
}));

vi.mock("@/features/workbench/components/agent-review", () => ({
  AgentReviewPanel: () => <div data-testid="agent-review-mock" />,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

const api = workbenchApi;

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderPage(props: { ticketId: string; backHref?: string }) {
  const queryClient = createQueryClient();
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <TicketDetailPage {...props} />
    </QueryClientProvider>
  );
  return { ...utils, queryClient };
}

function workspace(overrides?: Parameters<typeof buildWorkspaceDetailResponse>[0]) {
  return buildWorkspaceDetailResponse(overrides);
}

describe("TicketDetailPage", () => {
  beforeEach(() => {
    vi.mocked(api.getWorkspaceDetail).mockReset();
    vi.mocked(api.decideTicket).mockReset();
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
    vi.mocked(toast.info).mockClear();
  });

  describe("Loading State", () => {
    it("shows skeleton while loading", () => {
      vi.mocked(api.getWorkspaceDetail).mockImplementation(
        () => new Promise(() => {})
      );
      renderPage({ ticketId: "ticket-001" });
      expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(2);
    });
  });

  describe("Success State - Header", () => {
    it("renders back button with correct backHref", async () => {
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(workspace());
      renderPage({ ticketId: "ticket-001", backHref: "/review" });
      await waitFor(() =>
        expect(screen.getByRole("link")).toHaveAttribute("href", "/review")
      );
    });

    it("renders ticket title from filename", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          document: { ...base.document, filename: "report.docx" },
          parse_snapshot: { ...base.parse_snapshot!, source_filename: "report.docx" },
          ticket: { ...base.ticket!, filename: "report.docx" },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1, name: /report\.docx/i })).toBeInTheDocument()
      );
    });

    it("renders fallback title from doc_id when filename missing", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          document: { ...base.document, filename: "" },
          parse_snapshot: { ...base.parse_snapshot!, source_filename: "" },
          ticket: { ...base.ticket!, filename: "" },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1, name: "doc-001" })).toBeInTheDocument()
      );
    });

    it("renders fallback title from ticket_id when filename and doc_id missing", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          document: { ...base.document, doc_id: null, filename: "" },
          parse_snapshot: { ...base.parse_snapshot!, source_filename: "" },
          ticket: { ...base.ticket!, doc_id: null, filename: "" },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1, name: "ticket-001" })).toBeInTheDocument()
      );
    });

    it("shows status badge (待复核)", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({ ticket: { ...base.ticket!, status: "pending_review" } })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getAllByText("pending_review").length).toBeGreaterThanOrEqual(1)
      );
    });

    it("shows status badge (已批准)", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({ ticket: { ...base.ticket!, status: "approved" } })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getAllByText("Approved").length).toBeGreaterThanOrEqual(1)
      );
    });

    it("shows status badge (已拒绝)", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({ ticket: { ...base.ticket!, status: "rejected" } })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getAllByText("Rejected").length).toBeGreaterThanOrEqual(1)
      );
    });

    it("shows status badge (已退回)", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({ ticket: { ...base.ticket!, status: "returned" } })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getAllByText("returned").length).toBeGreaterThanOrEqual(1)
      );
    });

    it("shows failure_code badge when present", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({ ticket: { ...base.ticket!, failure_code: "PARSE_TIMEOUT" } })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByText("PARSE_TIMEOUT")).toBeInTheDocument());
    });

    it("shows next_action badge when present", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({ ticket: { ...base.ticket!, next_action: "review" } })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByText("Needs Review")).toBeInTheDocument());
    });

    it("shows linkage_source badge when not document_projection", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({ document: { ...base.document, linkage_source: "missing" } })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByText(/Linkage: missing/i)).toBeInTheDocument());
    });
  });

  function getMetricCardByLabel(label: string) {
    const labels = screen.getAllByText(label);
    const metricLabel = labels.find((el) =>
      el.classList.contains("text-muted-foreground")
    );
    if (!metricLabel) throw new Error(`Metric label "${label}" not found`);
    return metricLabel.parentElement as HTMLElement;
  }

  describe("Success State - Metrics", () => {
    it("shows Findings count", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          agent_review: {
            ...base.agent_review,
            findings: [
              {
                finding_id: "f-001",
                severity: "medium",
                category: "c1",
                problem_summary: "p1",
                state: "open",
              },
              {
                finding_id: "f-002",
                severity: "low",
                category: "c2",
                problem_summary: "p2",
                state: "open",
              },
            ],
          },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getAllByText("Findings").length).toBeGreaterThanOrEqual(1));
      expect(within(getMetricCardByLabel("Findings")).getByText("2")).toBeInTheDocument();
    });

    it("shows Risks count (critical/high severity)", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          agent_review: {
            ...base.agent_review,
            findings: [
              { finding_id: "f-001", severity: "critical", category: "c", problem_summary: "p", state: "open" },
              { finding_id: "f-002", severity: "high", category: "c", problem_summary: "p", state: "open" },
              { finding_id: "f-003", severity: "medium", category: "c", problem_summary: "p", state: "open" },
            ],
          },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getAllByText("Risks").length).toBeGreaterThanOrEqual(1));
      expect(within(getMetricCardByLabel("Risks")).getByText("2")).toBeInTheDocument();
    });

    it("shows Draft edits count", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          chunk_edits: {
            items: [
              {
                chunk_edit_id: "ce-001",
                tenant_id: "tenant-001",
                collection_id: "coll-001",
                base_evidence_id: "ev-001",
                edit_scope: "content",
                operation: "replace",
                edited_by: "user-001",
                status: "pending",
              },
            ],
            total: 1,
          },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getAllByText("Draft edits").length).toBeGreaterThanOrEqual(1));
      expect(within(getMetricCardByLabel("Draft edits")).getByText("1")).toBeInTheDocument();
    });

    it("shows Warnings count", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          parse_snapshot: {
            ...base.parse_snapshot!,
            warnings: ["warning-1", "warning-2"],
          },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getAllByText("Warnings").length).toBeGreaterThanOrEqual(1));
      expect(within(getMetricCardByLabel("Warnings")).getByText("2")).toBeInTheDocument();
    });
  });

  describe("Success State - Metadata", () => {
    it("shows Ticket id, Collection, Document id, Parse snapshot", async () => {
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(workspace());
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getAllByText("ticket-001").length).toBeGreaterThanOrEqual(1));
      expect(screen.getAllByText("coll-001").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("doc-001").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("ps-001").length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Degraded Alert", () => {
    it("shows degraded parts alert when degraded_parts is non-empty", async () => {
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({ degraded_parts: ["agent_review", "chunks"] })
      );
      renderPage({ ticketId: "ticket-001" });
      const alerts = await screen.findAllByRole("alert");
      const degradedAlert = alerts.find((a) =>
        a.textContent?.includes("Workspace is partially degraded")
      );
      expect(degradedAlert).toBeDefined();
      expect(degradedAlert!).toHaveTextContent(/agent_review, chunks/i);
    });
  });

  describe("Tabs", () => {
    it("renders all 3 tabs: Source, Draft edits, Agent review", async () => {
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(workspace());
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByRole("tab", { name: /Source/i })).toBeInTheDocument());
      expect(screen.getByRole("tab", { name: /Draft edits/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /Agent review/i })).toBeInTheDocument();
    });

    it("clicking tabs switches active tab", async () => {
      const user = userEvent.setup();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(workspace());
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByRole("tab", { name: /Source/i })).toBeInTheDocument());
      const draftsTab = screen.getByRole("tab", { name: /Draft edits/i });
      await user.click(draftsTab);
      await waitFor(() => expect(document.activeElement).toBe(draftsTab));
      const agentTab = screen.getByRole("tab", { name: /Agent review/i });
      await user.click(agentTab);
      await waitFor(() => expect(document.activeElement).toBe(agentTab));
    });

    it("tab content renders mocked child component", async () => {
      const user = userEvent.setup();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(workspace());
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByTestId("document-viewer-mock")).toBeInTheDocument());
      await user.click(screen.getByRole("tab", { name: /Draft edits/i }));
      await waitFor(() => expect(screen.getByTestId("chunk-editor-mock")).toBeInTheDocument());
      await user.click(screen.getByRole("tab", { name: /Agent review/i }));
      await waitFor(() => expect(screen.getByTestId("agent-review-mock")).toBeInTheDocument());
    });
  });

  describe("Decision Submission", () => {
    it("renders Approve/Reject/Return buttons when pending", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "pending_review" },
          capabilities: { ...base.capabilities, can_decide_ticket: true },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument());
      expect(screen.getByRole("button", { name: /Reject/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Return for revision/i })).toBeInTheDocument();
    });

    it("hides decision buttons when not pending", async () => {
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "approved" },
          capabilities: { ...base.capabilities, can_decide_ticket: false },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument());
      expect(screen.queryByRole("button", { name: /Reject/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Return for revision/i })).not.toBeInTheDocument();
    });

    it("entering reason and clicking Approve calls decideTicket with correct payload", async () => {
      const user = userEvent.setup();
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "pending_review" },
          capabilities: { ...base.capabilities, can_decide_ticket: true },
        })
      );
      vi.mocked(api.decideTicket).mockResolvedValue(buildDecideTicketResponse());
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument());
      const reasonInput = screen.getByPlaceholderText(/Optional decision reason/i);
      await user.type(reasonInput, "Looks good");
      await user.click(screen.getByRole("button", { name: /Approve/i }));
      await waitFor(() =>
        expect(api.decideTicket).toHaveBeenCalledWith("ticket-001", {
          decision_request_id: expect.stringMatching(/^dec_\d+$/),
          action: "APPROVE",
          reason: "Looks good",
          tenant_id: "tenant-001",
          collection_id: "coll-001",
        })
      );
    });

    it("shows success toast after decision", async () => {
      const user = userEvent.setup();
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "pending_review" },
          capabilities: { ...base.capabilities, can_decide_ticket: true },
        })
      );
      vi.mocked(api.decideTicket).mockResolvedValue(buildDecideTicketResponse());
      const { queryClient } = renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument());
      await user.click(screen.getByRole("button", { name: /Approve/i }));
      await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Review decision submitted"));
      await waitFor(() =>
        expect(queryClient.isFetching({ queryKey: ["workspace", "ticket-001"] })).toBe(0)
      );
    });

    it("shows error toast when decision fails", async () => {
      const user = userEvent.setup();
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "pending_review" },
          capabilities: { ...base.capabilities, can_decide_ticket: true },
        })
      );
      vi.mocked(api.decideTicket).mockRejectedValue(new ApiClientError("DECISION_FAILED", "Server error", 500));
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument());
      await user.click(screen.getByRole("button", { name: /Approve/i }));
      await waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith("Server error")
      );
    });
  });

  describe("Empty/Missing State", () => {
    it("shows empty state when workspace missing", async () => {
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(buildWorkspaceDetailEmptyResponse());
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getByText("Review workspace not found")).toBeInTheDocument()
      );
    });
  });

  describe("Error State", () => {
    it("shows BackendGap component for 501 errors", async () => {
      vi.mocked(api.getWorkspaceDetail).mockRejectedValue(
        new BackendGapError("Review detail workspace", "/api/workbench/tickets/ticket-001/workspace")
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() =>
        expect(screen.getByText(/后端能力缺口/i)).toBeInTheDocument()
      );
    });

    it("shows error alert for generic errors", async () => {
      vi.mocked(api.getWorkspaceDetail).mockRejectedValue(new ApiClientError("FETCH_FAILED", "Network error", 500));
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
    });
  });

  describe("Boundary State", () => {
    it("renders with very long filename", async () => {
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(buildWorkspaceDetailBoundaryResponse());
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
      expect(screen.getByRole("heading", { level: 1 }).textContent!.length).toBeGreaterThan(100);
    });

    it("renders with many findings", async () => {
      const manyFindings = Array.from({ length: 50 }, (_, i) => ({
        finding_id: `f-${i}`,
        severity: (i % 2 === 0 ? "critical" : "high") as "critical" | "high",
        category: "category",
        problem_summary: `Problem ${i}`,
        state: "open" as const,
      }));
      const base = workspace();
      vi.mocked(api.getWorkspaceDetail).mockResolvedValue(
        workspace({
          agent_review: {
            ...base.agent_review,
            findings: manyFindings,
          },
        })
      );
      renderPage({ ticketId: "ticket-001" });
      await waitFor(() => expect(screen.getByText("Findings")).toBeInTheDocument());
      const findingsSection = screen.getByText("Findings").parentElement;
      const risksSection = screen.getByText("Risks").parentElement;
      expect(within(findingsSection!).getByText("50")).toBeInTheDocument();
      expect(within(risksSection!).getByText("50")).toBeInTheDocument();
    });
  });
});
