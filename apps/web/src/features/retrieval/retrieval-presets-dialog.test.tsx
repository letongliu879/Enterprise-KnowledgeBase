import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { RetrievalPresetsDialog } from "./retrieval-presets-dialog";

// Mock localStorage for retrieval presets
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
  writable: true, configurable: true,
});

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  onLoadPreset: vi.fn(),
  currentQuery: "test query",
  currentCollectionId: "col-123",
  currentRetrievalProfileId: "profile-456",
  currentTokenBudget: 2000,
};

describe("RetrievalPresetsDialog", () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  it("renders when open", () => {
    render(<RetrievalPresetsDialog {...defaultProps} />);
    expect(screen.getByText("检索预设")).toBeInTheDocument();
  });

  it("shows existing presets from localStorage", () => {
    localStorageMock.setItem("ekb-retrieval-presets", JSON.stringify([
      { name: "My Preset", query: "hello", tokenBudget: 3000, },
    ]));
    render(<RetrievalPresetsDialog {...defaultProps} />);
    expect(screen.getByText("My Preset")).toBeInTheDocument();
  });

  it("saves current params as a new preset", async () => {
    render(<RetrievalPresetsDialog {...defaultProps} />);
    await userEvent.type(screen.getByPlaceholderText(/预设名称/i), "Test Preset");
    await userEvent.click(screen.getByRole("button", { name: /保存/i }));
    const saved = JSON.parse(localStorageMock.getItem("ekb-retrieval-presets") || "[]");
    expect(saved).toHaveLength(1);
    expect(saved[0].name).toBe("Test Preset");
  });

  it("loads a preset on click", async () => {
    const onLoadPreset = vi.fn();
    localStorageMock.setItem("ekb-retrieval-presets", JSON.stringify([
      { name: "My Preset", query: "hello", tokenBudget: 3000, collectionId: "col-123", retrievalProfileId: "profile-456" },
    ]));
    render(<RetrievalPresetsDialog {...defaultProps} onLoadPreset={onLoadPreset} />);
    await userEvent.click(screen.getByText("My Preset"));
    expect(onLoadPreset).toHaveBeenCalledWith(expect.objectContaining({ query: "hello", tokenBudget: 3000 }));
  });

  it("deletes a preset", async () => {
    localStorageMock.setItem("ekb-retrieval-presets", JSON.stringify([
      { name: "Preset A", query: "a" },
      { name: "Preset B", query: "b" },
    ]));
    render(<RetrievalPresetsDialog {...defaultProps} />);
    const deleteButtons = screen.getAllByRole("button", { name: /删除预设/i });
    await userEvent.click(deleteButtons[0]);
    const saved = JSON.parse(localStorageMock.getItem("ekb-retrieval-presets") || "[]");
    expect(saved).toHaveLength(1);
    expect(saved[0].name).toBe("Preset B");
  });

  it("does not render when closed", () => {
    const { container } = render(<RetrievalPresetsDialog {...defaultProps} open={false} />);
    expect(container.textContent).not.toContain("检索预设");
  });
});
