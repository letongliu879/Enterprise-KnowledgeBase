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
    listTrashItems: vi.fn(),
    restoreDocument: vi.fn(),
    permanentlyDeleteDocument: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { workbenchApi } from "@/lib/api/client";
import TrashPage from "./page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function mockTrashResponse() {
  return {
    items: [
      {
        doc_id: "doc-002",
        tenant_id: "tenant-001",
        collection_id: "coll-001",
        filename: "trashed-report.docx",
        source_file_id: "sf-002",
        deleted_by: "user-001",
        deleted_at: "2024-06-09T12:00:00Z",
        auto_purge_at: "2024-07-09T12:00:00Z",
      },
      {
        doc_id: "doc-003",
        tenant_id: "tenant-001",
        collection_id: "coll-001",
        filename: "old-presentation.pptx",
        source_file_id: "sf-003",
        deleted_by: "user-001",
        deleted_at: "2024-06-08T12:00:00Z",
        auto_purge_at: "2024-07-08T12:00:00Z",
      },
    ],
    total: 2,
  };
}

describe("TrashPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading skeletons", () => {
    vi.mocked(workbenchApi.listTrashItems).mockImplementation(() => new Promise(() => {}));

    const Wrapper = createWrapper();
    render(<TrashPage />, { wrapper: Wrapper });

    expect(screen.getAllByTestId("trash-skeleton")).toHaveLength(4);
  });

  it("renders trashed documents", async () => {
    vi.mocked(workbenchApi.listTrashItems).mockResolvedValue(mockTrashResponse() as any);

    const Wrapper = createWrapper();
    render(<TrashPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("trashed-report.docx")).toBeInTheDocument();
    });

    expect(screen.getByText("old-presentation.pptx")).toBeInTheDocument();
  });

  it("filters documents by search query", async () => {
    const user = userEvent.setup();
    vi.mocked(workbenchApi.listTrashItems).mockResolvedValue(mockTrashResponse() as any);

    const Wrapper = createWrapper();
    render(<TrashPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("trashed-report.docx")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("搜索文件名、文档 ID、集合 ID");
    await user.type(input, "pptx");

    expect(screen.queryByText("trashed-report.docx")).not.toBeInTheDocument();
    expect(screen.getByText("old-presentation.pptx")).toBeInTheDocument();
  });

  it("restores a document", async () => {
    const user = userEvent.setup();
    vi.mocked(workbenchApi.listTrashItems).mockResolvedValue(mockTrashResponse() as any);
    vi.mocked(workbenchApi.restoreDocument).mockResolvedValue({ doc_id: "doc-002", restored: true } as any);

    const Wrapper = createWrapper();
    render(<TrashPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("trashed-report.docx")).toBeInTheDocument();
    });

    const restoreButtons = screen.getAllByRole("button", { name: /恢复/i });
    await user.click(restoreButtons[0]);
    await user.click(screen.getByRole("button", { name: /^恢复$/i }));

    await waitFor(() => {
      expect(workbenchApi.restoreDocument).toHaveBeenCalledWith("doc-002");
    });
  });

  it("permanently deletes a document", async () => {
    const user = userEvent.setup();
    vi.mocked(workbenchApi.listTrashItems).mockResolvedValue(mockTrashResponse() as any);
    vi.mocked(workbenchApi.permanentlyDeleteDocument).mockResolvedValue(undefined as any);

    const Wrapper = createWrapper();
    render(<TrashPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("trashed-report.docx")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button", { name: "" });
    await user.click(deleteButtons[deleteButtons.length - 2]);
    await user.click(screen.getByRole("button", { name: /永久删除/i }));

    await waitFor(() => {
      expect(workbenchApi.permanentlyDeleteDocument).toHaveBeenCalledWith("doc-002");
    });
  });
});
