import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import UploadPage from "./page";
import { workbenchApi } from "@/lib/api/client";
import { BackendGapError, ApiClientError } from "@/lib/api/errors";
import { toast } from "sonner";
import type { WorkbenchTaskView } from "@/lib/api/types";

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

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    me: vi.fn(),
    listCollections: vi.fn(),
    createUpload: vi.fn(),
    uploadFileContent: vi.fn(),
    listTasks: vi.fn(),
  },
  WORKBENCH_BASE: "/api/workbench",
}));

// Provide a mutable store state that tests can override.
let mockStoreState: {
  currentCollectionId: string | null;
  accessScope: Record<string, unknown> | null;
} = {
  currentCollectionId: "coll-001",
  accessScope: { scope_type: "internal", department: "engineering" },
};

// Counter for generating unique upload_ids per createUpload call
let uploadIdCounter = 0;

vi.mock("@/lib/store", () => ({
  useAppStore: Object.assign(
    vi.fn(() => mockStoreState),
    { getState: vi.fn(() => ({ demoToken: null })) }
  ),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

// Mock IntersectionObserver for infinite scroll
class MockIntersectionObserver {
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
}
Object.defineProperty(window, "IntersectionObserver", {
  writable: true,
  configurable: true,
  value: MockIntersectionObserver,
});

const api = workbenchApi as any;

// ── Helpers ──────────────────────────────────────────────────────────────

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function mockTask(overrides?: Partial<WorkbenchTaskView>): WorkbenchTaskView {
  return {
    upload_id: "task-default-001",
    status: "published",
    progress_pct: 100,
    source_file_state: "ready",
    intake_job_state: "completed",
    parse_snapshot_state: "completed",
    ticket_state: "approved",
    published_document_state: "active",
    filename: "document.pdf",
    collection_id: "coll-001",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T01:00:00Z",
    ...overrides,
  };
}

function mockListTasksResponse(overrides?: {
  items?: WorkbenchTaskView[];
  total?: number;
}) {
  return {
    items: overrides?.items ?? [mockTask()],
    total: overrides?.total ?? 1,
  };
}

function createFile(name: string, type: string, size: number): File {
  // Generate content matching requested size (capped at 64KB for test speed).
  const actualSize = Math.max(1, Math.min(size, 64 * 1024));
  return new File(["x".repeat(actualSize)], name, { type });
}

function getCurrentUploadSection(): HTMLElement {
  const heading = screen.queryByText(/当前上传/);
  if (!heading) throw new Error("Current upload section not found");
  return heading.parentElement as HTMLElement;
}

function getFileCardByName(name: string): HTMLElement {
  const section = getCurrentUploadSection();
  const fileNameEl = within(section).getByText(name);
  const card = fileNameEl.closest('[data-slot="card"]') as HTMLElement | null;
  if (!card) throw new Error(`File card for "${name}" not found`);
  return card;
}

// ── Setup / Teardown ─────────────────────────────────────────────────────

describe("UploadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    uploadIdCounter = 0;
    mockStoreState = {
      currentCollectionId: "coll-001",
      accessScope: { scope_type: "internal", department: "engineering" },
    };
    vi.mocked(api.listTasks).mockResolvedValue(mockListTasksResponse());
    vi.mocked(api.createUpload).mockImplementation(() => {
      uploadIdCounter += 1;
      return Promise.resolve({
        upload_id: `upload-${String(uploadIdCounter).padStart(3, "0")}`,
        status: "ready",
      });
    });
    vi.mocked(api.uploadFileContent).mockResolvedValue({
      upload_id: "upload-001",
      status: "uploaded",
      progress_pct: 100,
    } as any);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Header / Badge State ───────────────────────────────────────────────

  describe("Header / Badge State", () => {
    it("shows ready badge when collection and scope are set", async () => {
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("就绪")).toBeInTheDocument();
      });

      expect(screen.getByText("批量入库")).toBeInTheDocument();
    });

    it("shows missing badge when collection is missing", async () => {
      mockStoreState = {
        currentCollectionId: null,
        accessScope: { scope_type: "internal", department: "engineering" },
      };
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/缺少集合或权限范围/)).toBeInTheDocument();
      });
    });

    it("shows missing badge when access scope is missing", async () => {
      mockStoreState = {
        currentCollectionId: "coll-001",
        accessScope: null,
      };
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/缺少集合或权限范围/)).toBeInTheDocument();
      });
    });

    it("shows missing badge when both collection and scope are missing", async () => {
      mockStoreState = { currentCollectionId: null, accessScope: null };
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/缺少集合或权限范围/)).toBeInTheDocument();
      });
    });
  });

  // ── Alert State ────────────────────────────────────────────────────────

  describe("Alert State", () => {
    it("does not show alert when collection and scope are set", async () => {
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("就绪")).toBeInTheDocument();
      });

      expect(
        screen.queryByText(/上传前必须在顶部选择知识库集合/)
      ).not.toBeInTheDocument();
    });

    it("shows alert when collection or scope is missing", async () => {
      mockStoreState = { currentCollectionId: null, accessScope: null };
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(
          screen.getByText(/上传前必须在顶部选择知识库集合/)
        ).toBeInTheDocument();
      });
    });
  });

  // ── File Addition ──────────────────────────────────────────────────────

  describe("File Addition", () => {
    it("adds files via drag-and-drop", async () => {
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const dropZone = screen.getByText(/拖拽文件至此，或点击选择/).closest("div") as HTMLElement;

      const file = createFile(
        "report.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        1024
      );

      const dropEvent = new Event("drop", { bubbles: true });
      Object.defineProperty(dropEvent, "dataTransfer", {
        value: { files: [file] },
      });
      Object.defineProperty(dropEvent, "preventDefault", { value: vi.fn() });
      dropZone.dispatchEvent(dropEvent);

      await waitFor(() => {
        expect(getFileCardByName("report.docx")).toBeInTheDocument();
      });
    });

    it("adds files via file input click", async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createFile(
        "slides.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        2048
      );

      await user.upload(input, file);

      await waitFor(() => {
        expect(getFileCardByName("slides.pptx")).toBeInTheDocument();
      });
    });

    it("rejects unsupported file types", async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createFile("malware.exe", "application/x-msdownload", 1024);

      await user.upload(input, file);

      await waitFor(() => {
        expect(screen.queryByText("malware.exe")).not.toBeInTheDocument();
      });
    });

    it("shows toast error when dropping files without collection/scope", async () => {
      mockStoreState = { currentCollectionId: null, accessScope: null };
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() =>
        expect(screen.getByText(/缺少集合或权限范围/)).toBeInTheDocument()
      );

      const dropZone = screen.getByText(/拖拽文件至此，或点击选择/).closest("div") as HTMLElement;
      const file = createFile("report.docx", "application/pdf", 1024);

      const dropEvent = new Event("drop", { bubbles: true });
      Object.defineProperty(dropEvent, "dataTransfer", {
        value: { files: [file] },
      });
      Object.defineProperty(dropEvent, "preventDefault", { value: vi.fn() });
      dropZone.dispatchEvent(dropEvent);

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          "请先选择知识库集合并配置权限范围"
        );
      });
    });
  });

  // ── File Card Rendering ────────────────────────────────────────────────

  describe("File Card Rendering", () => {
    it("renders file type icon, filename, size, and status badge", async () => {
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [mockTask({ upload_id: "upload-001", status: "uploading" })],
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createFile("my-document.pdf", "application/pdf", 5120);
      await user.upload(input, file);

      await waitFor(() => {
        expect(getFileCardByName("my-document.pdf")).toBeInTheDocument();
      });

      const card = getFileCardByName("my-document.pdf");
      expect(within(card).getByText(/5\.0 KB/)).toBeInTheDocument();
      expect(within(card).getByText(/PDF/)).toBeInTheDocument();
      expect(within(card).getByText("正在上传")).toBeInTheDocument();
    });

    it("renders progress bar for uploading status", async () => {
      vi.mocked(api.createUpload).mockResolvedValue({
        upload_id: "upload-001",
        status: "ready",
      });
      vi.mocked(api.uploadFileContent).mockImplementation(
        () => new Promise(() => {})
      );
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [mockTask({ upload_id: "upload-001", status: "uploading" })],
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createFile("uploading-test.pdf", "application/pdf", 1024);
      await user.upload(input, file);

      await waitFor(() => {
        expect(within(getFileCardByName("uploading-test.pdf")).getByText("正在上传")).toBeInTheDocument();
      });

      const card = getFileCardByName("uploading-test.pdf");
      const progressBars = card.querySelectorAll(
        ".h-1.rounded-full.bg-white\\/\\[0\\.04\\]"
      );
      expect(progressBars.length).toBeGreaterThanOrEqual(1);
    });

    it("renders progress bar for parsing status", async () => {
      vi.mocked(api.createUpload).mockResolvedValue({
        upload_id: "upload-001",
        status: "ready",
      });
      vi.mocked(api.uploadFileContent).mockResolvedValue({
        upload_id: "upload-001",
        status: "parsing",
        progress_pct: 60,
      } as any);
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [mockTask({ upload_id: "upload-001", status: "parsing" })],
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createFile("parsing-test.pdf", "application/pdf", 1024);
      await user.upload(input, file);

      await waitFor(() => {
        expect(within(getFileCardByName("parsing-test.pdf")).getByText("正在解析")).toBeInTheDocument();
      });

      const card = getFileCardByName("parsing-test.pdf");
      const progressBars = card.querySelectorAll(
        ".h-1.rounded-full.bg-white\\/\\[0\\.04\\]"
      );
      expect(progressBars.length).toBeGreaterThanOrEqual(1);
    });

    it("renders progress bar for indexing status", async () => {
      vi.mocked(api.createUpload).mockResolvedValue({
        upload_id: "upload-001",
        status: "ready",
      });
      vi.mocked(api.uploadFileContent).mockResolvedValue({
        upload_id: "upload-001",
        status: "indexing",
        progress_pct: 60,
      } as any);
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [mockTask({ upload_id: "upload-001", status: "indexing" })],
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createFile("indexing-test.pdf", "application/pdf", 1024);
      await user.upload(input, file);

      await waitFor(() => {
        expect(within(getFileCardByName("indexing-test.pdf")).getByText("正在构建索引")).toBeInTheDocument();
      });

      const card = getFileCardByName("indexing-test.pdf");
      const progressBars = card.querySelectorAll(
        ".h-1.rounded-full.bg-white\\/\\[0\\.04\\]"
      );
      expect(progressBars.length).toBeGreaterThanOrEqual(1);
    });

    it("renders error message and retry/remove buttons for failed uploads", async () => {
      vi.mocked(api.createUpload).mockRejectedValue(
        new ApiClientError("CREATE_FAILED", "Upload session failed", 500)
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createFile("failed-test.pdf", "application/pdf", 1024);
      await user.upload(input, file);

      await waitFor(() => {
        expect(screen.getByText(/Upload session failed/)).toBeInTheDocument();
      });

      expect(
        screen.getByRole("button", { name: /重试/ })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /删除/ })
      ).toBeInTheDocument();
    });

    it("removes file when clicking delete", async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createFile("temp.pdf", "application/pdf", 1024);
      await user.upload(input, file);

      await waitFor(() => {
        expect(getFileCardByName("temp.pdf")).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /删除/ }));

      await waitFor(() => {
        expect(screen.queryByText("temp.pdf")).not.toBeInTheDocument();
      });
    });
  });

  // ── Status Transitions via Polling ─────────────────────────────────────

  describe("Status Transitions via Polling", () => {
    it("transitions queued -> uploading -> uploaded", async () => {
      vi.mocked(api.createUpload).mockResolvedValue({
        upload_id: "upload-001",
        status: "ready",
      });
      vi.mocked(api.uploadFileContent).mockResolvedValue({
        upload_id: "upload-001",
        status: "uploaded",
        progress_pct: 100,
      } as any);
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [mockTask({ upload_id: "upload-001", status: "uploaded" })],
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, createFile("transition-test.pdf", "application/pdf", 1024));

      await waitFor(() => {
        expect(within(getFileCardByName("transition-test.pdf")).getByText("已上传")).toBeInTheDocument();
      });

      expect(toast.success).toHaveBeenCalledWith("已上传: transition-test.pdf");
    });

    it("transitions uploaded -> parsing via listTasks polling", async () => {
      vi.mocked(api.createUpload).mockResolvedValue({
        upload_id: "upload-001",
        status: "ready",
      });
      vi.mocked(api.uploadFileContent).mockResolvedValue({
        upload_id: "upload-001",
        status: "uploaded",
        progress_pct: 100,
      } as any);

      // Start by returning uploaded so the file stabilizes in uploaded state
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [
            mockTask({
              upload_id: "upload-001",
              status: "uploaded",
              filename: "poll-test.pdf",
            }),
          ],
          total: 1,
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, createFile("poll-test.pdf", "application/pdf", 1024));

      await waitFor(() => {
        expect(within(getFileCardByName("poll-test.pdf")).getByText("已上传")).toBeInTheDocument();
      });

      // Now switch listTasks to return parsing
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [
            mockTask({
              upload_id: "upload-001",
              status: "parsing",
              filename: "poll-test.pdf",
            }),
          ],
          total: 1,
        })
      );

      // Wait for polling interval to fire (5s while active uploads exist).
      await new Promise((r) => setTimeout(r, 5200));

      await waitFor(() => {
        expect(within(getFileCardByName("poll-test.pdf")).getByText("正在解析")).toBeInTheDocument();
      });
    }, 15000);

    it("transitions reviewing -> approved", async () => {
      vi.mocked(api.createUpload).mockResolvedValue({
        upload_id: "upload-001",
        status: "ready",
      });
      vi.mocked(api.uploadFileContent).mockResolvedValue({
        upload_id: "upload-001",
        status: "reviewing",
        progress_pct: 80,
      } as any);

      // Start with reviewing status
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [
            mockTask({
              upload_id: "upload-001",
              status: "reviewing",
              filename: "approve-test.pdf",
            }),
          ],
          total: 1,
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, createFile("approve-test.pdf", "application/pdf", 1024));

      await waitFor(() => {
        expect(within(getFileCardByName("approve-test.pdf")).getByText("正在等待复核")).toBeInTheDocument();
      });

      // Switch to approved
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [
            mockTask({
              upload_id: "upload-001",
              status: "approved",
              filename: "approve-test.pdf",
            }),
          ],
          total: 1,
        })
      );

      await new Promise((r) => setTimeout(r, 5200));

      await waitFor(() => {
        expect(within(getFileCardByName("approve-test.pdf")).getByText("已批准")).toBeInTheDocument();
      });
    }, 15000);

    it("transitions approved -> published", async () => {
      vi.mocked(api.createUpload).mockResolvedValue({
        upload_id: "upload-001",
        status: "ready",
      });
      vi.mocked(api.uploadFileContent).mockResolvedValue({
        upload_id: "upload-001",
        status: "approved",
        progress_pct: 100,
      } as any);

      // Start with approved status
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [
            mockTask({
              upload_id: "upload-001",
              status: "approved",
              filename: "publish-test.pdf",
            }),
          ],
          total: 1,
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, createFile("publish-test.pdf", "application/pdf", 1024));

      await waitFor(() => {
        expect(within(getFileCardByName("publish-test.pdf")).getByText("已批准")).toBeInTheDocument();
      });

      // Switch to published
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [
            mockTask({
              upload_id: "upload-001",
              status: "published",
              filename: "publish-test.pdf",
            }),
          ],
          total: 1,
        })
      );

      await new Promise((r) => setTimeout(r, 5200));

      await waitFor(() => {
        expect(within(getFileCardByName("publish-test.pdf")).getByText("已发布")).toBeInTheDocument();
      });
    }, 15000);
  });

  // ── Batch Stats Panel ──────────────────────────────────────────────────

  describe("Batch Stats Panel", () => {
    it("does not render stats panel when no files exist", async () => {
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      expect(screen.queryByText("总数")).not.toBeInTheDocument();
    });

    it("renders stats panel once files exist with correct counts", async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(
        input,
        createFile("stats-test.pdf", "application/pdf", 1024)
      );

      await waitFor(() => {
        expect(getFileCardByName("stats-test.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("总数")).toBeInTheDocument();
      // total should be 1
      const totalCard = screen.getByText("总数").closest('[data-slot="card"]') as HTMLElement;
      expect(within(totalCard).getByText("1")).toBeInTheDocument();
    });

    it("shows approved count when file reaches approved status", async () => {
      vi.mocked(api.createUpload).mockResolvedValue({
        upload_id: "upload-001",
        status: "ready",
      });
      vi.mocked(api.uploadFileContent).mockResolvedValue({
        upload_id: "upload-001",
        status: "approved",
        progress_pct: 100,
      } as any);
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [mockTask({ upload_id: "upload-001", status: "approved" })],
        })
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, createFile("approved-stats.pdf", "application/pdf", 1024));

      await waitFor(() => {
        expect(within(getFileCardByName("approved-stats.pdf")).getByText("已批准")).toBeInTheDocument();
      });

      const approvedCard = screen.getByText("已入库").closest('[data-slot="card"]') as HTMLElement;
      expect(within(approvedCard).getByText("1")).toBeInTheDocument();
    });
  });

  // ── Recent Tasks List ──────────────────────────────────────────────────

  describe("Recent Tasks List", () => {
    it("shows loading skeletons while recent tasks are loading", async () => {
      vi.mocked(api.listTasks).mockImplementation(() => new Promise(() => {}));

      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        const skeletons = document.querySelectorAll(".animate-shimmer");
        expect(skeletons.length).toBeGreaterThanOrEqual(1);
      });
    });

    it("renders recent task rows and total count", async () => {
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [
            mockTask({ upload_id: "upload-001", filename: "alpha.pdf" }),
            mockTask({ upload_id: "upload-002", filename: "beta.docx" }),
          ],
          total: 2,
        })
      );

      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("alpha.pdf")).toBeInTheDocument();
      });

      expect(screen.getByText("beta.docx")).toBeInTheDocument();
      expect(screen.getByText(/共 2 条记录/)).toBeInTheDocument();
    });

    it("renders infinite scroll sentinel", async () => {
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({
          items: [mockTask({ upload_id: "upload-001", filename: "alpha.pdf" })],
          total: 50,
        })
      );

      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("alpha.pdf")).toBeInTheDocument();
      });

      const sentinel = document.querySelector(".h-4");
      expect(sentinel).toBeInTheDocument();
    });

    it("shows empty state when no recent tasks exist", async () => {
      vi.mocked(api.listTasks).mockResolvedValue(
        mockListTasksResponse({ items: [], total: 0 })
      );

      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("暂无任务")).toBeInTheDocument();
      });

      expect(
        screen.getByText(/上传文件后将在此显示任务进度/)
      ).toBeInTheDocument();
    });
  });

  // ── Error States ───────────────────────────────────────────────────────

  describe("Error States", () => {
    it("shows generic API error on createUpload failure", async () => {
      vi.mocked(api.createUpload).mockRejectedValue(
        new ApiClientError("CREATE_FAILED", "Server error", 500)
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, createFile("error-test.pdf", "application/pdf", 1024));

      await waitFor(() => {
        expect(screen.getByText("Server error")).toBeInTheDocument();
      });

      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("创建上传会话失败")
      );
    });

    it("shows BackendGap error on createUpload 501", async () => {
      vi.mocked(api.createUpload).mockRejectedValue(
        new BackendGapError("create upload", "/api/workbench/uploads")
      );

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, createFile("gap-test.pdf", "application/pdf", 1024));

      await waitFor(() => {
        // BackendGapError message is displayed on the file card, not the BackendGap component
        expect(screen.getByText(/Backend API not yet implemented/)).toBeInTheDocument();
      });
    });

    it("shows generic API error on listTasks failure", async () => {
      vi.mocked(api.listTasks).mockRejectedValue(
        new ApiClientError("FETCH_FAILED", "Network error", 500)
      );

      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Network error")).toBeInTheDocument();
      });
    });

    it("shows BackendGap error on listTasks 501", async () => {
      vi.mocked(api.listTasks).mockRejectedValue(
        new BackendGapError("list tasks", "/api/workbench/tasks")
      );

      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/后端能力缺口/)).toBeInTheDocument();
      });
    });
  });

  // ── Boundary Cases ─────────────────────────────────────────────────────

  describe("Boundary Cases", () => {
    it("renders many files without crashing", async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const files = Array.from({ length: 30 }, (_, i) =>
        createFile(`doc-${i}.pdf`, "application/pdf", 1024)
      );
      await user.upload(input, files);

      await waitFor(() => {
        expect(getFileCardByName("doc-0.pdf")).toBeInTheDocument();
      });

      expect(getFileCardByName("doc-29.pdf")).toBeInTheDocument();
      const totalCard = screen.getByText("总数").closest('[data-slot="card"]') as HTMLElement;
      expect(within(totalCard).getByText("30")).toBeInTheDocument();
    });

    it("renders very long filename without crashing", async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const longName = "a".repeat(520) + ".pdf";
      await user.upload(input, createFile(longName, "application/pdf", 1024));

      await waitFor(() => {
        expect(getFileCardByName(longName)).toBeInTheDocument();
      });
    });

    it("renders large file size without crashing", async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<UploadPage />, { wrapper: Wrapper });

      await waitFor(() => expect(screen.getByText("就绪")).toBeInTheDocument());

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      // File constructor size is based on blob content; use a large reported size via Object.defineProperty.
      const file = createFile("huge.pdf", "application/pdf", 1);
      Object.defineProperty(file, "size", { value: 1024 * 1024 * 1024 });

      await user.upload(input, file);

      await waitFor(() => {
        expect(getFileCardByName("huge.pdf")).toBeInTheDocument();
      });

      const card = getFileCardByName("huge.pdf");
      expect(within(card).getByText(/1048576\.0 KB/)).toBeInTheDocument();
    });
  });
});
