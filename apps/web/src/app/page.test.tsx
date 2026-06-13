import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api/client", () => ({
  workbenchApi: {
    getDashboard: vi.fn(() => new Promise(() => {})),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import HomePage from "./page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("HomePage", () => {
  it("renders the dashboard with 4 stat skeletons while loading", () => {
    const Wrapper = createWrapper();
    render(<HomePage />, { wrapper: Wrapper });

    const skeletons = screen.getAllByTestId("stat-skeleton");
    expect(skeletons).toHaveLength(4);
  });
});
