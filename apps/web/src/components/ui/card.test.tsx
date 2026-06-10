import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
} from "./card";

describe("Card - 默认渲染", () => {
  it("happy path: 默认 Card 渲染 children", () => {
    render(<Card>Card Content</Card>);
    const card = screen.getByText("Card Content");
    expect(card).toBeInTheDocument();
    expect(card).toHaveAttribute("data-slot", "card");
  });

  it("空值: 无 children 也能渲染", () => {
    render(<Card />);
    const card = document.querySelector("[data-slot='card']");
    expect(card).toBeInTheDocument();
  });
});

describe("Card - interactive", () => {
  it("happy path: interactive=true 应用 cursor-pointer", () => {
    render(<Card interactive>Interactive Card</Card>);
    const card = screen.getByText("Interactive Card");
    expect(card.className).toContain("cursor-pointer");
  });

  it("happy path: interactive=false 不应用 cursor-pointer", () => {
    render(<Card>Non-Interactive</Card>);
    const card = screen.getByText("Non-Interactive");
    expect(card.className).not.toContain("cursor-pointer");
  });
});

describe("Card - size", () => {
  it("happy path: size=sm 应用 data-size=sm", () => {
    render(<Card size="sm">Small Card</Card>);
    const card = screen.getByText("Small Card");
    expect(card).toHaveAttribute("data-size", "sm");
  });

  it("happy path: 默认 size 应用 data-size=default", () => {
    render(<Card>Default Card</Card>);
    const card = screen.getByText("Default Card");
    expect(card).toHaveAttribute("data-size", "default");
  });
});

describe("Card - 组合", () => {
  it("happy path: CardHeader + CardContent + CardFooter 组合渲染", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardDescription>Description</CardDescription>
        </CardHeader>
        <CardContent>Main Content</CardContent>
        <CardFooter>Footer</CardFooter>
      </Card>
    );

    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(screen.getByText("Main Content")).toBeInTheDocument();
    expect(screen.getByText("Footer")).toBeInTheDocument();
  });

  it("边界: CardHeader 和 CardFooter 含 data-slot", () => {
    render(
      <Card>
        <CardHeader>Header</CardHeader>
        <CardContent>Content</CardContent>
        <CardFooter>Footer</CardFooter>
      </Card>
    );

    expect(screen.getByText("Header")).toHaveAttribute("data-slot", "card-header");
    expect(screen.getByText("Content")).toHaveAttribute("data-slot", "card-content");
    expect(screen.getByText("Footer")).toHaveAttribute("data-slot", "card-footer");
  });
});
