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
    listParserProfiles: vi.fn(),
    getParserProfileDetail: vi.fn(),
    createParserProfile: vi.fn(),
    updateParserProfile: vi.fn(),
    deleteParserProfile: vi.fn(),
    publishParserProfile: vi.fn(),
    cloneParserProfile: vi.fn(),
  } as any,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import { toast } from "sonner";

import { ParserProfilesPage } from "./parser-profiles-page";

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

function mockParserProfilesResponse(overrides?: Record<string, unknown>) {
  return {
    items: [
      {
        parser_profile_id: "pp-001",
        name: "Standard",
        state: "published",
        description: "Standard parser configuration",
        parser_id: "deepdoc",
        config: {
          ocr: true,
          table_detection: false,
          language: "en",
        },
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-06-01T00:00:00Z",
      },
      {
        parser_profile_id: "pp-002",
        name: "Aggressive",
        state: "draft",
        description: "Aggressive parser with OCR disabled",
        parser_id: "deepdoc",
        config: {
          ocr: false,
          table_detection: true,
          language: "zh",
        },
        created_at: "2024-02-01T00:00:00Z",
        updated_at: "2024-06-02T00:00:00Z",
      },
    ],
    total: 2,
    ...overrides,
  };
}

function mockParserProfilesEmptyResponse() {
  return { items: [], total: 0 };
}

function mockParserProfilesBoundaryResponse() {
  return {
    items: [
      {
        parser_profile_id: "pp-boundary",
        name: "a".repeat(520),
        state: "draft",
        description: "",
        parser_id: "deepdoc",
        config: {
          ocr: true,
          table_detection: true,
          language: "en",
        },
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-06-01T00:00:00Z",
      },
    ],
    total: 1,
  };
}

function mockParserProfileDetailResponse(overrides?: Record<string, unknown>) {
  return {
    parser_profile_id: "pp-001",
    name: "Standard",
    state: "published",
    description: "Standard parser configuration",
    parser_id: "deepdoc",
    config: {
      ocr: true,
      table_detection: false,
      language: "en",
    },
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    ...overrides,
  };
}

function mockCreateParserProfileResponse(overrides?: Record<string, unknown>) {
  return {
    parser_profile_id: "pp-new",
    name: "New Profile",
    state: "draft",
    created_at: "2024-06-10T00:00:00Z",
    ...overrides,
  };
}

function mockUpdateParserProfileResponse(overrides?: Record<string, unknown>) {
  return {
    parser_profile_id: "pp-001",
    name: "Updated Standard",
    state: "published",
    updated_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

function mockDeleteParserProfileResponse() {
  return { parser_profile_id: "pp-001", deleted: true };
}

function mockPublishParserProfileResponse() {
  return {
    parser_profile_id: "pp-002",
    state: "published",
    published_at: "2024-06-10T12:00:00Z",
  };
}

function mockCloneParserProfileResponse() {
  return {
    source_parser_profile_id: "pp-001",
    parser_profile_id: "pp-clone",
    name: "Standard (Copy)",
    state: "draft",
    created_at: "2024-06-10T12:00:00Z",
  };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("ParserProfilesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("renders skeleton while profiles are loading", async () => {
      vi.mocked(api.listParserProfiles).mockImplementation(
        () => new Promise(() => {})
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId("profile-skeleton")).toBeInTheDocument();
      });
    });
  });

  // ── Success State - Normal Data ────────────────────────────────────────

  describe("Success State - Normal Data", () => {
    it("renders profile list with names and states", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      expect(screen.getByText("Aggressive")).toBeInTheDocument();
    });

    it("distinguishes draft and published states with badges", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      expect(screen.getByText("published")).toBeInTheDocument();
      expect(screen.getByText("draft")).toBeInTheDocument();
    });

    it("renders action buttons for each profile", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

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
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const publishButtons = screen.getAllByRole("button", { name: /发布/i });
      expect(publishButtons.length).toBe(1);
    });

    it("shows description summary for each profile", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(
          screen.getByText("Standard parser configuration")
        ).toBeInTheDocument();
      });

      expect(
        screen.getByText("Aggressive parser with OCR disabled")
      ).toBeInTheDocument();
    });
  });

  // ── Create Profile ─────────────────────────────────────────────────────

  describe("Create Profile", () => {
    it("opens create dialog when clicking new profile button", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

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
      vi.mocked(api.listParserProfiles)
        .mockResolvedValueOnce(mockParserProfilesResponse() as any)
        .mockResolvedValueOnce({
          ...mockParserProfilesResponse(),
          items: [
            ...mockParserProfilesResponse().items,
            {
              parser_profile_id: "pp-new",
              name: "New Profile",
              state: "draft",
              description: "A new parser profile",
              parser_id: "deepdoc",
              config: {
                ocr: true,
                table_detection: true,
                language: "en",
              },
              created_at: "2024-06-10T00:00:00Z",
              updated_at: "2024-06-10T00:00:00Z",
            },
          ],
          total: 3,
        } as any);

      vi.mocked(api.createParserProfile).mockResolvedValue(
        mockCreateParserProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /新建配置/i }));

      await waitFor(() => {
        expect(screen.getByTestId("create-profile-dialog")).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/名称/i), "New Profile");
      await user.type(screen.getByLabelText(/描述/i), "A new parser profile");
      await user.type(screen.getByLabelText(/parser_id/i), "deepdoc");
      await user.type(screen.getByLabelText(/language/i), "en");

      await user.click(screen.getByRole("button", { name: /提交|创建|保存/i }));

      await waitFor(() => {
        expect(api.createParserProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.createParserProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "New Profile",
          description: "A new parser profile",
          parser_id: "deepdoc",
          language: "en",
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
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );
      vi.mocked(api.getParserProfileDetail).mockResolvedValue(
        mockParserProfileDetailResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button", { name: /编辑/i });
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId("edit-profile-dialog")).toBeInTheDocument();
      });

      expect(screen.getByDisplayValue("Standard")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Standard parser configuration")).toBeInTheDocument();
    });

    it("submits updated data and refreshes list", async () => {
      vi.mocked(api.listParserProfiles)
        .mockResolvedValueOnce(mockParserProfilesResponse() as any)
        .mockResolvedValueOnce({
          ...mockParserProfilesResponse(),
          items: [
            {
              ...mockParserProfilesResponse().items[0],
              name: "Updated Standard",
              description: "Updated description",
            },
            mockParserProfilesResponse().items[1],
          ],
        } as any);

      vi.mocked(api.getParserProfileDetail).mockResolvedValue(
        mockParserProfileDetailResponse() as any
      );
      vi.mocked(api.updateParserProfile).mockResolvedValue(
        mockUpdateParserProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

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
        expect(api.updateParserProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.updateParserProfile).toHaveBeenCalledWith(
        "pp-001",
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
      vi.mocked(api.listParserProfiles)
        .mockResolvedValueOnce(mockParserProfilesResponse() as any)
        .mockResolvedValueOnce(mockParserProfilesEmptyResponse() as any);

      vi.mocked(api.deleteParserProfile).mockResolvedValue(
        mockDeleteParserProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

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
        expect(api.deleteParserProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.deleteParserProfile).toHaveBeenCalledWith("pp-001");

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
      vi.mocked(api.listParserProfiles)
        .mockResolvedValueOnce(mockParserProfilesResponse() as any)
        .mockResolvedValueOnce({
          ...mockParserProfilesResponse(),
          items: [
            mockParserProfilesResponse().items[0],
            { ...mockParserProfilesResponse().items[1], state: "published" },
          ],
        } as any);

      vi.mocked(api.publishParserProfile).mockResolvedValue(
        mockPublishParserProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Aggressive")).toBeInTheDocument();
      });

      const publishButton = screen.getByRole("button", { name: /发布/i });
      await user.click(publishButton);

      await waitFor(() => {
        expect(api.publishParserProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.publishParserProfile).toHaveBeenCalledWith("pp-002");

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalled();
      });
    });
  });

  // ── Clone Profile ──────────────────────────────────────────────────────

  describe("Clone Profile", () => {
    it("clones profile and adds copy to list", async () => {
      vi.mocked(api.listParserProfiles)
        .mockResolvedValueOnce(mockParserProfilesResponse() as any)
        .mockResolvedValueOnce({
          ...mockParserProfilesResponse(),
          items: [
            ...mockParserProfilesResponse().items,
            {
              parser_profile_id: "pp-clone",
              name: "Standard (Copy)",
              state: "draft",
              description: "Standard parser configuration",
              parser_id: "deepdoc",
              config: {
                ocr: true,
                table_detection: false,
                language: "en",
              },
              created_at: "2024-06-10T12:00:00Z",
              updated_at: "2024-06-10T12:00:00Z",
            },
          ],
          total: 3,
        } as any);

      vi.mocked(api.cloneParserProfile).mockResolvedValue(
        mockCloneParserProfileResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Standard")).toBeInTheDocument();
      });

      const cloneButtons = screen.getAllByRole("button", { name: /克隆/i });
      await user.click(cloneButtons[0]);

      await waitFor(() => {
        expect(api.cloneParserProfile).toHaveBeenCalledTimes(1);
      });

      expect(api.cloneParserProfile).toHaveBeenCalledWith("pp-001");

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
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesEmptyResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/暂无配置/)).toBeInTheDocument();
      });
    });

    it("does not render profile list when empty", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesEmptyResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

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
      vi.mocked(api.listParserProfiles).mockRejectedValue(
        new Error("Network error")
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toBeInTheDocument();
        expect(alert).toHaveTextContent(/加载配置失败/);
      });
    });

    it("does not render skeleton after error", async () => {
      vi.mocked(api.listParserProfiles).mockRejectedValue(
        new Error("Network error")
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(screen.queryByTestId("profile-skeleton")).not.toBeInTheDocument();
    });

    it("shows error toast when create fails", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );
      vi.mocked(api.createParserProfile).mockRejectedValue(
        new Error("Create failed")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

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
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesResponse() as any
      );
      vi.mocked(api.deleteParserProfile).mockRejectedValue(
        new Error("Delete failed")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

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
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });
    });

    it("renders profile with empty description", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });
    });

    it("renders profile with very large config values", async () => {
      vi.mocked(api.listParserProfiles).mockResolvedValue(
        mockParserProfilesBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<ParserProfilesPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });
    });
  });
});
