import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    listApiKeys: vi.fn(),
    getApiKeyDetail: vi.fn(),
    createApiKey: vi.fn(),
    updateApiKey: vi.fn(),
    deleteApiKey: vi.fn(),
    getApiKeyUsage: vi.fn(),
  } as any,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import { toast } from "sonner";

import { ApiKeysPage } from "./api-keys-page";

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

function mockApiKeysResponse(overrides?: Record<string, unknown>) {
  return {
    items: [
      {
        api_key_id: "ak-001",
        name: "Production API Key",
        key_prefix: "ak_prod...",
        state: "active",
        permissions: ["read", "search"],
        collection_ids: ["coll-001"],
        expires_at: "2025-12-31T23:59:59Z",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-06-01T00:00:00Z",
        last_used_at: "2024-06-10T12:00:00Z",
      },
      {
        api_key_id: "ak-002",
        name: "Development API Key",
        key_prefix: "ak_dev...",
        state: "active",
        permissions: ["read", "search", "upload"],
        collection_ids: ["coll-001", "coll-002"],
        expires_at: null,
        created_at: "2024-03-01T00:00:00Z",
        updated_at: "2024-03-01T00:00:00Z",
        last_used_at: null,
      },
    ],
    total: 2,
    ...overrides,
  };
}

function mockApiKeysEmptyResponse() {
  return { items: [], total: 0 };
}

function mockApiKeysBoundaryResponse() {
  return {
    items: [
      {
        api_key_id: "ak-boundary",
        name: "a".repeat(520),
        key_prefix: "ak_boundary...",
        state: "active",
        permissions: ["read", "search", "upload", "delete", "admin", "manage"],
        collection_ids: ["coll-001", "coll-002", "coll-003", "coll-004", "coll-005"],
        expires_at: null,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-06-01T00:00:00Z",
        last_used_at: null,
      },
    ],
    total: 1,
  };
}

function mockApiKeyDetailResponse(overrides?: Record<string, unknown>) {
  return {
    api_key_id: "ak-001",
    name: "Production API Key",
    key_prefix: "ak_prod...",
    state: "active",
    permissions: ["read", "search"],
    collection_ids: ["coll-001"],
    expires_at: "2025-12-31T23:59:59Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    last_used_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

function mockCreateApiKeyResponse(overrides?: Record<string, unknown>) {
  return {
    api_key_id: "ak-new-001",
    name: "New API Key",
    key_prefix: "ak_new...",
    full_key: "ak_new_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    state: "active",
    permissions: ["read"],
    collection_ids: ["coll-001"],
    expires_at: null,
    created_at: "2024-06-10T12:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    last_used_at: null,
    ...overrides,
  };
}

function mockUpdateApiKeyResponse(overrides?: Record<string, unknown>) {
  return {
    api_key_id: "ak-001",
    name: "Updated API Key",
    key_prefix: "ak_prod...",
    state: "active",
    permissions: ["read", "search", "upload"],
    collection_ids: ["coll-001", "coll-002"],
    expires_at: "2025-12-31T23:59:59Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    last_used_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

function mockDeleteApiKeyResponse() {
  return { api_key_id: "ak-001", deleted: true };
}

function mockApiKeyUsageResponse(overrides?: Record<string, unknown>) {
  return {
    api_key_id: "ak-001",
    total_requests: 15420,
    total_tokens: 3847500,
    qps_peak: 45.2,
    last_used_at: "2024-06-10T12:00:00Z",
    daily_stats: [
      { date: "2024-06-08", requests: 5200, tokens: 1250000 },
      { date: "2024-06-09", requests: 4800, tokens: 1100000 },
      { date: "2024-06-10", requests: 5420, tokens: 1497500 },
    ],
    ...overrides,
  };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("ApiKeysPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading ────────────────────────────────────────────────────────────

  describe("API Keys Page - Loading", () => {
    it("shows skeleton while loading", async () => {
      vi.mocked(api.listApiKeys).mockImplementation(
        () => new Promise(() => {})
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId("api-key-skeleton")).toBeInTheDocument();
      });
    });
  });

  // ── Success ────────────────────────────────────────────────────────────

  describe("API Keys Page - Success", () => {
    it("renders list of API keys with names, prefixes, states, permissions", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      expect(screen.getByText("Development API Key")).toBeInTheDocument();
      expect(screen.getByText("ak_prod...")).toBeInTheDocument();
      expect(screen.getByText("ak_dev...")).toBeInTheDocument();
    });

    it("shows active/revoked badge states", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue({
        ...mockApiKeysResponse(),
        items: [
          mockApiKeysResponse().items[0],
          { ...mockApiKeysResponse().items[1], state: "revoked" },
        ],
      } as any);

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      expect(screen.getByText("active")).toBeInTheDocument();
      expect(screen.getByText("revoked")).toBeInTheDocument();
    });

    it("shows expiration dates (or 永不过期)", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      expect(screen.getByText(/2025-12-31/)).toBeInTheDocument();
      expect(screen.getByText(/永不过期/)).toBeInTheDocument();
    });

    it("shows last used time (or 从未使用)", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      expect(screen.getByText(/从未使用/)).toBeInTheDocument();
    });

    it("clicking a key opens detail modal", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );
      vi.mocked(api.getApiKeyDetail).mockResolvedValue(
        mockApiKeyDetailResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Production API Key"));

      await waitFor(() => {
        expect(screen.getByTestId("api-key-detail-dialog")).toBeInTheDocument();
      });
    });
  });

  // ── Create ─────────────────────────────────────────────────────────────

  describe("API Keys Page - Create", () => {
    it("clicking 创建密钥 opens create modal", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const createBtn = screen.getByRole("button", { name: /创建密钥/i });
      await user.click(createBtn);

      await waitFor(() => {
        expect(screen.getByTestId("create-api-key-dialog")).toBeInTheDocument();
      });
    });

    it("filling form and submitting creates key", async () => {
      vi.mocked(api.listApiKeys)
        .mockResolvedValueOnce(mockApiKeysResponse() as any)
        .mockResolvedValueOnce({
          ...mockApiKeysResponse(),
          items: [
            ...mockApiKeysResponse().items,
            {
              api_key_id: "ak-new-001",
              name: "New API Key",
              key_prefix: "ak_new...",
              state: "active",
              permissions: ["read"],
              collection_ids: ["coll-001"],
              expires_at: null,
              created_at: "2024-06-10T12:00:00Z",
              updated_at: "2024-06-10T12:00:00Z",
              last_used_at: null,
            },
          ],
          total: 3,
        } as any);

      vi.mocked(api.createApiKey).mockResolvedValue(
        mockCreateApiKeyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /创建密钥/i }));

      await waitFor(() => {
        expect(screen.getByTestId("create-api-key-dialog")).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/名称/i), "New API Key");

      await user.click(screen.getByRole("button", { name: /提交|创建|保存/i }));

      await waitFor(() => {
        expect(api.createApiKey).toHaveBeenCalledTimes(1);
      });

      expect(api.createApiKey).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "New API Key",
        })
      );
    });

    it("new key full value is displayed (copyable)", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );
      vi.mocked(api.createApiKey).mockResolvedValue(
        mockCreateApiKeyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /创建密钥/i }));

      await waitFor(() => {
        expect(screen.getByTestId("create-api-key-dialog")).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/名称/i), "New API Key");
      await user.click(screen.getByRole("button", { name: /提交|创建|保存/i }));

      await waitFor(() => {
        expect(
          screen.getByText("ak_new_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        ).toBeInTheDocument();
      });
    });

    it("after creation, list refreshes", async () => {
      vi.mocked(api.listApiKeys)
        .mockResolvedValueOnce(mockApiKeysResponse() as any)
        .mockResolvedValueOnce({
          ...mockApiKeysResponse(),
          items: [
            ...mockApiKeysResponse().items,
            {
              api_key_id: "ak-new-001",
              name: "New API Key",
              key_prefix: "ak_new...",
              state: "active",
              permissions: ["read"],
              collection_ids: ["coll-001"],
              expires_at: null,
              created_at: "2024-06-10T12:00:00Z",
              updated_at: "2024-06-10T12:00:00Z",
              last_used_at: null,
            },
          ],
          total: 3,
        } as any);

      vi.mocked(api.createApiKey).mockResolvedValue(
        mockCreateApiKeyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /创建密钥/i }));

      await waitFor(() => {
        expect(screen.getByTestId("create-api-key-dialog")).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/名称/i), "New API Key");
      await user.click(screen.getByRole("button", { name: /提交|创建|保存/i }));

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByText("New API Key")).toBeInTheDocument();
      });
    });
  });

  // ── Update ─────────────────────────────────────────────────────────────

  describe("API Keys Page - Update", () => {
    it("clicking edit opens edit modal", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );
      vi.mocked(api.getApiKeyDetail).mockResolvedValue(
        mockApiKeyDetailResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button", { name: /编辑/i });
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("edit-api-key-dialog")).toBeInTheDocument();
      });
    });

    it("changing name and saving updates key", async () => {
      vi.mocked(api.listApiKeys)
        .mockResolvedValueOnce(mockApiKeysResponse() as any)
        .mockResolvedValueOnce({
          ...mockApiKeysResponse(),
          items: [
            { ...mockApiKeysResponse().items[0], name: "Updated API Key" },
            mockApiKeysResponse().items[1],
          ],
        } as any);

      vi.mocked(api.getApiKeyDetail).mockResolvedValue(
        mockApiKeyDetailResponse() as any
      );
      vi.mocked(api.updateApiKey).mockResolvedValue(
        mockUpdateApiKeyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button", { name: /编辑/i });
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("edit-api-key-dialog")).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText(/名称/i);
      await user.clear(nameInput);
      await user.type(nameInput, "Updated API Key");

      await user.click(screen.getByRole("button", { name: /提交|保存|更新/i }));

      await waitFor(() => {
        expect(api.updateApiKey).toHaveBeenCalledTimes(1);
      });

      expect(api.updateApiKey).toHaveBeenCalledWith(
        "ak-001",
        expect.objectContaining({ name: "Updated API Key" })
      );
    });

    it("after update, list refreshes", async () => {
      vi.mocked(api.listApiKeys)
        .mockResolvedValueOnce(mockApiKeysResponse() as any)
        .mockResolvedValueOnce({
          ...mockApiKeysResponse(),
          items: [
            { ...mockApiKeysResponse().items[0], name: "Updated API Key" },
            mockApiKeysResponse().items[1],
          ],
        } as any);

      vi.mocked(api.getApiKeyDetail).mockResolvedValue(
        mockApiKeyDetailResponse() as any
      );
      vi.mocked(api.updateApiKey).mockResolvedValue(
        mockUpdateApiKeyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button", { name: /编辑/i });
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("edit-api-key-dialog")).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText(/名称/i);
      await user.clear(nameInput);
      await user.type(nameInput, "Updated API Key");

      await user.click(screen.getByRole("button", { name: /提交|保存|更新/i }));

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByText("Updated API Key")).toBeInTheDocument();
      });
    });
  });

  // ── Revoke ─────────────────────────────────────────────────────────────

  describe("API Keys Page - Revoke", () => {
    it("clicking revoke shows confirmation dialog", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const revokeButtons = screen.getAllByRole("button", { name: /吊销|撤销|revoke/i });
      await user.click(revokeButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("revoke-confirm-dialog")).toBeInTheDocument();
      });
    });

    it("confirming revoke changes key state", async () => {
      vi.mocked(api.listApiKeys)
        .mockResolvedValueOnce(mockApiKeysResponse() as any)
        .mockResolvedValueOnce({
          ...mockApiKeysResponse(),
          items: [
            { ...mockApiKeysResponse().items[0], state: "revoked" },
            mockApiKeysResponse().items[1],
          ],
        } as any);

      vi.mocked(api.deleteApiKey).mockResolvedValue(
        mockDeleteApiKeyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const revokeButtons = screen.getAllByRole("button", { name: /吊销|撤销|revoke/i });
      await user.click(revokeButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("revoke-confirm-dialog")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /确认|确定|吊销/i }));

      await waitFor(() => {
        expect(api.deleteApiKey).toHaveBeenCalledTimes(1);
      });

      expect(api.deleteApiKey).toHaveBeenCalledWith("ak-001");
    });

    it("after revoke, list refreshes", async () => {
      vi.mocked(api.listApiKeys)
        .mockResolvedValueOnce(mockApiKeysResponse() as any)
        .mockResolvedValueOnce({
          ...mockApiKeysResponse(),
          items: [
            { ...mockApiKeysResponse().items[0], state: "revoked" },
            mockApiKeysResponse().items[1],
          ],
        } as any);

      vi.mocked(api.deleteApiKey).mockResolvedValue(
        mockDeleteApiKeyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const revokeButtons = screen.getAllByRole("button", { name: /吊销|撤销|revoke/i });
      await user.click(revokeButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("revoke-confirm-dialog")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /确认|确定|吊销/i }));

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByText("revoked")).toBeInTheDocument();
      });
    });
  });

  // ── Usage Stats ────────────────────────────────────────────────────────

  describe("API Keys Page - Usage Stats", () => {
    it("clicking usage button opens stats modal", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );
      vi.mocked(api.getApiKeyUsage).mockResolvedValue(
        mockApiKeyUsageResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const usageButtons = screen.getAllByRole("button", { name: /用量|统计|usage/i });
      await user.click(usageButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("api-key-usage-dialog")).toBeInTheDocument();
      });
    });

    it("shows total requests, tokens, QPS peak", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );
      vi.mocked(api.getApiKeyUsage).mockResolvedValue(
        mockApiKeyUsageResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const usageButtons = screen.getAllByRole("button", { name: /用量|统计|usage/i });
      await user.click(usageButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("api-key-usage-dialog")).toBeInTheDocument();
      });

      expect(screen.getByText(/15420/)).toBeInTheDocument();
      expect(screen.getByText(/3847500/)).toBeInTheDocument();
      expect(screen.getByText(/45.2/)).toBeInTheDocument();
    });

    it("shows daily stats chart/table", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );
      vi.mocked(api.getApiKeyUsage).mockResolvedValue(
        mockApiKeyUsageResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const usageButtons = screen.getAllByRole("button", { name: /用量|统计|usage/i });
      await user.click(usageButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("api-key-usage-dialog")).toBeInTheDocument();
      });

      expect(screen.getByText(/2024-06-08/)).toBeInTheDocument();
      expect(screen.getByText(/2024-06-09/)).toBeInTheDocument();
      expect(screen.getByText(/2024-06-10/)).toBeInTheDocument();
    });
  });

  // ── Empty ──────────────────────────────────────────────────────────────

  describe("API Keys Page - Empty", () => {
    it("shows empty state when no keys", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysEmptyResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无密钥/)).toBeInTheDocument();
      });
    });
  });

  // ── Error ──────────────────────────────────────────────────────────────

  describe("API Keys Page - Error", () => {
    it("shows error alert when list API fails", async () => {
      vi.mocked(api.listApiKeys).mockRejectedValue(
        new Error("Network error")
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toBeInTheDocument();
        expect(alert).toHaveTextContent(/加载密钥失败/);
      });
    });

    it("shows error toast when create fails", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );
      vi.mocked(api.createApiKey).mockRejectedValue(
        new Error("Create failed")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /创建密钥/i }));

      await waitFor(() => {
        expect(screen.getByTestId("create-api-key-dialog")).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/名称/i), "New API Key");
      await user.click(screen.getByRole("button", { name: /提交|创建|保存/i }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalled();
      });
    });

    it("shows error toast when revoke fails", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysResponse() as any
      );
      vi.mocked(api.deleteApiKey).mockRejectedValue(
        new Error("Revoke failed")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Production API Key")).toBeInTheDocument();
      });

      const revokeButtons = screen.getAllByRole("button", { name: /吊销|撤销|revoke/i });
      await user.click(revokeButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("revoke-confirm-dialog")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /确认|确定|吊销/i }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalled();
      });
    });
  });

  // ── Boundary ───────────────────────────────────────────────────────────

  describe("API Keys Page - Boundary", () => {
    it("renders correctly with very long names", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });
    });

    it("renders correctly with many permissions", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });

      expect(screen.getByText(/read/)).toBeInTheDocument();
      expect(screen.getByText(/search/)).toBeInTheDocument();
      expect(screen.getByText(/upload/)).toBeInTheDocument();
    });

    it("renders correctly with null expiration", async () => {
      vi.mocked(api.listApiKeys).mockResolvedValue(
        mockApiKeysBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ApiKeysPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });

      expect(screen.getByText(/永不过期/)).toBeInTheDocument();
    });
  });
});
