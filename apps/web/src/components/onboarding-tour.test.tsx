import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockSetItem = vi.fn();
const mockGetItem = vi.fn();

Object.defineProperty(window, "localStorage", {
  value: {
    getItem: mockGetItem,
    setItem: mockSetItem,
    removeItem: vi.fn(),
  },
  writable: true,
});

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { OnboardingTour } from "./onboarding-tour";

describe("OnboardingTour", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetItem.mockReturnValue(null);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the first step when not completed", () => {
    render(<OnboardingTour />);
    expect(screen.getByText("欢迎使用 Knowledge Workbench")).toBeInTheDocument();
    expect(screen.getByText("批量入库")).toBeInTheDocument();
  });

  it("does not render when already completed", () => {
    mockGetItem.mockReturnValue("true");
    render(<OnboardingTour />);
    expect(screen.queryByText("欢迎使用 Knowledge Workbench")).not.toBeInTheDocument();
  });

  it("navigates to next step", async () => {
    const user = userEvent.setup();
    render(<OnboardingTour />);

    await user.click(screen.getByRole("button", { name: /下一步/i }));
    await waitFor(() => {
      expect(screen.getByText("人工复核")).toBeInTheDocument();
    });
  });

  it("completes tour on last step", async () => {
    const user = userEvent.setup();
    render(<OnboardingTour />);

    await user.click(screen.getByRole("button", { name: /下一步/i }));
    await user.click(screen.getByRole("button", { name: /下一步/i }));
    await user.click(screen.getByRole("button", { name: /下一步/i }));
    await user.click(screen.getByRole("button", { name: /完成/i }));

    expect(mockSetItem).toHaveBeenCalledWith("ekb-onboarding-completed", "true");
  });

  it("can be skipped", async () => {
    const user = userEvent.setup();
    render(<OnboardingTour />);

    await user.click(screen.getByRole("button", { name: /跳过/i }));
    expect(screen.queryByText("欢迎使用 Knowledge Workbench")).not.toBeInTheDocument();
  });
});
