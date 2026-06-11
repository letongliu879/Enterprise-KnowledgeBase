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
    listRetrievalProfiles: vi.fn(),
    getRetrievalProfileDetail: vi.fn(),
    createRetrievalProfile: vi.fn(),
    updateRetrievalProfile: vi.fn(),
    deleteRetrievalProfile: vi.fn(),
    publishRetrievalProfile: vi.fn(),
    cloneRetrievalProfile: vi.fn(),
  } as any,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import { toast } from "sonner";

import { RetrievalProfilesPage } from "./retrieval-profiles-page";

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

function mockRetrievalProfilesResponse(overrides?: Record<string, unknown>) {
  return {
    items: [
      {
        retrieval_profile_id: "rp-001",
        name: "Standard",
        state: "published",
        description: "Standard retrieval configuration",
        config: {
          rerank_model: "default",
          top_k: 10,
          similarity_threshold: 0.75,
          token_budget_limit: 4096,
        },
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-06-01T00:00:00Z",
      },
      {
        retrieval_profile_id: "rp-002",
        name: "Aggressive",
        state: "draft",
        description: "Aggressive retrieval with high top_k",
        config: {
          rerank_model: "cross-encoder",
          top_k: 50,
          similarity_threshold: 0.5,
          token_budget_limit: 8192,
        },
        created_at: "2024-02-01T00:00:00Z",
        updated_at: "2024-06-02T00:00:00Z",
      },
    ],
    total: 2,
    ...overrides,
  };
}

function mockRetrievalProfilesEmptyResponse() {
  return { items: [], total: 0 };
}

function mockRetrievalProfilesBoundaryResponse() {
  return {
    items: [
      {
        retrieval_profile_id: "rp-boundary",
        name: "a".repeat(520),
        state: "draft",
        description: "",
        config: {
          rerank_model: "default",
          top_k: 999999,
          similarity_threshold: 1.0,
          token_budget_limit: 999999999,
        },
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-06-01T00:00:00Z",
      },
    ],
    total: 1,
  };
}

function mockRetrievalProfileDetailResponse(overrides?: Record<string, unknown>) {
  return {
    retrieval_profile_id: "rp-001",
    name: "Standard",
    state: "published",
    description: "Standard retrieval configuration",
    config: {
      rerank_model: "default",
      top_k: 10,
      similarity_threshold: 0.75,
      token_budget_limit: 4096,
    },
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    ...overrides,
  };
}

function mockCreateRetrievalProfileResponse(overrides?: Record<string, unknown>) {
  return {
    retrieval_profile_id: "rp-new",
    name: "New Profile",
    state: "draft",
    created_at: "2024-06-10T00:00:00Z",
    ...overrides,
  };
}

function mockUpdateRetrievalProfileResponse(overrides?: Record<string, unknown>) {
  return {
    retrieval_profile_id: "rp-001",
    name: "Updated Standard",
    state: "published",
    updated_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

function mockDeleteRetrievalProfileResponse() {
  return { retrieval_profile_id: "rp-001", deleted: true };
}

function mockPublishRetrievalProfileResponse() {
  return { retrieval_profile_id: "rp-002", state: "published", published_at: "2024-06-10T12:00:00Z" };
}

function mockCloneRetrievalProfileResponse() {
  return {
    source_retrieval_profile_id: "rp-001",
    retrieval_profile_id: "rp-clone",
    name: "Standard (Copy)",
    state: "draft",
    created_at: "2024-06-10T12:00:00Z",
  };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("RetrievalProfilesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("renders skeleton while profiles are loading", async () => {
      vi.mocked(api.listRetrievalProfiles).mockImplementation(
        () => new Promise(() => {})
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId("profile-skeleton")).toBeInTheDocument();
      });
    });
  });

  // ── Success State - Normal Data ────────────────────────────────────────

  describe("Success State - Normal Data", () => {
    it("renders profile list with names and states", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      expect(screen.getByText("Aggressive")).toBeInTheDocument();
    });

    it("distinguishes draft and published states with badges", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      expect(screen.getByText("published")).toBeInTheDocument();
      expect(screen.getByText("draft")).toBeInTheDocument();
    });

    it("renders action buttons for each profile", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button", { name: /编辑/i });
      const deleteButtons = screen.getAllByRole("button", { name: /删除/i });
      const cloneButtons = screen.getAllByRole("button", { name: /克隆/i });

      expect(editButtons.length).toBeGreaterThanOrEqual(2);
      expect(deleteButtons.length).toBeGreaterThanOrEqual(2);
      expect(cloneButtons.length).toBeGreaterThanOrEqual(2);
    });

    it("shows publish button only for draft profiles", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const publishButtons = screen.getAllByRole("button", { name: /发布/i });
      expect(publishButtons.length).toBe(1);
    });

    it("shows description summary for each profile", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(
          screen.getByText("Standard retrieval configuration")
        ).toBeInTheDocument();
      });

      expect(
        screen.getByText("Aggressive retrieval with high top_k")
      ).toBeInTheDocument();
    });
  });

  // ── Create Profile ─────────────────────────────────────────────────────

  describe("Create Profile", () => {
    it("opens create dialog when clicking new profile button", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const newBtn = screen.getByRole("button", { name: /新建配置/i });
      await user.click(newBtn);

      await waitFor(() => {
        expect(screen.getByTestId("create-profile-dialog")).toBeInTheDocument();
      });
    });

    it("creates profile with form data and refreshes list", async () => {
      vi.mocked(api.listRetrievalProfiles)
        .mockResolvedValueOnce(mockRetrievalProfilesResponse() as any)
        .mockResolvedValueOnce({
          ...mockRetrievalProfilesResponse(),
          items: [
            ...mockRetrievalProfilesResponse().items,
            {
              retrieval_profile_id: "rp-new",
              name: "New Profile",
              state: "draft",
              description: "A new profile",
              config: {
                rerank_model: "default",
                top_k: 20,
                similarity_threshold: 0.8,
                token_budget_limit: 2048,
              },
              created_at: "2024-06-10T00:00:00Z",
              updated_at: "2024-06-10T00:00:00Z",
            },
          ],
          total: 3,
        } as any);

      vi.mocked(api.createRetrievalProfile).mockResolvedValue(
        mockCreateRetrievalProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /新建配置/i }));

      await waitFor(() => {
        expect(screen.getByTestId("create-profile-dialog")).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/名称/i), "New Profile");
      await user.type(screen.getByLabelText(/描述/i), "A new profile");
      await user.type(screen.getByLabelText(/rerank_model/i), "default");
      await user.type(screen.getByLabelText(/top_k/i), "20");
      await user.type(screen.getByLabelText(/similarity_threshold/i), "0.8");
      await user.type(screen.getByLabelText(/token_budget_limit/i), "2048");

      await user.click(screen.getByRole("button", { name: /提交|创建|保存/i }));

      await waitFor(() => {
        expect(api.createRetrievalProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.createRetrievalProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "New Profile",
          description: "A new profile",
          config: expect.objectContaining({
            rerank_model: "default",
            top_k: 20,
            similarity_threshold: 0.8,
            token_budget_limit: 2048,
          }),
        })
      );

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.queryByTestId("create-profile-dialog")).not.toBeInTheDocument();
      });
    });
  });

  // ── Edit Profile ───────────────────────────────────────────────────────

  describe("Edit Profile", () => {
    it("opens edit dialog with prefilled data", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );
      vi.mocked(api.getRetrievalProfileDetail).mockResolvedValue(
        mockRetrievalProfileDetailResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button", { name: /编辑/i });
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("edit-profile-dialog")).toBeInTheDocument();
      });

      expect(screen.getByDisplayValue("Standard")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Standard retrieval configuration")).toBeInTheDocument();
    });

    it("submits updated data and refreshes list", async () => {
      vi.mocked(api.listRetrievalProfiles)
        .mockResolvedValueOnce(mockRetrievalProfilesResponse() as any)
        .mockResolvedValueOnce({
          ...mockRetrievalProfilesResponse(),
          items: [
            {
              ...mockRetrievalProfilesResponse().items[0],
              name: "Updated Standard",
              description: "Updated description",
            },
            mockRetrievalProfilesResponse().items[1],
          ],
        } as any);

      vi.mocked(api.getRetrievalProfileDetail).mockResolvedValue(
        mockRetrievalProfileDetailResponse() as any
      );
      vi.mocked(api.updateRetrievalProfile).mockResolvedValue(
        mockUpdateRetrievalProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button", { name: /编辑/i });
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("edit-profile-dialog")).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText(/名称/i);
      await user.clear(nameInput);
      await user.type(nameInput, "Updated Standard");

      await user.click(screen.getByRole("button", { name: /提交|保存|更新/i }));

      await waitFor(() => {
        expect(api.updateRetrievalProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.updateRetrievalProfile).toHaveBeenCalledWith(
        "rp-001",
        expect.objectContaining({ name: "Updated Standard" })
      );

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.queryByTestId("edit-profile-dialog")).not.toBeInTheDocument();
      });
    });
  });

  // ── Delete Profile ─────────────────────────────────────────────────────

  describe("Delete Profile", () => {
    it("shows confirm dialog and deletes on confirmation", async () => {
      vi.mocked(api.listRetrievalProfiles)
        .mockResolvedValueOnce(mockRetrievalProfilesResponse() as any)
        .mockResolvedValueOnce(mockRetrievalProfilesEmptyResponse() as any);

      vi.mocked(api.deleteRetrievalProfile).mockResolvedValue(
        mockDeleteRetrievalProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole("button", { name: /删除/i });
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("delete-confirm-dialog")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /确认|确定|删除/i }));

      await waitFor(() => {
        expect(api.deleteRetrievalProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.deleteRetrievalProfile).toHaveBeenCalledWith("rp-001");

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.queryByTestId("delete-confirm-dialog")).not.toBeInTheDocument();
      });
    });
  });

  // ── Publish Profile ────────────────────────────────────────────────────

  describe("Publish Profile", () => {
    it("publishes draft profile and updates state", async () => {
      vi.mocked(api.listRetrievalProfiles)
        .mockResolvedValueOnce(mockRetrievalProfilesResponse() as any)
        .mockResolvedValueOnce({
          ...mockRetrievalProfilesResponse(),
          items: [
            mockRetrievalProfilesResponse().items[0],
            { ...mockRetrievalProfilesResponse().items[1], state: "published" },
          ],
        } as any);

      vi.mocked(api.publishRetrievalProfile).mockResolvedValue(
        mockPublishRetrievalProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Aggressive")).toBeInTheDocument();
      });

      const publishButton = screen.getByRole("button", { name: /发布/i });
      await user.click(publishButton);

      await waitFor(() => {
        expect(api.publishRetrievalProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.publishRetrievalProfile).toHaveBeenCalledWith("rp-002");

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });
    });
  });

  // ── Clone Profile ──────────────────────────────────────────────────────

  describe("Clone Profile", () => {
    it("clones profile and adds copy to list", async () => {
      vi.mocked(api.listRetrievalProfiles)
        .mockResolvedValueOnce(mockRetrievalProfilesResponse() as any)
        .mockResolvedValueOnce({
          ...mockRetrievalProfilesResponse(),
          items: [
            ...mockRetrievalProfilesResponse().items,
            {
              retrieval_profile_id: "rp-clone",
              name: "Standard (Copy)",
              state: "draft",
              description: "Standard retrieval configuration",
              config: {
                rerank_model: "default",
                top_k: 10,
                similarity_threshold: 0.75,
                token_budget_limit: 4096,
              },
              created_at: "2024-06-10T12:00:00Z",
              updated_at: "2024-06-10T12:00:00Z",
            },
          ],
          total: 3,
        } as any);

      vi.mocked(api.cloneRetrievalProfile).mockResolvedValue(
        mockCloneRetrievalProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const cloneButtons = screen.getAllByRole("button", { name: /克隆/i });
      await user.click(cloneButtons[0]);

      await waitFor(() => {
        expect(api.cloneRetrievalProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.cloneRetrievalProfile).toHaveBeenCalledWith("rp-001");

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByText("Standard (Copy)")).toBeInTheDocument();
      });
    });
  });

  // ── Empty State ────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows EmptyState with '暂无配置' when no profiles", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesEmptyResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无配置/)).toBeInTheDocument();
      });
    });

    it("does not render profile list when empty", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesEmptyResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无配置/)).toBeInTheDocument();
      });

      expect(screen.queryByText("Standard")).not.toBeInTheDocument();
      expect(screen.queryByText("Aggressive")).not.toBeInTheDocument();
    });
  });

  // ── Error State ────────────────────────────────────────────────────────

  describe("Error State", () => {
    it("shows Alert with '加载配置失败' when list API fails", async () => {
      vi.mocked(api.listRetrievalProfiles).mockRejectedValue(
        new Error("Network error")
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toBeInTheDocument();
        expect(alert).toHaveTextContent(/加载配置失败/);
      });
    });

    it("does not render skeleton after error", async () => {
      vi.mocked(api.listRetrievalProfiles).mockRejectedValue(
        new Error("Network error")
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(screen.queryByTestId("profile-skeleton")).not.toBeInTheDocument();
    });

    it("shows error toast when create fails", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );
      vi.mocked(api.createRetrievalProfile).mockRejectedValue(
        new Error("Create failed")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /新建配置/i }));

      await waitFor(() => {
        expect(screen.getByTestId("create-profile-dialog")).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/名称/i), "New Profile");
      await user.click(screen.getByRole("button", { name: /提交|创建|保存/i }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalled();
      });
    });

    it("shows error toast when delete fails", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesResponse() as any
      );
      vi.mocked(api.deleteRetrievalProfile).mockRejectedValue(
        new Error("Delete failed")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole("button", { name: /删除/i });
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("delete-confirm-dialog")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /确认|确定|删除/i }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalled();
      });
    });
  });

  // ── Boundary State ─────────────────────────────────────────────────────

  describe("Boundary State", () => {
    it("renders profile with very long name without crashing", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });
    });

    it("renders profile with empty description", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });
    });

    it("renders profile with very large top_k value", async () => {
      vi.mocked(api.listRetrievalProfiles).mockResolvedValue(
        mockRetrievalProfilesBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<RetrievalProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });

      expect(screen.getByText(/999999/)).toBeInTheDocument();
    });
  });
});
