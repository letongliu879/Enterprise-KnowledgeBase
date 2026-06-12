import { describe, it, expect, vi } from "vitest";

const mockRedirect = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (path: string) => {
    mockRedirect(path);
    // Next.js redirect() throws NEXT_REDIRECT in real usage.
    // For test we just record the call — no throw needed since we
    // test the side effect synchronously via module initialisation.
  },
}));

describe("HomePage", () => {
  it("SHE-001: redirects to /upload on render", async () => {
    const mod = await import("./page");
    // The default export is a component function. Calling it triggers
    // redirect("/upload") via the mocked next/navigation.
    mod.default();
    expect(mockRedirect).toHaveBeenCalledTimes(1);
    expect(mockRedirect).toHaveBeenCalledWith("/upload");
  });
});
