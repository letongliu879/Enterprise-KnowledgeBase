import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DocumentDetailPage from "./page";
import { workbenchApi } from "@/lib/api/client";
import { ApiClientError, BackendGapError } from "@/lib/api/errors";
import {
  buildDocumentWorkspaceResponse,
  buildDocumentWorkspaceEmptyResponse,
  buildDocumentWorkspaceBoundaryResponse,
  buildDecideTicketResponse,
  buildArchiveDocumentResponse,
  buildRetractDocumentResponse,
  buildReindexDocumentResponse,
} from "@/mocks/handlers";
import { toast } from "sonner";

vi.mock("next/navigation", () => ({
  useParams: () => ({ docId: "doc-001" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    getDocumentWorkspace: vi.fn(),
    decideTicket: vi.fn(),
    archiveDocument: vi.fn(),
    retractDocument: vi.fn(),
    reindexDocument: vi.fn(),
  },
  WORKBENCH_BASE: "/api/workbench",
}));

vi.mock("@/components/document-workbench/document-viewer", () => ({
  DocumentViewer: () => <div data-testid="document-viewer-mock" />,
}));

vi.mock("@/features/workbench/components/chunk-editor", () => ({
  ChunkEditorWorkbench: () => <div data-testid="chunk-editor-mock" />,
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

function renderPage() {
  const queryClient = createQueryClient();
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <DocumentDetailPage />
    </QueryClientProvider>
  );
  return { ...utils, queryClient };
}

function workspace(overrides?: Parameters<typeof buildDocumentWorkspaceResponse>[0]) {
  return buildDocumentWorkspaceResponse(overrides);
}

describe("DocumentDetailPage", () => {
  beforeEach(() => {
    vi.mocked(api.getDocumentWorkspace).mockReset();
    vi.mocked(api.decideTicket).mockReset();
    vi.mocked(api.archiveDocument).mockReset();
    vi.mocked(api.retractDocument).mockReset();
    vi.mocked(api.reindexDocument).mockReset();
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
    vi.mocked(toast.info).mockClear();
  });

  describe("Loading State", () => {
    it("shows skeleton while loading", () => {
      vi.mocked(api.getDocumentWorkspace).mockImplementation(() => new Promise(() => {}));
      renderPage();
      expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(2);
    });
  });

  describe("Success State - Header", () => {
    it("renders document title from filename", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          document: { ...base.document, filename: "report.docx" },
          ticket: { ...base.ticket!, filename: "report.docx" },
        })
      );
      renderPage();
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1, name: /report\.docx/i })).toBeInTheDocument()
      );
    });

    it("renders fallback title from doc_id when filename missing", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          document: { ...base.document, filename: "" },
          ticket: { ...base.ticket!, filename: "" },
        })
      );
      renderPage();
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1, name: "doc-001" })).toBeInTheDocument()
      );
    });

    it("renders fallback title from docId when filename and doc_id missing", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          document: { ...base.document, doc_id: "", filename: "" },
          ticket: { ...base.ticket!, doc_id: "", filename: "" },
        })
      );
      renderPage();
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1, name: "doc-001" })).toBeInTheDocument()
      );
    });

    it("shows document state badge", async () => {
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      renderPage();
      await waitFor(() => expect(screen.getByText("active")).toBeInTheDocument());
    });

    it("shows review status badge when ticket present", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({ ticket: { ...base.ticket!, status: "pending_review" } })
      );
      renderPage();
      await waitFor(() => expect(screen.getByText(/Review:/i)).toBeInTheDocument());
    });

    it("shows task status badge when task present", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({ task: { ...base.task!, status: "published" } })
      );
      renderPage();
      await waitFor(() => expect(screen.getByText(/Task:/i)).toBeInTheDocument());
    });

    it("shows stale badge when document is stale", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({ document: { ...base.document, is_stale: true } })
      );
      renderPage();
      await waitFor(() => expect(screen.getByText("STALE")).toBeInTheDocument());
    });

    it("shows degraded parts badge when present", async () => {
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({ degraded_parts: ["agent_review", "chunks"] })
      );
      renderPage();
      await waitFor(() =>
        expect(screen.getAllByText(/Degraded:/i).length).toBeGreaterThanOrEqual(1)
      );
      const badge = screen.getAllByText(/Degraded:/i).find((el) =>
        el.getAttribute("data-slot") === "badge"
      );
      expect(badge).toHaveTextContent(/agent_review, chunks/);
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
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          agent_review: {
            ...base.agent_review,
            findings: [
              {
                finding_id: "f-001",
                severity: "medium",
                category: "c1",
                problem_summary: "p1",
                source_quote: "q1",
                evidence_id: "ev-001",
                doc_id: "doc-001",
                source_file_id: "sf-001",
                parse_snapshot_id: "ps-001",
                page_from: 1,
                page_to: 1,
                state: "open",
                confidence: 0.8,
              },
              {
                finding_id: "f-002",
                severity: "low",
                category: "c2",
                problem_summary: "p2",
                source_quote: "q2",
                evidence_id: "ev-002",
                doc_id: "doc-001",
                source_file_id: "sf-001",
                parse_snapshot_id: "ps-001",
                page_from: 2,
                page_to: 2,
                state: "open",
                confidence: 0.7,
              },
            ],
          },
        })
      );
      renderPage();
      await waitFor(() => expect(screen.getAllByText("Findings").length).toBeGreaterThanOrEqual(1));
      expect(within(getMetricCardByLabel("Findings")).getByText("2")).toBeInTheDocument();
    });

    it("shows Blocking count (critical/high severity)", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          agent_review: {
            ...base.agent_review,
            findings: [
              {
                finding_id: "f-001",
                severity: "critical",
                category: "c",
                problem_summary: "p",
                source_quote: "q",
                evidence_id: "ev-001",
                doc_id: "doc-001",
                source_file_id: "sf-001",
                parse_snapshot_id: "ps-001",
                page_from: 1,
                page_to: 1,
                state: "open",
                confidence: 0.9,
              },
              {
                finding_id: "f-002",
                severity: "high",
                category: "c",
                problem_summary: "p",
                source_quote: "q",
                evidence_id: "ev-002",
                doc_id: "doc-001",
                source_file_id: "sf-001",
                parse_snapshot_id: "ps-001",
                page_from: 1,
                page_to: 1,
                state: "open",
                confidence: 0.85,
              },
              {
                finding_id: "f-003",
                severity: "medium",
                category: "c",
                problem_summary: "p",
                source_quote: "q",
                evidence_id: "ev-003",
                doc_id: "doc-001",
                source_file_id: "sf-001",
                parse_snapshot_id: "ps-001",
                page_from: 1,
                page_to: 1,
                state: "open",
                confidence: 0.7,
              },
            ],
          },
        })
      );
      renderPage();
      await waitFor(() => expect(screen.getAllByText("Blocking").length).toBeGreaterThanOrEqual(1));
      expect(within(getMetricCardByLabel("Blocking")).getByText("2")).toBeInTheDocument();
    });

    it("shows Chunks count", async () => {
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      renderPage();
      await waitFor(() => expect(screen.getAllByText("Chunks").length).toBeGreaterThanOrEqual(1));
      expect(within(getMetricCardByLabel("Chunks")).getByText("1")).toBeInTheDocument();
    });

    it("shows Draft edits count", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
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
      renderPage();
      await waitFor(() => expect(screen.getAllByText("Draft edits").length).toBeGreaterThanOrEqual(1));
      expect(within(getMetricCardByLabel("Draft edits")).getByText("1")).toBeInTheDocument();
    });
  });

  describe("Success State - Metadata", () => {
    it("shows Doc ID, Collection, Source File, Parse Snapshot", async () => {
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      renderPage();
      await waitFor(() => expect(screen.getAllByText("doc-001").length).toBeGreaterThanOrEqual(1));
      expect(screen.getAllByText("coll-001").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("sf-001").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("ps-001").length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Degraded Alert", () => {
    it("shows degraded alert when degraded_parts is non-empty", async () => {
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({ degraded_parts: ["agent_review", "chunks"] })
      );
      renderPage();
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(/partially degraded/i);
      expect(alert).toHaveTextContent(/agent_review, chunks/i);
    });
  });

  describe("Tabs", () => {
    it("renders all 3 tabs: Source, Drafts / Chunks, Agent review", async () => {
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      renderPage();
      await waitFor(() => expect(screen.getByRole("tab", { name: /Source/i })).toBeInTheDocument());
      expect(screen.getByRole("tab", { name: /Drafts \/ Chunks/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /Agent review/i })).toBeInTheDocument();
    });

    it("clicking tabs switches active tab", async () => {
      const user = userEvent.setup();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      renderPage();
      await waitFor(() => expect(screen.getByRole("tab", { name: /Source/i })).toBeInTheDocument());
      const chunksTab = screen.getByRole("tab", { name: /Drafts \/ Chunks/i });
      await user.click(chunksTab);
      await waitFor(() => expect(document.activeElement).toBe(chunksTab));
      const agentTab = screen.getByRole("tab", { name: /Agent review/i });
      await user.click(agentTab);
      await waitFor(() => expect(document.activeElement).toBe(agentTab));
    });

    it("tab content renders mocked child component", async () => {
      const user = userEvent.setup();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      renderPage();
      await waitFor(() => expect(screen.getByTestId("document-viewer-mock")).toBeInTheDocument());
      await user.click(screen.getByRole("tab", { name: /Drafts \/ Chunks/i }));
      await waitFor(() => expect(screen.getByTestId("chunk-editor-mock")).toBeInTheDocument());
      await user.click(screen.getByRole("tab", { name: /Agent review/i }));
      await waitFor(() => expect(screen.getByTestId("agent-review-mock")).toBeInTheDocument());
    });
  });

  describe("Review Cockpit", () => {
    it("renders Approve/Reject/Return buttons when pending", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "pending_review" },
          capabilities: { ...base.capabilities, can_decide_ticket: true },
        })
      );
      renderPage();
      await waitFor(() => expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument());
      expect(screen.getByRole("button", { name: /Reject/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Return/i })).toBeInTheDocument();
    });

    it("hides decision buttons when not pending", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "approved" },
          capabilities: { ...base.capabilities, can_decide_ticket: false },
        })
      );
      renderPage();
      await waitFor(() => expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument());
      expect(screen.queryByRole("button", { name: /Reject/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Return/i })).not.toBeInTheDocument();
    });

    it("entering reason and clicking Approve calls decideTicket with correct payload", async () => {
      const user = userEvent.setup();
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "pending_review" },
          capabilities: { ...base.capabilities, can_decide_ticket: true },
        })
      );
      vi.mocked(api.decideTicket).mockResolvedValue(buildDecideTicketResponse());
      renderPage();
      await waitFor(() => expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument());
      const reasonInput = screen.getByPlaceholderText(/Optional review reason/i);
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

    it("shows success toast after decision and invalidates queries", async () => {
      const user = userEvent.setup();
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "pending_review" },
          capabilities: { ...base.capabilities, can_decide_ticket: true },
        })
      );
      vi.mocked(api.decideTicket).mockResolvedValue(buildDecideTicketResponse());
      const { queryClient } = renderPage();
      await waitFor(() => expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument());
      await user.click(screen.getByRole("button", { name: /Approve/i }));
      await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Review decision submitted"));
      await waitFor(() =>
        expect(queryClient.isFetching({ queryKey: ["document-workspace", "doc-001"] })).toBe(0)
      );
    });

    it("shows error toast when decision fails", async () => {
      const user = userEvent.setup();
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          ticket: { ...base.ticket!, status: "pending_review" },
          capabilities: { ...base.capabilities, can_decide_ticket: true },
        })
      );
      vi.mocked(api.decideTicket).mockRejectedValue(new ApiClientError("DECISION_FAILED", "Server error", 500));
      renderPage();
      await waitFor(() => expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument());
      await user.click(screen.getByRole("button", { name: /Approve/i }));
      await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Server error"));
    });
  });

  describe("Lifecycle Actions", () => {
    it("opens archive dialog and calls archiveDocument with payload", async () => {
      const user = userEvent.setup();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      vi.mocked(api.archiveDocument).mockResolvedValue(buildArchiveDocumentResponse());
      renderPage();
      await waitFor(() => expect(screen.getByRole("button", { name: /Archive Document/i })).toBeInTheDocument());
      await user.click(screen.getByRole("button", { name: /Archive Document/i }));
      await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
      const reasonInput = screen.getByPlaceholderText("Reason");
      await user.type(reasonInput, "Old doc");
      await user.click(screen.getByRole("button", { name: /Confirm/i }));
      await waitFor(() =>
        expect(api.archiveDocument).toHaveBeenCalledWith("doc-001", {
          reason: "Old doc",
          index_profile_id: undefined,
        })
      );
      await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("Archive")));
    });

    it("opens retract dialog and calls retractDocument with payload", async () => {
      const user = userEvent.setup();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      vi.mocked(api.retractDocument).mockResolvedValue(buildRetractDocumentResponse());
      renderPage();
      await waitFor(() => expect(screen.getByRole("button", { name: /Retract Document/i })).toBeInTheDocument());
      await user.click(screen.getByRole("button", { name: /Retract Document/i }));
      await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
      const reasonInput = screen.getByPlaceholderText("Reason");
      await user.type(reasonInput, "Bad content");
      await user.click(screen.getByRole("button", { name: /Confirm/i }));
      await waitFor(() =>
        expect(api.retractDocument).toHaveBeenCalledWith("doc-001", {
          reason: "Bad content",
          index_profile_id: undefined,
        })
      );
      await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("Retract")));
    });

    it("opens reindex dialog and calls reindexDocument with payload including index_profile_id", async () => {
      const user = userEvent.setup();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(workspace());
      vi.mocked(api.reindexDocument).mockResolvedValue(buildReindexDocumentResponse());
      renderPage();
      await waitFor(() => expect(screen.getByRole("button", { name: /Reindex Document/i })).toBeInTheDocument());
      await user.click(screen.getByRole("button", { name: /Reindex Document/i }));
      await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
      const reasonInput = screen.getByPlaceholderText("Reason");
      await user.type(reasonInput, "Rebuild");
      await user.click(screen.getByRole("button", { name: /Confirm/i }));
      await waitFor(() =>
        expect(api.reindexDocument).toHaveBeenCalledWith("doc-001", {
          reason: "Rebuild",
          index_profile_id: "ragflow",
        })
      );
      await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("Reindex")));
    });
  });

  describe("Diagnostics Panel", () => {
    it("shows Task Status, Index Version, Next Action, Failure Stage", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          task: { ...base.task!, status: "published" },
          document: { ...base.document, active_index_version: "v2" },
          ticket: { ...base.ticket!, next_action: "review", failure_stage: "parse" },
        })
      );
      renderPage();
      await waitFor(() => expect(screen.getByText(/Diagnostics/i)).toBeInTheDocument());
      const diagnosticsCard = (screen.getByText(/Diagnostics/i).closest("[data-slot='card']") || screen.getByText(/Diagnostics/i).parentElement) as HTMLElement;
      expect(within(diagnosticsCard).getByText("published")).toBeInTheDocument();
      expect(within(diagnosticsCard!).getByText("v2")).toBeInTheDocument();
      expect(within(diagnosticsCard!).getByText(/Needs Review/i)).toBeInTheDocument();
      expect(within(diagnosticsCard!).getByText(/Parse/i)).toBeInTheDocument();
    });

    it("shows failure_code alert when present", async () => {
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({ ticket: { ...base.ticket!, failure_code: "PARSE_TIMEOUT" } })
      );
      renderPage();
      await waitFor(() => expect(screen.getByText("PARSE_TIMEOUT")).toBeInTheDocument());
    });
  });

  describe("Empty/Missing State", () => {
    it("shows empty state when workspace missing document", async () => {
      const empty = buildDocumentWorkspaceEmptyResponse();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue({ ...empty, document: null as unknown as typeof empty.document });
      renderPage();
      await waitFor(() =>
        expect(screen.getByText("Document workspace not found")).toBeInTheDocument()
      );
    });
  });

  describe("Error State", () => {
    it("shows BackendGap component for 501 errors", async () => {
      vi.mocked(api.getDocumentWorkspace).mockRejectedValue(
        new BackendGapError("GET /api/workbench/documents/doc-001/workspace", "/api/workbench/documents/doc-001/workspace")
      );
      renderPage();
      await waitFor(() => expect(screen.getByText(/后端能力缺口/i)).toBeInTheDocument());
    });

    it("shows error alert for generic errors", async () => {
      vi.mocked(api.getDocumentWorkspace).mockRejectedValue(new ApiClientError("FETCH_FAILED", "Network error", 500));
      renderPage();
      await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
    });
  });

  describe("Boundary State", () => {
    it("renders with very long filename", async () => {
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(buildDocumentWorkspaceBoundaryResponse());
      renderPage();
      await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
      expect(screen.getByRole("heading", { level: 1 }).textContent!.length).toBeGreaterThan(100);
    });

    it("renders with many findings", async () => {
      const manyFindings = Array.from({ length: 50 }, (_, i) => ({
        finding_id: `f-${i}`,
        severity: (i % 2 === 0 ? "critical" : "high") as "critical" | "high",
        category: "category",
        problem_summary: `Problem ${i}`,
        source_quote: `Quote ${i}`,
        evidence_id: `ev-${i}`,
        doc_id: "doc-001",
        source_file_id: "sf-001",
        parse_snapshot_id: "ps-001",
        page_from: 1,
        page_to: 1,
        state: "open" as const,
        confidence: 0.9,
      }));
      const base = workspace();
      vi.mocked(api.getDocumentWorkspace).mockResolvedValue(
        workspace({
          agent_review: {
            ...base.agent_review,
            findings: manyFindings,
          },
        })
      );
      renderPage();
      await waitFor(() => expect(screen.getByText("Findings")).toBeInTheDocument());
      const findingsSection = screen.getByText("Findings").parentElement;
      const blockingSection = screen.getByText("Blocking").parentElement;
      expect(within(findingsSection!).getByText("50")).toBeInTheDocument();
      expect(within(blockingSection!).getByText("50")).toBeInTheDocument();
    });
  });
});
