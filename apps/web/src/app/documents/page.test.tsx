import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { toast } from "sonner";

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

vi.mock("@/lib/store", () => ({
  useAppStore: {
    getState: () => ({
      demoToken: null,
      currentCollectionId: null,
      accessScope: null,
      demoApiKey: null,
    }),
    subscribe: () => () => {},
    setState: vi.fn(),
  },
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    me: vi.fn(),
    listCollections: vi.fn(),
    listDocuments: vi.fn(),
    batchArchiveDocuments: vi.fn(),
    batchRetractDocuments: vi.fn(),
    batchReindexDocuments: vi.fn(),
  } as any,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

import { workbenchApi } from "@/lib/api/client";
import DocumentsPage from "./page";

const api = workbenchApi as any;

// ── Helpers ──────────────────────────────────────────────────────────────

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
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

function mockCollectionsResponse() {
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
  };
}

function mockDocumentItem(overrides?: Record<string, unknown>) {
  return {
    doc_id: "doc-001",
    tenant_id: "tenant-001",
    collection_id: "coll-001",
    source_file_id: "sf-001",
    parse_snapshot_id: "ps-001",
    published_doc_id: null,
    upload_id: "up-001",
    filename: "document.pdf",
    mime_type: "application/pdf",
    document_state: "active",
    publish_state: null,
    active_index_version: null,
    chunk_count: 42,
    page_count: 12,
    parser_profile_id: "parser-default",
    parser_profile_name: "Default Parser",
    projection_updated_at: new Date().toISOString(),
    is_stale: false,
    degraded_reason: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: new Date().toISOString(),
    ticket_id: "ticket-001",
    ticket_status: "pending_review",
    task_status: "published",
    has_source_file: true,
    has_parse_snapshot: true,
    has_active_index: true,
    latest_updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function mockListDocumentsResponse() {
  return {
    items: [
      mockDocumentItem(),
      mockDocumentItem({
        doc_id: "doc-002",
        collection_id: "coll-002",
        filename: "report.docx",
        document_state: "archived",
        ticket_status: "approved",
        has_active_index: false,
        is_stale: true,
        degraded_reason: "Source file missing",
        chunk_count: 10,
        page_count: 5,
      }),
      mockDocumentItem({
        doc_id: "doc-003",
        collection_id: "coll-001",
        filename: "slides.pptx",
        document_state: "pending",
        ticket_status: "rejected",
        has_active_index: false,
        is_stale: false,
        chunk_count: 8,
        page_count: 20,
      }),
      mockDocumentItem({
        doc_id: "doc-004",
        collection_id: "coll-002",
        filename: "sheet.xlsx",
        document_state: "active",
        ticket_status: null,
        has_active_index: true,
        is_stale: false,
        chunk_count: 100,
        page_count: 3,
      }),
    ],
    total: 4,
  };
}

function mockBatchResult(overrides?: Record<string, unknown>) {
  return {
    total: 2,
    succeeded: 1,
    failed: 1,
    items: [
      { doc_id: "doc-001", success: true, new_state: "archived" },
      { doc_id: "doc-002", success: false, error_code: "ALREADY_ARCHIVED", error_message: "Already archived" },
    ],
    ...overrides,
  };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("DocumentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.me).mockResolvedValue(mockMeResponse());
    vi.mocked(api.listCollections).mockResolvedValue(mockCollectionsResponse());
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("renders skeleton cards while documents are loading", async () => {
      vi.mocked(api.listDocuments).mockImplementation(() => new Promise(() => {}));

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
        expect(skeletons.length).toBeGreaterThanOrEqual(4);
      });
    });
  });

  // ── Success State - Header ─────────────────────────────────────────────

  describe("Success State - Header", () => {
    it("renders page title and subtitle", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: /Document Library/i })).toBeInTheDocument();
      });

      expect(
        screen.getByText(/Manage document health, review linkage, index status, and lifecycle operations/i)
      ).toBeInTheDocument();
    });

    it("renders admin badge for knowledge_admin", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/Admin lifecycle enabled/i)).toBeInTheDocument();
      });
    });

    it("renders admin badge for platform_admin", async () => {
      vi.mocked(api.me).mockResolvedValue(mockMeResponse({ roles: ["platform_admin"] }));
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/Admin lifecycle enabled/i)).toBeInTheDocument();
      });
    });

    it("does not render admin badge for non-admin", async () => {
      vi.mocked(api.me).mockResolvedValue(mockMeResponse({ roles: ["viewer"] }));
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.queryByText(/Admin lifecycle enabled/i)).not.toBeInTheDocument();
    });
  });

  // ── Success State - Document Cards ─────────────────────────────────────

  describe("Success State - Document Cards", () => {
    it("renders document cards with filename", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("report.docx")).toBeInTheDocument();
      expect(screen.getByText("slides.pptx")).toBeInTheDocument();
      expect(screen.getByText("sheet.xlsx")).toBeInTheDocument();
    });

    it("falls back to doc_id when filename is missing", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue({
        items: [mockDocumentItem({ filename: "" })],
        total: 1,
      });

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("doc-001")).toBeInTheDocument();
      });
    });

    it("shows file type icons via aria-hidden svgs", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      const { container } = render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const svgs = container.querySelectorAll("svg");
      expect(svgs.length).toBeGreaterThanOrEqual(4);
    });

    it("shows state badges for all document states", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getAllByText("Active").length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("Archived")).toBeInTheDocument();
      expect(screen.getByText("Pending")).toBeInTheDocument();
    });

    it("shows review badges when ticket_status is present", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText(/Review pending_review/i)).toBeInTheDocument();
      expect(screen.getByText(/Review approved/i)).toBeInTheDocument();
      expect(screen.getByText(/Review rejected/i)).toBeInTheDocument();
    });

    it("shows indexed badge for documents with active index", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getAllByText("Indexed").length).toBeGreaterThanOrEqual(2);
    });

    it("shows collection, chunks, pages, and completeness info", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const collectionBadges = screen.getAllByText("coll-001").filter((el) =>
        el.classList.contains("text-[10px]")
      );
      expect(collectionBadges.length).toBeGreaterThanOrEqual(2);
      expect(screen.getAllByText("coll-002").filter((el) =>
        el.classList.contains("text-[10px]")
      ).length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("42 chunks")).toBeInTheDocument();
      expect(screen.getByText("12 pages")).toBeInTheDocument();
      expect(screen.getAllByText("Complete").length).toBeGreaterThanOrEqual(1);
    });

    it("shows Partial completeness when source or snapshot missing", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue({
        items: [mockDocumentItem({ has_source_file: false })],
        total: 1,
      });

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("Partial")).toBeInTheDocument();
    });

    it("shows relative time for latest_updated_at", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      expect(screen.getAllByText(/just now|m ago|h ago|d ago|\d{4}\/\d{1,2}\/\d{1,2}/i).length).toBeGreaterThanOrEqual(1);
    });

    it("shows stale badge for stale documents", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("STALE")).toBeInTheDocument();
      });
    });

    it("shows degraded reason when present", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Source file missing")).toBeInTheDocument();
      });
    });
  });

  // ── Filters ────────────────────────────────────────────────────────────

  describe("Filters", () => {
    it("filters by search query (filename)", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search by filename or doc id/i);
      await user.type(searchInput, "report");

      await waitFor(() => {
        expect(screen.queryByText("document.pdf")).not.toBeInTheDocument();
        expect(screen.getByText("report.docx")).toBeInTheDocument();
      });
    });

    it("filters by collection", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const collectionTrigger = screen.getAllByRole("combobox")[0];
      await user.click(collectionTrigger);

      await waitFor(() => {
        expect(screen.getByText("Default Collection")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Default Collection"));

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
        expect(screen.queryByText("report.docx")).not.toBeInTheDocument();
      });
    });

    it("filters by state", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const stateTrigger = screen.getAllByRole("combobox")[1];
      await user.click(stateTrigger);

      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const archivedOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("Archived")
      );
      expect(archivedOption).toBeDefined();
      await user.click(archivedOption!);

      await waitFor(() => {
        expect(screen.queryByText("document.pdf")).not.toBeInTheDocument();
        expect(screen.getByText("report.docx")).toBeInTheDocument();
      });
    });

    it("filters by review status", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const reviewTrigger = screen.getAllByRole("combobox")[2];
      await user.click(reviewTrigger);

      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const approvedOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("Approved")
      );
      expect(approvedOption).toBeDefined();
      await user.click(approvedOption!);

      await waitFor(() => {
        expect(screen.queryByText("document.pdf")).not.toBeInTheDocument();
        expect(screen.getByText("report.docx")).toBeInTheDocument();
      });
    });

    it("filters by file type", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const typeTrigger = screen.getAllByRole("combobox")[3];
      await user.click(typeTrigger);

      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const pdfOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("PDF")
      );
      expect(pdfOption).toBeDefined();
      await user.click(pdfOption!);

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
        expect(screen.queryByText("report.docx")).not.toBeInTheDocument();
      });
    });

    it("filters by stale status", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const staleTrigger = screen.getAllByRole("combobox")[4];
      await user.click(staleTrigger);

      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const staleOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("Stale only")
      );
      expect(staleOption).toBeDefined();
      await user.click(staleOption!);

      await waitFor(() => {
        expect(screen.queryByText("document.pdf")).not.toBeInTheDocument();
        expect(screen.getByText("report.docx")).toBeInTheDocument();
      });
    });

    it("filters by index status", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const indexTrigger = screen.getAllByRole("combobox")[5];
      await user.click(indexTrigger);

      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const indexedOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("Indexed")
      );
      expect(indexedOption).toBeDefined();
      await user.click(indexedOption!);

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
        expect(screen.queryByText("report.docx")).not.toBeInTheDocument();
      });
    });

    it("combines multiple filters", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const stateTrigger = screen.getAllByRole("combobox")[1];
      await user.click(stateTrigger);

      await waitFor(() => {
        const options = screen.getAllByRole("option");
        expect(options.length).toBeGreaterThan(0);
      });

      const activeOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("Active")
      );
      await user.click(activeOption!);

      const indexTrigger = screen.getAllByRole("combobox")[5];
      await user.click(indexTrigger);

      await waitFor(() => {
        expect(screen.getAllByRole("option").length).toBeGreaterThan(0);
      });

      const indexedOption = screen.getAllByRole("option").find((opt) =>
        opt.textContent?.includes("Indexed")
      );
      await user.click(indexedOption!);

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
        expect(screen.getByText("sheet.xlsx")).toBeInTheDocument();
        expect(screen.queryByText("report.docx")).not.toBeInTheDocument();
        expect(screen.queryByText("slides.pptx")).not.toBeInTheDocument();
      });
    });
  });

  // ── Bulk Selection ─────────────────────────────────────────────────────

  describe("Bulk Selection", () => {
    it("shows bulk action bar when documents are selected", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      expect(checkboxes.length).toBeGreaterThanOrEqual(2);

      await user.click(checkboxes[1]);

      await waitFor(() => {
        expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /Archive/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Retract/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reindex/i })).toBeInTheDocument();
    });

    it("selects all visible documents with select-all checkbox", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      await user.click(checkboxes[0]);

      await waitFor(() => {
        expect(screen.getByText(/4 selected/i)).toBeInTheDocument();
      });
    });

    it("deselects all visible documents when select-all is toggled off", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      await user.click(checkboxes[0]);

      await waitFor(() => {
        expect(screen.getByText(/4 selected/i)).toBeInTheDocument();
      });

      await user.click(checkboxes[0]);

      await waitFor(() => {
        expect(screen.queryByText(/selected/i)).not.toBeInTheDocument();
      });
    });

    it("disables checkboxes for non-admin users", async () => {
      vi.mocked(api.me).mockResolvedValue(mockMeResponse({ roles: ["viewer"] }));
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      expect(checkboxes[0]).toBeDisabled();
    });
  });

  // ── Batch Actions ──────────────────────────────────────────────────────

  describe("Batch Actions", () => {
    it("opens archive dialog and calls batchArchiveDocuments", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());
      vi.mocked(api.batchArchiveDocuments).mockResolvedValue(mockBatchResult());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      await user.click(checkboxes[1]);

      await waitFor(() => {
        expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /Archive/i }));

      await waitFor(() => {
        expect(screen.getByText(/Archive selected documents/i)).toBeInTheDocument();
      });

      const reasonInput = screen.getByPlaceholderText(/Reason/i);
      await user.type(reasonInput, "End of life");

      await user.click(screen.getByRole("button", { name: /Confirm/i }));

      await waitFor(() => {
        expect(api.batchArchiveDocuments).toHaveBeenCalledWith({
          doc_ids: expect.arrayContaining(["doc-001"]),
          reason: "End of life",
        });
      });

      expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("Batch completed"));
    });

    it("opens retract dialog and calls batchRetractDocuments", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());
      vi.mocked(api.batchRetractDocuments).mockResolvedValue(mockBatchResult());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      await user.click(checkboxes[1]);

      await waitFor(() => {
        expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /Retract/i }));

      await waitFor(() => {
        expect(screen.getByText(/Retract selected documents/i)).toBeInTheDocument();
      });

      const reasonInput = screen.getByPlaceholderText(/Reason/i);
      await user.type(reasonInput, "Compliance");

      await user.click(screen.getByRole("button", { name: /Confirm/i }));

      await waitFor(() => {
        expect(api.batchRetractDocuments).toHaveBeenCalledWith({
          doc_ids: expect.arrayContaining(["doc-001"]),
          reason: "Compliance",
        });
      });
    });

    it("opens reindex dialog and calls batchReindexDocuments with profile id", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());
      vi.mocked(api.batchReindexDocuments).mockResolvedValue(mockBatchResult());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      await user.click(checkboxes[1]);

      await waitFor(() => {
        expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /Reindex/i }));

      await waitFor(() => {
        expect(screen.getByText(/Reindex selected documents/i)).toBeInTheDocument();
      });

      const profileInput = screen.getByPlaceholderText(/Index profile id/i);
      await user.clear(profileInput);
      await user.type(profileInput, "custom-profile");

      const reasonInput = screen.getByPlaceholderText(/Reason/i);
      await user.type(reasonInput, "Refresh index");

      await user.click(screen.getByRole("button", { name: /Confirm/i }));

      await waitFor(() => {
        expect(api.batchReindexDocuments).toHaveBeenCalledWith({
          doc_ids: expect.arrayContaining(["doc-001"]),
          reason: "Refresh index",
          index_profile_id: "custom-profile",
        });
      });
    });

    it("renders batch result panel after successful action", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());
      vi.mocked(api.batchArchiveDocuments).mockResolvedValue(mockBatchResult());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      await user.click(checkboxes[1]);

      await waitFor(() => {
        expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /Archive/i }));

      await waitFor(() => {
        expect(screen.getByText(/Archive selected documents/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /Confirm/i }));

      await waitFor(() => {
        expect(screen.getByText(/Total 2/i)).toBeInTheDocument();
        expect(screen.getByText(/Succeeded 1/i)).toBeInTheDocument();
        expect(screen.getByText(/Failed 1/i)).toBeInTheDocument();
        expect(screen.getByText("ALREADY_ARCHIVED")).toBeInTheDocument();
      });
    });

    it("shows error toast when batch action fails", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());
      vi.mocked(api.batchArchiveDocuments).mockRejectedValue(new Error("Server error"));

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole("checkbox");
      await user.click(checkboxes[1]);

      await waitFor(() => {
        expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /Archive/i }));

      await waitFor(() => {
        expect(screen.getByText(/Archive selected documents/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /Confirm/i }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Server error");
      });
    });
  });

  // ── Empty State ────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows empty state when no documents exist", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue({ items: [], total: 0 });

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "No documents" })).toBeInTheDocument();
      });

      expect(
        screen.getByText(/No documents match the current filters/i)
      ).toBeInTheDocument();
    });

    it("shows empty state when filters match no documents", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue(mockListDocumentsResponse());

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("document.pdf")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search by filename or doc id/i);
      await user.type(searchInput, "nonexistent-query-xyz");

      await waitFor(() => {
        expect(screen.getByText(/No documents match/i)).toBeInTheDocument();
      });
    });
  });

  // ── Error State ────────────────────────────────────────────────────────

  describe("Error State", () => {
    it("shows error message when documents API fails", async () => {
      vi.mocked(api.listDocuments).mockRejectedValue(new Error("Network error"));

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();
      });
    });

    it("does not render skeleton after error", async () => {
      vi.mocked(api.listDocuments).mockRejectedValue(new Error("Network error"));

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();
      });

      expect(document.querySelector('[data-slot="skeleton"]')).not.toBeInTheDocument();
    });

    it("shows BackendGap when API returns 501", async () => {
      const { BackendGapError } = await import("@/lib/api/errors");
      vi.mocked(api.listDocuments).mockRejectedValue(
        new BackendGapError("GET /workbench/documents", "/api/workbench/documents", "Not implemented")
      );

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/后端能力缺口/i)).toBeInTheDocument();
      });
    });
  });

  // ── Boundary State ─────────────────────────────────────────────────────

  describe("Boundary State", () => {
    it("renders document with very long filename without crashing", async () => {
      vi.mocked(api.listDocuments).mockResolvedValue({
        items: [mockDocumentItem({ filename: "a".repeat(520) })],
        total: 1,
      });

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });
    });

    it("renders many documents without crashing", async () => {
      const manyDocs = Array.from({ length: 50 }, (_, i) =>
        mockDocumentItem({
          doc_id: `doc-${String(i).padStart(3, "0")}`,
          filename: `file-${i}.pdf`,
          collection_id: i % 2 === 0 ? "coll-001" : "coll-002",
          document_state: i % 3 === 0 ? "active" : i % 3 === 1 ? "pending" : "archived",
        })
      );

      vi.mocked(api.listDocuments).mockResolvedValue({ items: manyDocs, total: 50 });

      const Wrapper = createWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("file-0.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("file-49.pdf")).toBeInTheDocument();
    });
  });
});
