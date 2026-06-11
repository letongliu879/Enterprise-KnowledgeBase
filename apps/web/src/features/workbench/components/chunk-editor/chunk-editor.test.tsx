import { describe, it, expect, beforeAll, afterEach, afterAll, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "@/mocks/server";
import { http, HttpResponse } from "msw";
import {
  buildParseSnapshotChunksResponse,
  buildParseSnapshotChunksEmptyResponse,
  buildPatchChunkResponse,
} from "@/mocks/handlers";
import { ChunkEditorWorkbench } from "./index";
import { ChunkEditModal } from "./chunk-edit-modal";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { toast } from "sonner";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
  vi.clearAllMocks();
});

afterAll(() => {
  server.close();
});

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

// ── Helpers ──────────────────────────────────────────────────────────────

function mockChunksSuccess(items: Array<Record<string, unknown>> = []) {
  server.use(
    http.get("*/api/workbench/parse-snapshots/:id/chunks", () =>
      HttpResponse.json(buildParseSnapshotChunksResponse({ items: items as any, total: items.length }))
    )
  );
}

function mockChunksError(status = 500, message = "Server error") {
  server.use(
    http.get("*/api/workbench/parse-snapshots/:id/chunks", () =>
      new HttpResponse(JSON.stringify({ message }), { status })
    )
  );
}

function mockPatchSuccess() {
  server.use(
    http.patch("*/api/workbench/chunks/:evidence_id", () =>
      HttpResponse.json(buildPatchChunkResponse())
    )
  );
}

function mockPatchError(status = 500, message = "Patch failed") {
  server.use(
    http.patch("*/api/workbench/chunks/:evidence_id", () =>
      new HttpResponse(JSON.stringify({ message }), { status })
    )
  );
}

// ── Layer A: Browse ──────────────────────────────────────────────────────

describe("ChunkEditorWorkbench - Browse", () => {
  it("A1: shows skeleton then renders chunk cards", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "First chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
      {
        evidence_id: "ev-002",
        doc_id: "doc-001",
        content: "Second chunk content",
        section_path: ["Section 2"],
        page_spans: [{ page_from: 2, page_to: 2 }],
        chunk_type: "text",
      },
    ]);

    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    // Skeleton should be visible initially
    expect(document.querySelector("[data-slot='skeleton']")).toBeInTheDocument();

    // After loading, chunks appear
    await waitFor(() => {
      expect(screen.getByText("First chunk content")).toBeInTheDocument();
      expect(screen.getByText("Second chunk content")).toBeInTheDocument();
    });
  });

  it("A2: filters chunks by search query (content and evidence_id)", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-apple",
        doc_id: "doc-001",
        content: "Apple chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
      {
        evidence_id: "ev-banana",
        doc_id: "doc-001",
        content: "Banana chunk content",
        section_path: ["Section 2"],
        page_spans: [{ page_from: 2, page_to: 2 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Apple chunk content")).toBeInTheDocument();
      expect(screen.getByText("Banana chunk content")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search chunks/i);
    await user.type(searchInput, "Apple");

    await waitFor(() => {
      expect(screen.getByText("Apple chunk content")).toBeInTheDocument();
      expect(screen.queryByText("Banana chunk content")).not.toBeInTheDocument();
    });

    // Badge shows filtered count
    expect(screen.getByText("1 / 2")).toBeInTheDocument();

    // Search by evidence_id
    await user.clear(searchInput);
    await user.type(searchInput, "ev-banana");

    await waitFor(() => {
      expect(screen.queryByText("Apple chunk content")).not.toBeInTheDocument();
      expect(screen.getByText("Banana chunk content")).toBeInTheDocument();
    });
  });

  it("A3: shows empty state when no chunks exist", async () => {
    mockChunksSuccess([]);

    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("No chunks found")).toBeInTheDocument();
      expect(
        screen.getByText("This parse snapshot does not contain any chunks yet.")
      ).toBeInTheDocument();
    });
  });

  it("A3b: shows no-match state when search yields nothing", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "First chunk",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("First chunk")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search chunks/i);
    await user.type(searchInput, "nonexistent");

    await waitFor(() => {
      expect(screen.getByText("No chunks found")).toBeInTheDocument();
      expect(screen.getByText("No chunks match your search query.")).toBeInTheDocument();
    });
  });

  it("A4: shows alert on API error", async () => {
    mockChunksError(500, "Failed to load chunks");

    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toBeInTheDocument();
      expect(alert).toHaveTextContent(/Failed to load chunks/);
    });
  });

  it("A5: highlights focused evidence chunk with ring border", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-target",
        doc_id: "doc-001",
        content: "Target chunk to highlight",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const Wrapper = createWrapper();
    render(
      <ChunkEditorWorkbench
        parseSnapshotId="ps-001"
        mode="pre-publish"
        focusEvidenceId="ev-target"
      />,
      { wrapper: Wrapper }
    );

    await waitFor(() => {
      const targetCard = screen.getByText("Target chunk to highlight").closest("[data-slot='card']");
      expect(targetCard).toHaveClass("ring-2");
    });
  });
});

// ── Layer B: Edit Modal ──────────────────────────────────────────────────

describe("ChunkEditorWorkbench - Edit Modal", () => {
  it("B1: opens modal with pre-filled data on edit click", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "First chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
        metadata: { key: "value" },
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("First chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("First chunk content").closest("[data-slot='card']");
    const editBtn = card?.querySelector("button");
    expect(editBtn).toBeTruthy();
    await user.click(editBtn!);

    // Modal should be visible
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    // Content field pre-filled
    const contentTextarea = screen.getByLabelText(/Content/i) as HTMLTextAreaElement;
    expect(contentTextarea.value).toBe("First chunk content");

    // Edit reason empty initially
    const editReasonInput = screen.getByLabelText(/Edit Reason/i) as HTMLInputElement;
    expect(editReasonInput.value).toBe("");

    // Section path pre-filled as JSON
    const sectionPathTextarea = screen.getByLabelText(/Section Path/i) as HTMLTextAreaElement;
    expect(sectionPathTextarea.value).toContain("Section 1");
  });

  it("B2: pre-publish mode shows orange title, Save Draft and Submit buttons", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "Chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("Chunk content").closest("[data-slot='card']");
    await user.click(card!.querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    expect(screen.getByText(/Edit Chunk \(Pre-publish\)/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save Draft/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Submit/i })).toBeInTheDocument();
  });

  it("B3: post-publish mode shows blue title, only Save button, disabled section_path", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "Chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="post-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("Chunk content").closest("[data-slot='card']");
    await user.click(card!.querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    expect(screen.getByText(/Edit Chunk \(Published\)/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Save$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Save Draft/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Submit/i })).not.toBeInTheDocument();

    const sectionPathTextarea = screen.getByLabelText(/Section Path/i) as HTMLTextAreaElement;
    expect(sectionPathTextarea).toBeDisabled();
  });

  it("B4: disables Save/Save Draft when content is empty", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "Chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="post-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("Chunk content").closest("[data-slot='card']");
    await user.click(card!.querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    // Initially enabled because content is non-empty
    const saveBtn = screen.getByRole("button", { name: /^Save$/i });
    expect(saveBtn).not.toBeDisabled();

    // Clear content
    const contentTextarea = screen.getByLabelText(/Content/i) as HTMLTextAreaElement;
    await user.clear(contentTextarea);

    await waitFor(() => {
      expect(saveBtn).toBeDisabled();
    });
  });

  it("B5: disables Submit when edit_reason is empty (pre-publish only)", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "Chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("Chunk content").closest("[data-slot='card']");
    await user.click(card!.querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const submitBtn = screen.getByRole("button", { name: /Submit/i });

    // Initially disabled because edit_reason is empty
    expect(submitBtn).toBeDisabled();

    // Fill edit reason
    const editReasonInput = screen.getByLabelText(/Edit Reason/i) as HTMLInputElement;
    await user.type(editReasonInput, "Fixing typo");

    await waitFor(() => {
      expect(submitBtn).not.toBeDisabled();
    });
  });

  it("B6: tolerates invalid JSON in section_path and metadata (buildData ignores error)", async () => {
    const onSaveDraft = vi.fn();
    const chunk = {
      evidence_id: "ev-001",
      doc_id: "doc-001",
      content: "Original content",
      section_path: ["Section 1"],
      page_spans: [{ page_from: 1, page_to: 1 }],
      chunk_type: "text",
      metadata: { key: "value" },
    };

    const user = userEvent.setup();
    render(
      <ChunkEditModal
        open={true}
        mode="pre-publish"
        chunk={chunk as any}
        onSaveDraft={onSaveDraft}
        onCancel={() => {}}
      />
    );

    const sectionPathTextarea = screen.getByLabelText(/Section Path/i) as HTMLTextAreaElement;
    const metadataTextarea = screen.getByLabelText(/Metadata/i) as HTMLTextAreaElement;

    // Enter invalid JSON
    await user.clear(sectionPathTextarea);
    await user.type(sectionPathTextarea, "not valid json");

    await user.clear(metadataTextarea);
    await user.type(metadataTextarea, "{{invalid");

    // Click Save Draft
    const saveBtn = screen.getByRole("button", { name: /Save Draft/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(onSaveDraft).toHaveBeenCalledTimes(1);
    });

    const payload = onSaveDraft.mock.calls[0][0];
    // Invalid JSON should be ignored => undefined
    expect(payload.section_path).toBeUndefined();
    expect(payload.metadata).toBeUndefined();
    // Content should still be preserved
    expect(payload.content).toBe("Original content");
  });

  it("B7: closes modal on Cancel click", async () => {
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "Chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("Chunk content").closest("[data-slot='card']");
    await user.click(card!.querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const cancelBtn = screen.getByRole("button", { name: /Cancel/i });
    await user.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});

// ── Layer C: Persist ─────────────────────────────────────────────────────

describe("ChunkEditorWorkbench - Persist", () => {
  it("C1: pre-publish Submit success shows toast, closes modal, refreshes list", async () => {
    mockPatchSuccess();
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "Chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="pre-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("Chunk content").closest("[data-slot='card']");
    await user.click(card!.querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    // Fill edit reason to enable Submit
    const editReasonInput = screen.getByLabelText(/Edit Reason/i) as HTMLInputElement;
    await user.type(editReasonInput, "Fixing typo");

    const submitBtn = screen.getByRole("button", { name: /Submit/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("Chunk updated");
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("C2: post-publish Save success shows toast, closes modal, refreshes list", async () => {
    mockPatchSuccess();
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "Chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="post-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("Chunk content").closest("[data-slot='card']");
    await user.click(card!.querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    // Modify content
    const contentTextarea = screen.getByLabelText(/Content/i) as HTMLTextAreaElement;
    await user.clear(contentTextarea);
    await user.type(contentTextarea, "Updated chunk content");

    const saveBtn = screen.getByRole("button", { name: /^Save$/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("Chunk updated");
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("C3: patch failure shows error toast and keeps modal open", async () => {
    mockPatchError(500, "Patch failed");
    mockChunksSuccess([
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "Chunk content",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
      },
    ]);

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<ChunkEditorWorkbench parseSnapshotId="ps-001" mode="post-publish" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText("Chunk content")).toBeInTheDocument();
    });

    const card = screen.getByText("Chunk content").closest("[data-slot='card']");
    await user.click(card!.querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const saveBtn = screen.getByRole("button", { name: /^Save$/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Patch failed");
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });
});
