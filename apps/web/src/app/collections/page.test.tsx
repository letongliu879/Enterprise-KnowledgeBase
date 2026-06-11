import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, className, onClick }: any) => (
    <a href={href} className={className} onClick={onClick}>{children}</a>
  ),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    me: vi.fn(),
    listCollections: vi.fn(),
    createCollection: vi.fn(),
  } as any,
}));

const storeSetCurrentCollectionId = vi.fn();

vi.mock("@/lib/store", () => ({
  useAppStore: Object.assign(
    vi.fn(() => ({
      currentCollectionId: null,
      setCurrentCollectionId: storeSetCurrentCollectionId,
      demoToken: null,
      setDemoToken: vi.fn(),
      accessScope: null,
      setAccessScope: vi.fn(),
      demoApiKey: null,
      setDemoApiKey: vi.fn(),
    })),
    {
      getState: vi.fn(() => ({
        currentCollectionId: null,
        setCurrentCollectionId: storeSetCurrentCollectionId,
        demoToken: null,
        setDemoToken: vi.fn(),
        accessScope: null,
        setAccessScope: vi.fn(),
        demoApiKey: null,
        setDemoApiKey: vi.fn(),
      })),
      setState: vi.fn(),
      subscribe: vi.fn(() => () => {}),
    }
  ),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import { useAppStore } from "@/lib/store";
import { toast } from "sonner";
import CollectionsPage from "./page";

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
        description: "",
        lifecycle_state: "archived",
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

function mockCollectionsEmptyResponse() {
  return { items: [], total: 0 };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("CollectionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAppStore).mockReturnValue({
      currentCollectionId: null,
      setCurrentCollectionId: storeSetCurrentCollectionId,
      demoToken: null,
      setDemoToken: vi.fn(),
      accessScope: null,
      setAccessScope: vi.fn(),
      demoApiKey: null,
      setDemoApiKey: vi.fn(),
    } as any);
    vi.mocked(api.me).mockResolvedValue(mockMeResponse());
    vi.mocked(api.listCollections).mockResolvedValue(mockCollectionsResponse());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Header ─────────────────────────────────────────────────────────────

  it("renders header title, subtitle and create button", async () => {
    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("知识库集合")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/管理知识库集合。上传必须归属到某个集合。/)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /新建集合/ })).toBeInTheDocument();
  });

  // ── Loading State ──────────────────────────────────────────────────────

  it("renders 3 skeleton cards while collections are loading", async () => {
    vi.mocked(api.listCollections).mockImplementation(() => new Promise(() => {}));

    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
      expect(skeletons.length).toBeGreaterThanOrEqual(3);
    });
  });

  // ── Success State - Collection Cards ───────────────────────────────────

  it("renders collection cards with name, badge, id, description and tenant", async () => {
    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Default Collection")).toBeInTheDocument();
    });

    expect(screen.getByText("Secondary Collection")).toBeInTheDocument();
    expect(screen.getByText("coll-001")).toBeInTheDocument();
    expect(screen.getByText("coll-002")).toBeInTheDocument();
    expect(
      screen.getByText("Primary knowledge base collection")
    ).toBeInTheDocument();
    expect(screen.getByText("无描述")).toBeInTheDocument();
    expect(screen.getAllByText("租户: tenant-001").length).toBeGreaterThanOrEqual(2);

    // Lifecycle state badges
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("archived")).toBeInTheDocument();
  });

  it("shows hover overlay on collection cards", async () => {
    const Wrapper = createWrapper();
    const { container } = render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Default Collection")).toBeInTheDocument();
    });

    const overlays = container.querySelectorAll(
      ".bg-gradient-to-br.from-primary\\/\\[0\\.02\\]"
    );
    expect(overlays.length).toBeGreaterThanOrEqual(2);
  });

  it("selecting a collection updates the store and shows a success toast", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Default Collection")).toBeInTheDocument();
    });

    const selectButton = screen.getAllByRole("button", {
      name: /选择用于上传/,
    })[0];
    await user.click(selectButton);

    expect(storeSetCurrentCollectionId).toHaveBeenCalledWith("coll-001");
    expect(vi.mocked(toast.success)).toHaveBeenCalledWith(
      "已选择集合: Default Collection"
    );
  });

  // ── Create Dialog ──────────────────────────────────────────────────────

  it("opens the create dialog when clicking the create button", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /新建集合/ })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /新建集合/ }));

    expect(screen.getByText("创建集合")).toBeInTheDocument();
    expect(screen.getByLabelText(/集合 ID/)).toBeInTheDocument();
    expect(screen.getByLabelText(/名称/)).toBeInTheDocument();
    expect(screen.getByLabelText(/描述/)).toBeInTheDocument();
  });

  it("validates required fields and disables submit until they are filled", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /新建集合/ })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /新建集合/ }));

    const submitButton = screen.getByRole("button", { name: /^创建$/ });
    expect(submitButton).toBeDisabled();

    await user.type(screen.getByLabelText(/集合 ID/), "coll-new");
    expect(submitButton).toBeDisabled();

    await user.type(screen.getByLabelText(/名称/), "New Collection");
    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
  });

  it("submits the create form, refreshes list, closes dialog, resets form and toasts success", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createCollection).mockResolvedValue({
      collection_id: "coll-new",
    });

    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /新建集合/ })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /新建集合/ }));

    await user.type(screen.getByLabelText(/集合 ID/), "coll-new");
    await user.type(screen.getByLabelText(/名称/), "New Collection");
    await user.type(screen.getByLabelText(/描述/), "A brand new collection");

    await user.click(screen.getByRole("button", { name: /^创建$/ }));

    await waitFor(() => {
      expect(api.createCollection).toHaveBeenCalled();
    });
    const [callArgs] = api.createCollection.mock.calls[0];
    expect(callArgs).toMatchObject({
      collection_id: "coll-new",
      name: "New Collection",
      description: "A brand new collection",
      lifecycle_state: "active",
      tenant_id: "tenant-001",
    });

    await waitFor(() => {
      expect(vi.mocked(toast.success)).toHaveBeenCalledWith("集合已创建");
    });

    // List should be refreshed (called at least twice: initial + invalidate)
    await waitFor(() => {
      expect(api.listCollections).toHaveBeenCalledTimes(2);
    });

    // Dialog should close (heading removed from accessible tree)
    await waitFor(() => {
      expect(
        screen.queryByRole("heading", { name: "创建集合" })
      ).not.toBeInTheDocument();
    });

    // Reopen dialog to verify form reset
    await user.click(screen.getByRole("button", { name: /新建集合/ }));
    await waitFor(() => {
      expect(screen.getByLabelText(/集合 ID/)).toBeInTheDocument();
    });
    expect((screen.getByLabelText(/集合 ID/) as HTMLInputElement).value).toBe(
      ""
    );
    expect((screen.getByLabelText(/名称/) as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText(/描述/) as HTMLInputElement).value).toBe("");
  });

  it("shows BackendGap when create returns a backend gap error", async () => {
    const user = userEvent.setup();
    const { BackendGapError } = await import("@/lib/api/errors");
    vi.mocked(api.createCollection).mockRejectedValue(
      new BackendGapError("创建集合", "/api/workbench/collections")
    );

    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /新建集合/ })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /新建集合/ }));

    await user.type(screen.getByLabelText(/集合 ID/), "coll-gap");
    await user.type(screen.getByLabelText(/名称/), "Gap Collection");

    await user.click(screen.getByRole("button", { name: /^创建$/ }));

    await waitFor(() => {
      expect(screen.getByText(/后端能力缺口/)).toBeInTheDocument();
    });

    expect(screen.getByText("该功能依赖的后端 API 尚未实现。")).toBeInTheDocument();
    expect(
      screen.getByText("/api/workbench/collections")
    ).toBeInTheDocument();
  });

  // ── Empty State ────────────────────────────────────────────────────────

  it("shows empty state when no collections exist and create action opens dialog", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listCollections).mockResolvedValue(mockCollectionsEmptyResponse());

    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("暂无集合")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/创建第一个集合以开始上传文档。/)
    ).toBeInTheDocument();

    const createButton = screen.getByRole("button", { name: /创建集合/ });
    expect(createButton).toBeInTheDocument();

    await user.click(createButton);
    expect(screen.getByText("创建集合")).toBeInTheDocument();
  });

  // ── Error State ────────────────────────────────────────────────────────

  it("shows generic error alert when listCollections fails", async () => {
    const { ApiClientError } = await import("@/lib/api/errors");
    vi.mocked(api.listCollections).mockRejectedValue(
      new ApiClientError("NETWORK_ERROR", "Network error", 500)
    );

    const Wrapper = createWrapper();
    render(<CollectionsPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeInTheDocument();
    });
  });
});
