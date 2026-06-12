import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { DocumentAnnotations } from "./document-annotations";

describe("DocumentAnnotations", () => {
  it("shows empty state when no annotations", () => {
    render(<DocumentAnnotations annotations={[]} />);
    expect(screen.getByText(/暂无批注/)).toBeInTheDocument();
  });

  it("renders annotation list", () => {
    const annotations = [
      { id: "1", author: "张三", content: "需要确认这段数据的来源", createdAt: "2024-01-15T10:00:00Z" },
      { id: "2", author: "李四", content: "已核实，数据无误", createdAt: "2024-01-16T14:30:00Z" },
    ];
    render(<DocumentAnnotations annotations={annotations} />);
    expect(screen.getByText("张三")).toBeInTheDocument();
    expect(screen.getByText("李四")).toBeInTheDocument();
    expect(screen.getByText(/需要确认这段数据的来源/)).toBeInTheDocument();
  });

  it("allows adding a new annotation", async () => {
    const onAdd = vi.fn();
    render(<DocumentAnnotations annotations={[]} onAdd={onAdd} />);
    await userEvent.type(screen.getByPlaceholderText(/添加批注/i), "新批注内容");
    await userEvent.click(screen.getByRole("button", { name: /提交/i }));
    expect(onAdd).toHaveBeenCalledWith("新批注内容");
  });
});
