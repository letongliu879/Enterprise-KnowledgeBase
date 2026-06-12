import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Breadcrumb } from "./breadcrumb";

const mockUsePathname = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...rest }: any) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

describe("Breadcrumb - 已知路由标签", () => {
  it("SHE-004: /upload -> 首页 > 批量入库", () => {
    mockUsePathname.mockReturnValue("/upload");
    render(<Breadcrumb />);
    expect(screen.getByText("批量入库")).toBeInTheDocument();
    expect(screen.getByText("首页")).toBeInTheDocument();
  });

  it("SHE-004: /documents -> 显示文档库", () => {
    mockUsePathname.mockReturnValue("/documents");
    render(<Breadcrumb />);
    expect(screen.getByText("文档库")).toBeInTheDocument();
  });

  it("SHE-004: /review -> 显示人工复核", () => {
    mockUsePathname.mockReturnValue("/review");
    render(<Breadcrumb />);
    expect(screen.getByText("人工复核")).toBeInTheDocument();
  });

  it("SHE-004: /settings -> 显示设置", () => {
    mockUsePathname.mockReturnValue("/settings");
    render(<Breadcrumb />);
    expect(screen.getByText("设置")).toBeInTheDocument();
  });

  it("SHE-004: 首页带有 Home 图标和正确 href", () => {
    mockUsePathname.mockReturnValue("/upload");
    render(<Breadcrumb />);
    const homeLink = screen.getByText("首页").closest("a");
    expect(homeLink).toHaveAttribute("href", "/");
  });
});

describe("Breadcrumb - 动态段识别", () => {
  it("SHE-004: UUID 段显示父段前缀文档 详情", () => {
    mockUsePathname.mockReturnValue("/documents/550e8400-e29b-41d4-a716-446655440000");
    render(<Breadcrumb />);
    expect(screen.getByText("文档 详情")).toBeInTheDocument();
  });

  it("SHE-004: 20 位以上 hex 段显示为工单 详情", () => {
    mockUsePathname.mockReturnValue("/review/abcdef1234567890abcdef1234567890ab");
    render(<Breadcrumb />);
    expect(screen.getByText("工单 详情")).toBeInTheDocument();
  });

  it("SHE-004: 纯数字 6 位以上段显示动态前缀上传 详情", () => {
    mockUsePathname.mockReturnValue("/upload/1234567");
    render(<Breadcrumb />);
    expect(screen.getByText("上传 详情")).toBeInTheDocument();
  });

  it("SHE-004: 未知父级段 ID 使用父段名做前缀", () => {
    mockUsePathname.mockReturnValue("/custom/550e8400-e29b-41d4-a716-446655440000");
    render(<Breadcrumb />);
    expect(screen.getByText("custom 详情")).toBeInTheDocument();
  });

  it("SHE-004: 集合 ID 显示为集合 详情", () => {
    mockUsePathname.mockReturnValue("/collections/abcdef1234567890abcdef1234567890ab");
    render(<Breadcrumb />);
    expect(screen.getByText("集合 详情")).toBeInTheDocument();
  });
});

describe("Breadcrumb - 边界与路径", () => {
  it("SHE-004: 根路径返回 null", () => {
    mockUsePathname.mockReturnValue("/");
    const { container } = render(<Breadcrumb />);
    expect(container.innerHTML).toBe("");
  });

  it("SHE-004: 最后一段非链接（span）", () => {
    mockUsePathname.mockReturnValue("/upload");
    render(<Breadcrumb />);
    const lastEl = screen.getByText("批量入库");
    expect(lastEl.tagName).toBe("SPAN");
  });

  it("SHE-004: 中间段为链接", () => {
    mockUsePathname.mockReturnValue("/settings/api-keys");
    render(<Breadcrumb />);
    const settingsLink = screen.getByText("设置").closest("a");
    expect(settingsLink).toHaveAttribute("href", "/settings");
  });

  it("SHE-004: 未知段名原文显示", () => {
    mockUsePathname.mockReturnValue("/unknown-route");
    render(<Breadcrumb />);
    expect(screen.getByText("unknown-route")).toBeInTheDocument();
  });

  it("SHE-004: Breadcrumb 带有 aria-label", () => {
    mockUsePathname.mockReturnValue("/upload");
    render(<Breadcrumb />);
    expect(screen.getByLabelText("Breadcrumb")).toBeInTheDocument();
  });
});
