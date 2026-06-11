import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TicketDetailPage } from "./ticket-detail";
import { workbenchApi } from "@/lib/api/client";
import { buildWorkspaceDetailResponse } from "@/mocks/handlers";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    getWorkspaceDetail: vi.fn(),
    decideTicket: vi.fn(),
  },
}));

vi.mock("@/features/workbench/components/chunk-editor", () => ({
  ChunkEditorWorkbench: () => <div data-testid="chunk-editor-mock" />,
}));
vi.mock("@/components/document-workbench/document-viewer", () => ({
  DocumentViewer: () => <div data-testid="document-viewer-mock" />,
}));
vi.mock("@/features/workbench/components/agent-review", () => ({
  AgentReviewPanel: () => <div data-testid="agent-review-mock" />,
}));

const api = workbenchApi;

describe("Debug", () => {
  beforeEach(() => {
    vi.mocked(api.getWorkspaceDetail).mockReset();
  });

  it("back button", async () => {
    vi.mocked(api.getWorkspaceDetail).mockResolvedValue(buildWorkspaceDetailResponse());
    const { container } = render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <TicketDetailPage ticketId="ticket-001" backHref="/review" />
      </QueryClientProvider>
    );
    await waitFor(() => expect(api.getWorkspaceDetail).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 100));
    console.log("BACK HTML:", container.innerHTML.slice(0, 1500));
    expect(true).toBe(true);
  });
});
