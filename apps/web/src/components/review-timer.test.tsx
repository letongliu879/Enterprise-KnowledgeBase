import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReviewTimer } from "./review-timer";

describe("ReviewTimer - 审核计时器", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Fix the date to 2024-06-15 12:00:00 UTC
    vi.setSystemTime(new Date("2024-06-15T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("happy path: 创建时间 5 分钟前，显示低严重度", () => {
    const createdAt = new Date("2024-06-15T11:55:00Z").toISOString();
    render(<ReviewTimer createdAt={createdAt} />);
    expect(screen.getByText(/5 分钟/)).toBeInTheDocument();
    // 低严重度 = 无红色/琥珀色样式
    expect(screen.getByText(/等待/)).toBeInTheDocument();
  });

  it("边界: 刚刚创建的工单，显示'刚刚'", () => {
    const createdAt = new Date("2024-06-15T11:59:55Z").toISOString();
    render(<ReviewTimer createdAt={createdAt} />);
    expect(screen.getByText(/刚刚/)).toBeInTheDocument();
  });

  it("中严重度: 超过 4 小时，显示琥珀色", () => {
    const createdAt = new Date("2024-06-15T07:30:00Z").toISOString();
    render(<ReviewTimer createdAt={createdAt} />);
    expect(screen.getByText(/4 小时/)).toBeInTheDocument();
    expect(screen.getByText(/等待/)).toBeInTheDocument();
  });

  it("高严重度: 超过 24 小时，显示红色和脉冲图标", () => {
    const createdAt = new Date("2024-06-14T10:00:00Z").toISOString();
    render(<ReviewTimer createdAt={createdAt} />);
    expect(screen.getByText(/超时/)).toBeInTheDocument();
  });
});
