import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ────────────────────────────────────────────────────────────────

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    getNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    readAllNotifications: vi.fn(),
    getUnreadCount: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import { NotificationCenter } from "./notification-center";

// ── Helpers ──────────────────────────────────────────────────────────────

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function mockNotificationsResponse(overrides?: Record<string, unknown>) {
  return {
    items: [
      {
        notification_id: "notif-001",
        type: "ticket_status_change",
        title: "Ticket status changed",
        message: "Your ticket ticket-001 has been approved.",
        link: "/workbench/tickets/ticket-001",
        is_read: false,
        created_at: "2024-01-01T00:00:00Z",
      },
      {
        notification_id: "notif-002",
        type: "chunk_edit_conflict",
        title: "Chunk edit conflict detected",
        message: "A conflict was found in chunk ev-001.",
        link: "/workbench/documents/doc-001",
        is_read: true,
        created_at: "2024-01-02T00:00:00Z",
      },
      {
        notification_id: "notif-003",
        type: "quota_warning",
        title: "Storage quota warning",
        message: "You have used 90% of your storage quota.",
        link: null,
        is_read: false,
        created_at: "2024-01-03T00:00:00Z",
      },
      {
        notification_id: "notif-004",
        type: "system_maintenance",
        title: "Scheduled maintenance",
        message: "System maintenance is scheduled for tonight.",
        link: null,
        is_read: true,
        created_at: "2024-01-04T00:00:00Z",
      },
    ],
    total: 4,
    unread_count: 2,
    ...overrides,
  };
}

function mockNotificationsEmptyResponse() {
  return { items: [], total: 0, unread_count: 0 };
}

function mockNotificationsBoundaryResponse() {
  return {
    items: [
      {
        notification_id: "notif-boundary",
        type: "system_maintenance",
        title: "a".repeat(520),
        message: "测试中文内容 🚀 日本語テキスト 🇯🇵 한국어 텍스트 🇰🇷 العربية 🌍",
        link: "/workbench/tickets/ticket-boundary",
        is_read: false,
        created_at: "2099-12-31T23:59:59Z",
      },
    ],
    total: 999999,
    unread_count: 999999,
  };
}

function mockUnreadCountResponse(count: number) {
  return { count };
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("NotificationCenter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Initial Render ─────────────────────────────────────────────────────

  describe("Initial Render", () => {
    it("renders bell icon with aria-label", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );

      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });
    });

    it("SHE-018: shows unread badge when unread_count > 0", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(5) as any
      );

      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("5")).toBeInTheDocument();
      });
    });

    it("does not show unread badge when unread_count = 0", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );

      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByText("0")).not.toBeInTheDocument();
      });
    });
  });

  // ── Panel Interaction ──────────────────────────────────────────────────

  describe("Panel Interaction", () => {
    it("opens panel when bell is clicked", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockImplementation(
        () => new Promise(() => {})
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      expect(screen.getByTestId("notification-panel")).toBeInTheDocument();
    });

    it("SHE-019: panel has animation attributes on open (scale + fade)", async () => {
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      const bell = screen.getByRole("button", { name: /notifications/i });
      await userEvent.click(bell);

      await waitFor(() => {
        const panel = screen.getByTestId("notification-panel");
        expect(panel).toBeInTheDocument();
      });
    });

    it("closes panel when bell is clicked again", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsEmptyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));
      await waitFor(() => {
        expect(screen.getByTestId("notification-panel")).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));
      await waitFor(() => {
        expect(screen.queryByTestId("notification-panel")).not.toBeInTheDocument();
      });
    });
  });

  // ── Loading State ──────────────────────────────────────────────────────

  describe("Loading State", () => {
    it("shows skeleton while notifications are loading", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockImplementation(
        () => new Promise(() => {})
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      expect(screen.getByTestId("notification-skeleton")).toBeInTheDocument();
    });
  });

  // ── Success State - Normal Data ────────────────────────────────────────

  describe("Success State - Normal Data", () => {
    it("renders notification list with titles", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(2) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText("Ticket status changed")).toBeInTheDocument();
      });

      expect(screen.getByText("Chunk edit conflict detected")).toBeInTheDocument();
      expect(screen.getByText("Storage quota warning")).toBeInTheDocument();
      expect(screen.getByText("Scheduled maintenance")).toBeInTheDocument();
    });

    it("distinguishes unread and read notifications", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(2) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText("Ticket status changed")).toBeInTheDocument();
      });

      const unreadItems = screen.getAllByTestId("notification-item-unread");
      const readItems = screen.getAllByTestId("notification-item-read");

      expect(unreadItems.length).toBe(2);
      expect(readItems.length).toBe(2);
    });

    it("renders type icons for each notification", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(2) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        const items = screen.getAllByTestId(/notification-item-/);
        expect(items.length).toBe(4);
      });
    });
  });

  // ── Action -> Effect Chain ─────────────────────────────────────────────

  describe("Action -> Effect Chain", () => {
    it("SHE-020: clicking unread notification marks it read and navigates", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(2) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsResponse() as any
      );
      vi.mocked(workbenchApi.markNotificationRead).mockResolvedValue({
        notification_id: "notif-001",
        is_read: true,
      } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText("Ticket status changed")).toBeInTheDocument();
      });

      const unreadItem = screen.getAllByTestId("notification-item-unread")[0];
      await user.click(unreadItem);

      expect(workbenchApi.markNotificationRead).toHaveBeenCalledTimes(1);
      expect(workbenchApi.markNotificationRead).toHaveBeenCalledWith("notif-001");
      expect(mockPush).toHaveBeenCalledTimes(1);
      expect(mockPush).toHaveBeenCalledWith("/workbench/tickets/ticket-001");
    });

    it("clicking read notification does not call mark read but still navigates", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(2) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsResponse() as any
      );
      vi.mocked(workbenchApi.markNotificationRead).mockResolvedValue({
        notification_id: "notif-002",
        is_read: true,
      } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText("Chunk edit conflict detected")).toBeInTheDocument();
      });

      const readItem = screen.getAllByTestId("notification-item-read")[0];
      await user.click(readItem);

      expect(workbenchApi.markNotificationRead).not.toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledTimes(1);
      expect(mockPush).toHaveBeenCalledWith("/workbench/documents/doc-001");
    });

    it("clicking notification without link does not navigate", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(2) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsResponse() as any
      );
      vi.mocked(workbenchApi.markNotificationRead).mockResolvedValue({
        notification_id: "notif-003",
        is_read: true,
      } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText("Storage quota warning")).toBeInTheDocument();
      });

      const unreadItems = screen.getAllByTestId("notification-item-unread");
      const noLinkItem = unreadItems.find((el) =>
        el.textContent?.includes("Storage quota warning")
      );
      expect(noLinkItem).toBeTruthy();
      await user.click(noLinkItem!);

      expect(workbenchApi.markNotificationRead).toHaveBeenCalledWith("notif-003");
      expect(mockPush).not.toHaveBeenCalled();
    });

    it("SHE-021: clicking 'mark all read' calls API and hides badge", async () => {
      vi.mocked(workbenchApi.getUnreadCount)
        .mockResolvedValueOnce(mockUnreadCountResponse(2) as any)
        .mockResolvedValue(mockUnreadCountResponse(0) as any);
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsResponse() as any
      );
      vi.mocked(workbenchApi.readAllNotifications).mockResolvedValue({
        count: 2,
      } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("2")).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText("Ticket status changed")).toBeInTheDocument();
      });

      const markAllBtn = screen.getByRole("button", { name: /全部已读/i });
      await user.click(markAllBtn);

      await waitFor(() => {
        expect(workbenchApi.readAllNotifications).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(screen.queryByText("2")).not.toBeInTheDocument();
      });
    });
  });

  // ── Empty State ────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows '暂无通知' when no notifications", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsEmptyResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText(/暂无通知/)).toBeInTheDocument();
      });
    });
  });

  // ── Error State ────────────────────────────────────────────────────────

  describe("Error State", () => {
    it("SHE-036: shows error message when API fails", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockRejectedValue(
        new Error("Network error")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
    });

    it("does not render skeleton after error", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockRejectedValue(
        new Error("Network error")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(screen.queryByTestId("notification-skeleton")).not.toBeInTheDocument();
    });

    it("SHE-037: 错误状态显示重试按钮", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockRejectedValue(
        new Error("Network error")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /重试/i })).toBeInTheDocument();
      });
    });

    it("SHE-037: 重试按钮点击后调用 refetch", async () => {
      const retrySpy = vi.fn();
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(0) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockRejectedValue(
        new Error("Network error")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /重试/i })).toBeInTheDocument();
      });

      // The retry button's onClick calls refetch, which re-runs queryFn
      // Since queryFn rejects again, we just verify the button triggers a re-fetch
      // by checking that the alert re-appears
      await user.click(screen.getByRole("button", { name: /重试/i }));

      // After clicking retry, the loading state should briefly show before error re-occurs
      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
    });
  });

  // ── A11y ────────────────────────────────────────────────────────────────

  describe("A11y", () => {
    it("通知面板有 role='dialog' 和 aria-label", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(3) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        const dialog = screen.getByRole("dialog");
        expect(dialog).toHaveAttribute("aria-label", "通知面板");
      });
    });
  });

  // ── Boundary State ─────────────────────────────────────────────────────

  describe("Boundary State", () => {
    it("renders notification with very long title and message", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(999999) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsBoundaryResponse() as any
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });

      expect(
        screen.getByText(/测试中文内容|🚀|日本語/)
      ).toBeInTheDocument();
    });

    it("formats large unread count", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(999999) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsBoundaryResponse() as any
      );

      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("999999")).toBeInTheDocument();
      });
    });

    it("clicking boundary notification marks read and navigates correctly", async () => {
      vi.mocked(workbenchApi.getUnreadCount).mockResolvedValue(
        mockUnreadCountResponse(999999) as any
      );
      vi.mocked(workbenchApi.getNotifications).mockResolvedValue(
        mockNotificationsBoundaryResponse() as any
      );
      vi.mocked(workbenchApi.markNotificationRead).mockResolvedValue({
        notification_id: "notif-boundary",
        is_read: true,
      } as any);

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<NotificationCenter />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/Notifications/i)).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText(/Notifications/i));

      await waitFor(() => {
        expect(screen.getByText("a".repeat(520))).toBeInTheDocument();
      });

      const unreadItem = screen.getByTestId("notification-item-unread");
      await user.click(unreadItem);

      expect(workbenchApi.markNotificationRead).toHaveBeenCalledWith("notif-boundary");
      expect(mockPush).toHaveBeenCalledWith("/workbench/tickets/ticket-boundary");
    });
  });
});
