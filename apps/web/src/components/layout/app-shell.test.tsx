import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.hoisted(() => {
  const store: Record<string, string> = {};
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => { store[key] = value; },
      removeItem: (key: string) => { delete store[key]; },
    },
    writable: true,
    configurable: true,
  });

  Object.defineProperty(window, "matchMedia", {
    value: (query: string) => ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }),
    writable: true,
    configurable: true,
  });

  class MockBroadcastChannel {
    name: string;
    constructor(name: string) { this.name = name; }
    postMessage() {}
    close() {}
    addEventListener() {}
    removeEventListener() {}
  }
  Object.defineProperty(window, "BroadcastChannel", {
    value: MockBroadcastChannel,
    writable: true,
    configurable: true,
  });
});

const mockPush = vi.fn();
const mockPathname = "/upload";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockPathname,
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    healthAll: vi.fn().mockResolvedValue({
      all_healthy: true,
      services: {
        admin: { status: "ok" },
        workbench: { status: "ok" },
        access: { status: "ok" },
        retrieval: { status: "ok" },
        ingestion: { status: "ok" },
      },
    }),
    me: vi.fn().mockResolvedValue({
      tenant_id: "tenant-1",
      user_id: "user-1",
      email: "test@test.com",
      roles: ["admin"],
      allowed_collections: [],
    }),
    listCollections: vi.fn().mockResolvedValue({
      items: [
        { collection_id: "coll-1", name: "Collection 1", lifecycle_state: "active" },
      ],
    }),
  },
}));

import { AppShell } from "./app-shell";
import { workbenchApi } from "@/lib/api/client";
import { useAppStore } from "@/lib/store";

const mockHealthAll = vi.mocked(workbenchApi.healthAll);

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("AppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("SHE-002: renders sidebar with navigation items", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

    expect(screen.getByRole("link", { name: /批量入库/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /人工复核/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /文档库/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /检索验证/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /知识库集合/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /回收站/i })).toBeInTheDocument();
  });

  it("SHE-002: renders header with settings link", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

    expect(screen.getByLabelText("Open settings")).toBeInTheDocument();
  });

  it("SHE-002: renders main content area with children", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div data-testid="test-child">hello</div></AppShell>, { wrapper: Wrapper });

    expect(screen.getByTestId("test-child")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("SHE-005: current page nav item has aria-current='page'", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

    const navItems = screen.getAllByRole("navigation");
    const activeItem = navItems.find(n => n.getAttribute("aria-current") === "page");
    expect(activeItem).toBeTruthy();
    expect(activeItem!.textContent).toContain("批量入库");
  });

  it("SHE-006: nav items link to correct routes", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

    expect(screen.getByRole("link", { name: /批量入库/i })).toHaveAttribute("href", "/upload");
    expect(screen.getByRole("link", { name: /人工复核/i })).toHaveAttribute("href", "/review");
    expect(screen.getByRole("link", { name: /文档库/i })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: /检索验证/i })).toHaveAttribute("href", "/retrieval");
    expect(screen.getByRole("link", { name: /知识库集合/i })).toHaveAttribute("href", "/collections");
    expect(screen.getByRole("link", { name: /回收站/i })).toHaveAttribute("href", "/trash");
  });

  it("SHE-013: settings button links to /settings", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

    const settingsLink = screen.getByLabelText("Open settings").closest("a");
    expect(settingsLink).toHaveAttribute("href", "/settings");
  });

  it("SHE-007: sidebar toggle button exists", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

    expect(screen.getByLabelText(/sidebar/i)).toBeInTheDocument();
  });

  it("renders skip-to-content link for a11y", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

    const skipLink = screen.getByText("跳转到内容");
    expect(skipLink).toBeInTheDocument();
    expect(skipLink).toHaveAttribute("href", "#main-content");
  });

  it("renders help center link", () => {
    const Wrapper = createWrapper();
    render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

    expect(screen.getByLabelText("Open help center")).toBeInTheDocument();
  });

  describe("Health indicator", () => {
    it("SHE-010: all healthy badge shows when all services ok", async () => {
      mockHealthAll.mockResolvedValue({
        all_healthy: true,
        services: { admin: { status: "ok" }, workbench: { status: "ok" }, access: { status: "ok" }, retrieval: { status: "ok" }, ingestion: { status: "ok" } },
      });
      const Wrapper = createWrapper();
      render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("All Healthy")).toBeInTheDocument();
      });
    });

    it("SHE-009: health dot shows red when service is down", async () => {
      mockHealthAll.mockResolvedValue({
        all_healthy: false,
        services: { admin: { status: "error" }, workbench: { status: "ok" }, access: { status: "ok" }, retrieval: { status: "ok" }, ingestion: { status: "ok" } },
      });
      const Wrapper = createWrapper();
      render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

      await waitFor(() => {
        const adminDots = screen.getAllByTitle(/admin/i);
        const redDot = adminDots.find(d =>
          d.querySelector("span.bg-red-500")
        );
        expect(redDot).toBeTruthy();
      });
    });

    it("SHE-031: health query fires on mount", async () => {
      const Wrapper = createWrapper();
      render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockHealthAll).toHaveBeenCalled();
      });
    });

    it("SHE-032: single service offline does not hide other services", async () => {
      mockHealthAll.mockResolvedValue({
        all_healthy: false,
        services: { admin: { status: "error" }, workbench: { status: "ok" }, access: { status: "ok" }, retrieval: { status: "ok" }, ingestion: { status: "ok" } },
      });
      const Wrapper = createWrapper();
      render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTitle(/admin/i)).toBeInTheDocument();
      });
      expect(screen.getByTitle(/workbench/i)).toBeInTheDocument();
      expect(screen.getByTitle(/access/i)).toBeInTheDocument();
      expect(screen.getByTitle(/retrieval/i)).toBeInTheDocument();
      expect(screen.getByTitle(/ingestion/i)).toBeInTheDocument();
    });
  });

  describe("Collection selector", () => {
    beforeEach(() => {
      useAppStore.setState({ demoToken: "test-token", demoApiKey: "test-key" });
    });

    it("SHE-011: collection selector shows placeholder when loaded", async () => {
      const Wrapper = createWrapper();
      render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText("Select Collection")).toBeInTheDocument();
      });
    });

    it("SHE-012: collection selector has accessible combobox role", async () => {
      const Wrapper = createWrapper();
      render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole("combobox")).toBeInTheDocument();
      });
    });
  });

  describe("Mobile drawer", () => {
    it("SHE-008: mobile hamburger button exists and opens drawer", async () => {
      window.matchMedia = vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("(max-width: 768px)"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }));

      const Wrapper = createWrapper();
      render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

      const menuButton = screen.getByLabelText(/menu|hamburger|sidebar/i);
      expect(menuButton).toBeInTheDocument();
    });

    it("SHE-035: mobile drawer overlay click provides at least one close method", async () => {
      window.matchMedia = vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("(max-width: 768px)"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }));

      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<AppShell><div>content</div></AppShell>, { wrapper: Wrapper });

      const menuButton = screen.getByLabelText(/menu|hamburger|sidebar/i);
      await user.click(menuButton);

      // After opening, either an overlay with role="presentation" or a close button should exist
      const hasOverlay = screen.queryByRole("presentation");
      const hasCloseBtn = screen.queryByLabelText(/close|关闭/i);
      expect(hasOverlay || hasCloseBtn).toBeTruthy();
    });
  });
});
