import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

describe("cn utility", () => {
  it("merges class names", () => {
    expect(cn("px-4", "px-2")).toBe("px-2");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("returns empty string for no inputs", () => {
    expect(cn()).toBe("");
  });
});

describe("Badge component", () => {
  it("renders default variant", () => {
    render(<Badge>Test</Badge>);
    const badge = screen.getByText("Test");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("data-slot", "badge");
  });

  it("renders with custom className", () => {
    render(<Badge className="custom-class">Custom</Badge>);
    expect(screen.getByText("Custom")).toHaveClass("custom-class");
  });
});

describe("Card component", () => {
  it("renders basic card", () => {
    render(<Card>Content</Card>);
    const card = screen.getByText("Content");
    expect(card).toBeInTheDocument();
    expect(card).toHaveAttribute("data-slot", "card");
  });

  it("applies interactive styles when interactive prop is true", () => {
    render(<Card interactive>Interactive</Card>);
    const card = screen.getByText("Interactive");
    expect(card.className).toContain("cursor-pointer");
  });
});
