import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    me: vi.fn(),
    listCollections: vi.fn(),
    listRetrievalProfiles: vi.fn(),
    listQueryRuns: vi.fn(),
    retrieve: vi.fn(),
  } as any,
}));

const mockStoreState: {
  currentCollectionId: string | null;
  setCurrentCollectionId: ReturnType<typeof vi.fn>;
} = {
  currentCollectionId: null,
  setCurrentCollectionId: vi.fn(),
};

vi.mock("@/lib/store", () => ({
  useAppStore: vi.fn((selector?: (state: any) => any) => {
    if (typeof selector === "function") {
      return selector(mockStoreState);
    }
    return mockStoreState;
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

import { workbenchApi } from "@/lib/api/client";
import { useAppStore } from "@/lib/store";
import { toast } from "sonner";
import { BackendGapError, ApiClientError } from "@/lib/api/errors";
import RetrievalPage from "./page";

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

function mockMeResponse() {
  return {
    user_id: "user-001",
    email: "admin@example.com",
    display_name: "Administrator",
    roles: ["knowledge_admin"],
    tenant_id: "tenant-001",
    allowed_collections: ["coll-001"],
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

function mockProfilesResponse() {
  return {
    items: [
      {
        retrieval_profile_id: "rp-001",
        name: "Default Profile",
        description: "Default retrieval profile",
        state: "published",
        config: {},
      },
      {
        retrieval_profile_id: "rp-002",
        name: "Strict Profile",
        description: "Strict retrieval profile",
        state: "published",
        config: {},
      },
    ],
    total: 2,
  };
}

function mockEvidenceItem(overrides?: Record<string, unknown>) {
  return {
    doc_id: "doc-001",
    evidence_id: "ev-001",
    collection_id: "coll-001",
    score: 0.85,
    content: "This is the evidence content for the retrieval result.",
    source_stage: "chunk",
    why_selected: "High relevance to query",
    section_path: ["Section 1", "Subsection A"],
    ...overrides,
  };
}

function mockRetrieveResponse(overrides?: Record<string, unknown>) {
  return {
    query_run_id: "qr-001",
    knowledge_context: {},
    latency_ms: 120,
    trace_id: "trace-001",
    token_budget_used: 450,
    evidence_items: [mockEvidenceItem()],
    ...overrides,
  };
}

function setStoreState(state: {
  currentCollectionId?: string | null;
  setCurrentCollectionId?: ReturnType<typeof vi.fn>;
}) {
  const setCurrentCollectionId = state.setCurrentCollectionId ?? vi.fn();
  mockStoreState.currentCollectionId = state.currentCollectionId ?? null;
  mockStoreState.setCurrentCollectionId = setCurrentCollectionId;
  return { setCurrentCollectionId };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("RetrievalPage", () => {
  let clipboardWriteText = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    clipboardWriteText = vi.fn().mockResolvedValue(undefined);
    // jsdom doesn't have navigator.clipboard; define it safely
    if (!navigator.clipboard) {
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText: clipboardWriteText },
        writable: true,
        configurable: true,
      });
    } else {
      navigator.clipboard.writeText = clipboardWriteText;
    }

    vi.mocked(api.me).mockResolvedValue(mockMeResponse());
    vi.mocked(api.listCollections).mockResolvedValue(mockCollectionsResponse());
    vi.mocked(api.listRetrievalProfiles).mockResolvedValue(mockProfilesResponse());
    vi.mocked(api.listQueryRuns).mockResolvedValue({ items: [], total: 0 });

    setStoreState({ currentCollectionId: "coll-001" });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Header ─────────────────────────────────────────────────────────────

  describe("Header", () => {
    it("renders title and description", async () => {
      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: /检索验证/i })).toBeInTheDocument();
      });

      expect(
        screen.getByText(/验证检索结果。这是上下文工作台——展示证据片段，而非生成答案。/)
      ).toBeInTheDocument();
    });
  });

  // ── Search Form ────────────────────────────────────────────────────────

  describe("Search Form", () => {
    it("renders query input and token budget input", async () => {
      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/查询/i)).toBeInTheDocument();
      });

      expect(screen.getByPlaceholderText(/输入检索查询/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/token 预算/i)).toHaveValue(2000);
    });

    it("renders collection, retrieval profile and debug selects", async () => {
      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        // Base UI Select values don't render as plain text in jsdom;
        // verify the combobox triggers are present instead
        const triggers = screen.getAllByRole("combobox");
        expect(triggers.length).toBeGreaterThanOrEqual(3);
      });
    });

    it("collection select triggers setCurrentCollectionId", async () => {
      const { setCurrentCollectionId } = setStoreState({ currentCollectionId: null });
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getAllByRole("combobox").length).toBeGreaterThanOrEqual(1);
      });

      const collectionTrigger = screen.getAllByRole("combobox")[0];
      await user.click(collectionTrigger);

      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Secondary Collection/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("option", { name: /Secondary Collection/i }));

      await waitFor(() => {
        expect(setCurrentCollectionId).toHaveBeenCalledWith("coll-002");
      });
    });

    it("search button is disabled until collection and profile are selected", async () => {
      setStoreState({ currentCollectionId: null });
      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeDisabled();
      });
    });

    it("pressing Enter in query input triggers search when form is valid", async () => {
      const user = userEvent.setup();
      setStoreState({ currentCollectionId: "coll-001" });
      vi.mocked(api.retrieve).mockResolvedValue(mockRetrieveResponse());

      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeInTheDocument();
      });

      // Select retrieval profile
      const profileTrigger = screen.getAllByRole("combobox")[1];
      await user.click(profileTrigger);
      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Default Profile/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole("option", { name: /Default Profile/i }));

      const queryInput = screen.getByPlaceholderText(/输入检索查询/i);
      await user.type(queryInput, "test query");

      const searchButton = screen.getByRole("button", { name: /检索上下文/i });
      await waitFor(() => expect(searchButton).toBeEnabled());

      await user.type(queryInput, "{Enter}");

      await waitFor(() => {
        expect(api.retrieve).toHaveBeenCalled();
      });
    });
  });

  // ── Alert ──────────────────────────────────────────────────────────────

  describe("Alert", () => {
    it("shows alert when collection is missing", async () => {
      setStoreState({ currentCollectionId: null });
      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(
          screen.getByText(/运行检索前请选择集合和已发布的检索配置/)
        ).toBeInTheDocument();
      });
    });

    it("shows alert when retrieval profile is missing", async () => {
      setStoreState({ currentCollectionId: "coll-001" });
      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(
          screen.getByText(/运行检索前请选择集合和已发布的检索配置/)
        ).toBeInTheDocument();
      });
    });
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("shows searching state while retrieve is in flight", async () => {
      const user = userEvent.setup();
      setStoreState({ currentCollectionId: "coll-001" });
      vi.mocked(api.retrieve).mockImplementation(() => new Promise(() => {}));

      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeInTheDocument();
      });

      const profileTrigger = screen.getAllByRole("combobox")[1];
      await user.click(profileTrigger);
      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Default Profile/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole("option", { name: /Default Profile/i }));

      await user.type(screen.getByPlaceholderText(/输入检索查询/i), "test query");

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeEnabled();
      });

      await user.click(screen.getByRole("button", { name: /检索上下文/i }));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索中/i })).toBeInTheDocument();
      });
    });
  });

  // ── Results Header ─────────────────────────────────────────────────────

  describe("Results Header", () => {
    it("renders results count and expand/collapse buttons", async () => {
      const user = userEvent.setup();
      setStoreState({ currentCollectionId: "coll-001" });
      vi.mocked(api.retrieve).mockResolvedValue(
        mockRetrieveResponse({
          evidence_items: [mockEvidenceItem(), mockEvidenceItem({ evidence_id: "ev-002" })],
        })
      );

      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeInTheDocument();
      });

      const profileTrigger = screen.getAllByRole("combobox")[1];
      await user.click(profileTrigger);
      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Default Profile/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole("option", { name: /Default Profile/i }));

      await user.type(screen.getByPlaceholderText(/输入检索查询/i), "test query");
      await user.click(screen.getByRole("button", { name: /检索上下文/i }));

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: /检索到的证据片段/i })).toBeInTheDocument();
      });

      expect(screen.getByText(/2 项/i)).toBeInTheDocument();
      expect(screen.getByText(/已用 450 Token/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /展开全部/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /收起全部/i })).toBeInTheDocument();
    });
  });

  // ── Evidence Cards ─────────────────────────────────────────────────────

  describe("Evidence Cards", () => {
    async function renderWithResults() {
      const user = userEvent.setup();
      setStoreState({ currentCollectionId: "coll-001" });
      vi.mocked(api.retrieve).mockResolvedValue(
        mockRetrieveResponse({
          evidence_items: [
            mockEvidenceItem({ score: 0.9123 }),
            mockEvidenceItem({ evidence_id: "ev-002", score: 0.5 }),
          ],
        })
      );

      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeInTheDocument();
      });

      const profileTrigger = screen.getAllByRole("combobox")[1];
      await user.click(profileTrigger);
      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Default Profile/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole("option", { name: /Default Profile/i }));

      await user.type(screen.getByPlaceholderText(/输入检索查询/i), "test query");
      await user.click(screen.getByRole("button", { name: /检索上下文/i }));

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: /检索到的证据片段/i })).toBeInTheDocument();
      });

      return { user };
    }

    it("renders index badge and score for each evidence", async () => {
      await renderWithResults();

      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByText("0.9123")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByText("0.5000")).toBeInTheDocument();
    });

    it("renders progress bar based on score", async () => {
      const { container } = render(<></>);
      await renderWithResults();

      const bars = document.querySelectorAll(".bg-gradient-to-r");
      expect(bars.length).toBeGreaterThanOrEqual(2);
    });

    it("copy button shows feedback state when clicked", async () => {
      const { user } = await renderWithResults();

      const copyButtons = screen.getAllByRole("button", { name: /复制/i });
      expect(copyButtons.length).toBeGreaterThanOrEqual(1);

      await user.click(copyButtons[0]);

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith("已复制到剪贴板");
      });

      await waitFor(() => {
        expect(screen.getByText("已复制")).toBeInTheDocument();
      });
    });

    it("expand/collapse toggles expanded details", async () => {
      const { user } = await renderWithResults();

      // Chevron buttons are the only non-disabled buttons with no text content
      const chevronButtons = Array.from(
        document.querySelectorAll('[data-slot="button"]')
      ).filter(
        (btn) =>
          !btn.hasAttribute("disabled") &&
          !(btn as HTMLElement).textContent?.trim()
      ) as HTMLElement[];
      expect(chevronButtons.length).toBeGreaterThanOrEqual(2);
      const firstCardChevron = chevronButtons[0];

      expect(screen.queryByText(/source_stage:/i)).not.toBeInTheDocument();

      await user.click(firstCardChevron);

      await waitFor(() => {
        expect(screen.getByText(/source_stage:/i)).toBeInTheDocument();
      });

      await user.click(firstCardChevron);

      await waitFor(() => {
        expect(screen.queryByText(/source_stage:/i)).not.toBeInTheDocument();
      });
    });

    it("renders metadata lines and content", async () => {
      await renderWithResults();

      // Two evidence cards share some metadata text; use getAllByText
      expect(screen.getAllByText(/doc_id: doc-001/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/evidence_id: ev-001/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/coll-001/i).length).toBeGreaterThanOrEqual(1);
      expect(
        screen.getAllByText("This is the evidence content for the retrieval result.").length
      ).toBeGreaterThanOrEqual(1);
    });

    it("expand all and collapse all buttons toggle all cards", async () => {
      const { user } = await renderWithResults();

      await user.click(screen.getByRole("button", { name: /展开全部/i }));

      await waitFor(() => {
        expect(screen.getAllByText(/source_stage:/i).length).toBe(2);
      });

      await user.click(screen.getByRole("button", { name: /收起全部/i }));

      await waitFor(() => {
        expect(screen.queryByText(/source_stage:/i)).not.toBeInTheDocument();
      });
    });
  });

  // ── Empty State ────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows empty state when retrieve returns no evidence", async () => {
      const user = userEvent.setup();
      setStoreState({ currentCollectionId: "coll-001" });
      vi.mocked(api.retrieve).mockResolvedValue(
        mockRetrieveResponse({ evidence_items: [] })
      );

      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeInTheDocument();
      });

      const profileTrigger = screen.getAllByRole("combobox")[1];
      await user.click(profileTrigger);
      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Default Profile/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole("option", { name: /Default Profile/i }));

      await user.type(screen.getByPlaceholderText(/输入检索查询/i), "test query");
      await user.click(screen.getByRole("button", { name: /检索上下文/i }));

      await waitFor(() => {
        expect(screen.getByText(/无证据片段/i)).toBeInTheDocument();
      });

      expect(
        screen.getByText(/检索返回空结果。请检查查询、集合范围和检索配置。/)
      ).toBeInTheDocument();
    });
  });

  // ── Error State ────────────────────────────────────────────────────────

  describe("Error State", () => {
    it("shows BackendGap component for backend gap errors", async () => {
      const user = userEvent.setup();
      setStoreState({ currentCollectionId: "coll-001" });
      vi.mocked(api.retrieve).mockRejectedValue(
        new BackendGapError("POST /workbench/retrieve", "/api/workbench/retrieve")
      );

      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeInTheDocument();
      });

      const profileTrigger = screen.getAllByRole("combobox")[1];
      await user.click(profileTrigger);
      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Default Profile/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole("option", { name: /Default Profile/i }));

      await user.type(screen.getByPlaceholderText(/输入检索查询/i), "test query");
      await user.click(screen.getByRole("button", { name: /检索上下文/i }));

      await waitFor(() => {
        expect(screen.getByText(/后端能力缺口/i)).toBeInTheDocument();
      });
    });

    it("shows generic error alert for ApiClientError", async () => {
      const user = userEvent.setup();
      setStoreState({ currentCollectionId: "coll-001" });
      vi.mocked(api.retrieve).mockRejectedValue(
        new ApiClientError("RETRIEVE_FAILED", "Search service unavailable", 500)
      );

      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeInTheDocument();
      });

      const profileTrigger = screen.getAllByRole("combobox")[1];
      await user.click(profileTrigger);
      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Default Profile/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole("option", { name: /Default Profile/i }));

      await user.type(screen.getByPlaceholderText(/输入检索查询/i), "test query");
      await user.click(screen.getByRole("button", { name: /检索上下文/i }));

      await waitFor(() => {
        expect(screen.getByText("Search service unavailable")).toBeInTheDocument();
      });
    });

    it("shows generic error alert for plain errors", async () => {
      const user = userEvent.setup();
      setStoreState({ currentCollectionId: "coll-001" });
      vi.mocked(api.retrieve).mockRejectedValue(new Error("Network failure"));

      const Wrapper = createWrapper();
      render(<RetrievalPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /检索上下文/i })).toBeInTheDocument();
      });

      const profileTrigger = screen.getAllByRole("combobox")[1];
      await user.click(profileTrigger);
      await waitFor(() => {
        expect(screen.getByRole("option", { name: /Default Profile/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole("option", { name: /Default Profile/i }));

      await user.type(screen.getByPlaceholderText(/输入检索查询/i), "test query");
      await user.click(screen.getByRole("button", { name: /检索上下文/i }));

      await waitFor(() => {
        // String(new Error("...")) produces "Error: ..."
        expect(screen.getByText("Error: Network failure")).toBeInTheDocument();
      });
    });
  });
});
