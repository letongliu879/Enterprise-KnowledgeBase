import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    listTicketComments: vi.fn(),
    createTicketComment: vi.fn(),
    updateTicketComment: vi.fn(),
    deleteTicketComment: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import { TicketComments } from "./ticket-comments";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function mockCommentsResponse() {
  return {
    items: [
      {
        comment_id: "comment-001",
        ticket_id: "ticket-001",
        author_id: "user-001",
        author_name: "Administrator",
        author_email: "admin@example.com",
        content: "First comment",
        mentions: null,
        created_at: "2024-06-10T12:00:00Z",
        updated_at: "2024-06-10T12:00:00Z",
      },
      {
        comment_id: "comment-002",
        ticket_id: "ticket-001",
        author_id: "user-002",
        author_name: "Reviewer",
        author_email: "reviewer@example.com",
        content: "@user-001 please check",
        mentions: ["user-001"],
        created_at: "2024-06-10T13:00:00Z",
        updated_at: "2024-06-10T13:00:00Z",
      },
    ],
    total: 2,
  };
}

describe("TicketComments", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading skeletons", () => {
    vi.mocked(workbenchApi.listTicketComments).mockImplementation(() => new Promise(() => {}));

    const Wrapper = createWrapper();
    render(<TicketComments ticketId="ticket-001" />, { wrapper: Wrapper });

    expect(screen.getAllByTestId("comment-skeleton")).toHaveLength(2);
  });

  it("renders comments and highlights mentions", async () => {
    vi.mocked(workbenchApi.listTicketComments).mockResolvedValue(mockCommentsResponse() as any);

    const Wrapper = createWrapper();
    render(<TicketComments ticketId="ticket-001" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("First comment")).toBeInTheDocument();
    });

    expect(screen.getByText("Administrator")).toBeInTheDocument();
    expect(screen.getByText("@user-001")).toHaveClass("text-primary");
  });

  it("creates a new comment", async () => {
    const user = userEvent.setup();
    vi.mocked(workbenchApi.listTicketComments).mockResolvedValue({ items: [], total: 0 } as any);
    vi.mocked(workbenchApi.createTicketComment).mockResolvedValue({
      comment_id: "comment-new",
      ticket_id: "ticket-001",
      author_id: "user-001",
      author_name: "Administrator",
      content: "New comment",
      created_at: "2024-06-10T14:00:00Z",
      updated_at: "2024-06-10T14:00:00Z",
    } as any);

    const Wrapper = createWrapper();
    render(<TicketComments ticketId="ticket-001" currentUserId="user-001" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("暂无评论，写下第一条评论吧")).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText("写下评论，使用 @用户名 提及同事...");
    await user.type(textarea, "New comment");
    await user.click(screen.getByRole("button", { name: /发表评论/i }));

    await waitFor(() => {
      expect(workbenchApi.createTicketComment).toHaveBeenCalledWith("ticket-001", {
        content: "New comment",
      });
    });
  });

  it("deletes a comment", async () => {
    const user = userEvent.setup();
    vi.mocked(workbenchApi.listTicketComments).mockResolvedValue({
      items: [
        {
          comment_id: "comment-001",
          ticket_id: "ticket-001",
          author_id: "user-001",
          author_name: "Administrator",
          content: "Delete me",
          created_at: "2024-06-10T12:00:00Z",
          updated_at: "2024-06-10T12:00:00Z",
        },
      ],
      total: 1,
    } as any);
    vi.mocked(workbenchApi.deleteTicketComment).mockResolvedValue(undefined as any);

    const Wrapper = createWrapper();
    render(<TicketComments ticketId="ticket-001" currentUserId="user-001" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Delete me")).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText("删除评论"));

    await waitFor(() => {
      expect(workbenchApi.deleteTicketComment).toHaveBeenCalledWith("comment-001");
    });
  });

  it("edits a comment", async () => {
    const user = userEvent.setup();
    vi.mocked(workbenchApi.listTicketComments).mockResolvedValue({
      items: [
        {
          comment_id: "comment-001",
          ticket_id: "ticket-001",
          author_id: "user-001",
          author_name: "Administrator",
          content: "Old text",
          created_at: "2024-06-10T12:00:00Z",
          updated_at: "2024-06-10T12:00:00Z",
        },
      ],
      total: 1,
    } as any);
    vi.mocked(workbenchApi.updateTicketComment).mockResolvedValue({
      comment_id: "comment-001",
      content: "Updated text",
    } as any);

    const Wrapper = createWrapper();
    render(<TicketComments ticketId="ticket-001" currentUserId="user-001" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Old text")).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText("编辑评论"));

    const textarea = screen.getByDisplayValue("Old text");
    await user.clear(textarea);
    await user.type(textarea, "Updated text");
    await user.click(screen.getByRole("button", { name: /保存/i }));

    await waitFor(() => {
      expect(workbenchApi.updateTicketComment).toHaveBeenCalledWith("comment-001", {
        content: "Updated text",
      });
    });
  });
});
