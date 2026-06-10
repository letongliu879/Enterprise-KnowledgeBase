import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "./empty-state";

function MockIcon({ className }: { className?: string }) {
  return <svg data-testid="mock-icon" className={className} />;
}

describe("EmptyState - 纯 title", () => {
  it("happy path: 仅传 title 和 icon 能正确渲染", () => {
    render(<EmptyState icon={MockIcon} title="No Data" />);
    expect(screen.getByText("No Data")).toBeInTheDocument();
    expect(screen.getByTestId("mock-icon")).toBeInTheDocument();
  });

  it("空值: 无 description 时不渲染 description 段落", () => {
    render(<EmptyState icon={MockIcon} title="No Data" />);
    expect(screen.queryByText(/description/i)).not.toBeInTheDocument();
  });
});

describe("EmptyState - title + description", () => {
  it("happy path: title 和 description 都渲染", () => {
    render(
      <EmptyState icon={MockIcon} title="Empty" description="Nothing here yet" />
    );
    expect(screen.getByText("Empty")).toBeInTheDocument();
    expect(screen.getByText("Nothing here yet")).toBeInTheDocument();
  });

  it("边界: description 为空字符串时不渲染", () => {
    render(<EmptyState icon={MockIcon} title="Empty" description="" />);
    const paragraphs = screen.getByText("Empty").parentElement?.querySelectorAll("p");
    expect(paragraphs?.length ?? 0).toBe(0);
  });
});

describe("EmptyState - title + description + action", () => {
  it("happy path: action 被渲染为 button", () => {
    render(
      <EmptyState
        icon={MockIcon}
        title="No Items"
        description="Add your first item"
        action={<button type="button">Add Item</button>}
      />
    );
    expect(screen.getByText("No Items")).toBeInTheDocument();
    expect(screen.getByText("Add your first item")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Item" })).toBeInTheDocument();
  });

  it("边界: action 为复杂 ReactNode 也能渲染", () => {
    render(
      <EmptyState
        icon={MockIcon}
        title="No Items"
        action={
          <div>
            <span>Action</span>
          </div>
        }
      />
    );
    expect(screen.getByText("Action")).toBeInTheDocument();
  });
});

describe("EmptyState - action 渲染为 button", () => {
  it("happy path: action 是 button 元素", () => {
    render(
      <EmptyState
        icon={MockIcon}
        title="No Data"
        action={<button type="button">Click Me</button>}
      />
    );
    const btn = screen.getByRole("button", { name: "Click Me" });
    expect(btn).toBeInTheDocument();
    expect(btn.tagName.toLowerCase()).toBe("button");
  });

  it("边界: action 是 a 标签也能渲染", () => {
    render(
      <EmptyState
        icon={MockIcon}
        title="No Data"
        action={<a href="/link">Go to Link</a>}
      />
    );
    expect(screen.getByText("Go to Link")).toBeInTheDocument();
  });
});
