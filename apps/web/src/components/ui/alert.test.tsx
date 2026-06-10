import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Alert, AlertTitle, AlertDescription } from "./alert";

describe("Alert - 默认 variant", () => {
  it("happy path: 默认 variant 渲染", () => {
    render(<Alert>Alert Content</Alert>);
    const alert = screen.getByText("Alert Content");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveAttribute("role", "alert");
    expect(alert).toHaveAttribute("data-slot", "alert");
  });

  it("空值: 无 children 也能渲染", () => {
    render(<Alert />);
    const alert = document.querySelector("[data-slot='alert']");
    expect(alert).toBeInTheDocument();
  });
});

describe("Alert - destructive variant", () => {
  it("happy path: destructive variant 渲染", () => {
    render(<Alert variant="destructive">Danger</Alert>);
    const alert = screen.getByText("Danger");
    expect(alert).toBeInTheDocument();
  });

  it("边界: variant 切换不影响基础结构", () => {
    const { rerender } = render(<Alert variant="default">Switch</Alert>);
    expect(screen.getByText("Switch")).toBeInTheDocument();

    rerender(<Alert variant="destructive">Switch</Alert>);
    expect(screen.getByText("Switch")).toBeInTheDocument();
  });
});

describe("Alert - AlertTitle + AlertDescription 组合", () => {
  it("happy path: AlertTitle 和 AlertDescription 组合渲染", () => {
    render(
      <Alert>
        <AlertTitle>Title</AlertTitle>
        <AlertDescription>Description</AlertDescription>
      </Alert>
    );
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
  });

  it("happy path: AlertTitle 含 data-slot", () => {
    render(
      <Alert>
        <AlertTitle>My Title</AlertTitle>
      </Alert>
    );
    expect(screen.getByText("My Title")).toHaveAttribute("data-slot", "alert-title");
  });

  it("happy path: AlertDescription 含 data-slot", () => {
    render(
      <Alert>
        <AlertDescription>My Desc</AlertDescription>
      </Alert>
    );
    expect(screen.getByText("My Desc")).toHaveAttribute("data-slot", "alert-description");
  });

  it("边界: 含图标和标题描述的组合", () => {
    render(
      <Alert>
        <svg data-testid="alert-icon" />
        <AlertTitle>With Icon</AlertTitle>
        <AlertDescription>Details here</AlertDescription>
      </Alert>
    );
    expect(screen.getByTestId("alert-icon")).toBeInTheDocument();
    expect(screen.getByText("With Icon")).toBeInTheDocument();
    expect(screen.getByText("Details here")).toBeInTheDocument();
  });
});
