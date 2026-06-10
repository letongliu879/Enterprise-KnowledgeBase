import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./badge";

describe("Badge - 默认渲染", () => {
  it("happy path: 渲染默认 variant 并显示 children", () => {
    render(<Badge>Default</Badge>);
    const badge = screen.getByText("Default");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("data-slot", "badge");
  });

  it("空值: 无 children 也能渲染（空内容）", () => {
    render(<Badge />);
    const badge = document.querySelector("[data-slot='badge']");
    expect(badge).toBeInTheDocument();
  });
});

describe("Badge - variant", () => {
  it("happy path: secondary variant 渲染", () => {
    render(<Badge variant="secondary">Secondary</Badge>);
    expect(screen.getByText("Secondary")).toBeInTheDocument();
  });

  it("happy path: destructive variant 渲染", () => {
    render(<Badge variant="destructive">Destructive</Badge>);
    expect(screen.getByText("Destructive")).toBeInTheDocument();
  });

  it("happy path: success variant 渲染", () => {
    render(<Badge variant="success">Success</Badge>);
    expect(screen.getByText("Success")).toBeInTheDocument();
  });

  it("边界: warning variant 渲染", () => {
    render(<Badge variant="warning">Warning</Badge>);
    expect(screen.getByText("Warning")).toBeInTheDocument();
  });

  it("边界: outline variant 渲染", () => {
    render(<Badge variant="outline">Outline</Badge>);
    expect(screen.getByText("Outline")).toBeInTheDocument();
  });
});

describe("Badge - custom className", () => {
  it("happy path: 自定义 className 被应用", () => {
    render(<Badge className="my-custom-badge">Custom</Badge>);
    expect(screen.getByText("Custom")).toHaveClass("my-custom-badge");
  });

  it("边界: 多个自定义 class", () => {
    render(<Badge className="class-a class-b">Multi</Badge>);
    const badge = screen.getByText("Multi");
    expect(badge).toHaveClass("class-a");
    expect(badge).toHaveClass("class-b");
  });
});

describe("Badge - children 渲染", () => {
  it("happy path: 文本 children 正确渲染", () => {
    render(<Badge>Text Child</Badge>);
    expect(screen.getByText("Text Child")).toBeInTheDocument();
  });

  it("边界: 数字 children 正确渲染", () => {
    render(<Badge>{42}</Badge>);
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
