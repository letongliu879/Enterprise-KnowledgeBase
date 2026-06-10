import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BackendGap } from "./backend-gap";

describe("BackendGap - feature 渲染", () => {
  it("happy path: feature 显示在 AlertTitle 中", () => {
    render(<BackendGap feature="Upload" endpoint="/api/upload" />);
    expect(screen.getByText(/后端能力缺口 — Upload/)).toBeInTheDocument();
  });

  it("边界: feature 含特殊字符", () => {
    render(<BackendGap feature="功能 🚀" endpoint="/api/test" />);
    expect(screen.getByText(/后端能力缺口 — 功能 🚀/)).toBeInTheDocument();
  });
});

describe("BackendGap - endpoint 渲染", () => {
  it("happy path: endpoint 显示在 code 标签中", () => {
    render(<BackendGap feature="Download" endpoint="/api/v1/files/download" />);
    expect(screen.getByText("/api/v1/files/download")).toBeInTheDocument();
  });

  it("空值: endpoint 为空字符串也能渲染", () => {
    const { container } = render(<BackendGap feature="X" endpoint="" />);
    const code = container.querySelector("code");
    expect(code).toBeInTheDocument();
    expect(code?.textContent).toBe("");
  });

  it("边界: endpoint 含特殊字符和查询参数", () => {
    render(<BackendGap feature="Search" endpoint="/api/search?q=测试&limit=10" />);
    expect(screen.getByText("/api/search?q=测试&limit=10")).toBeInTheDocument();
  });
});

describe("BackendGap - 完整渲染", () => {
  it("happy path: Alert、AlertTitle、AlertDescription 组合渲染", () => {
    const { container } = render(
      <BackendGap feature="FeatureA" endpoint="/api/a" />
    );
    expect(container.querySelector("[role='alert']")).toBeInTheDocument();
    expect(screen.getByText(/后端能力缺口 — FeatureA/)).toBeInTheDocument();
    expect(screen.getByText("该功能依赖的后端 API 尚未实现。")).toBeInTheDocument();
    expect(screen.getByText("/api/a")).toBeInTheDocument();
  });

  it("边界: feature 和 endpoint 超长", () => {
    const longFeature = "Feature".repeat(50);
    const longEndpoint = "/api/" + "a".repeat(200);
    render(<BackendGap feature={longFeature} endpoint={longEndpoint} />);
    expect(screen.getByText(longEndpoint)).toBeInTheDocument();
  });
});
