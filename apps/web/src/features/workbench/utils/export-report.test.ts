import { describe, it, expect } from "vitest";
import { generateMarkdownReport } from "./export-report";

describe("generateMarkdownReport - 审核报告生成", () => {
  it("happy path: 包含工单基本信息和发现", () => {
    const report = generateMarkdownReport({
      ticket: {
        ticket_id: "ticket-001",
        collection_id: "coll-001",
        status: "reviewing",
        doc_id: "doc-001",
        created_at: "2024-06-15T10:00:00Z",
      },
      document: {
        filename: "report.pdf",
        doc_id: "doc-001",
      },
      findings: [
        {
          finding_id: "f-001",
          severity: "critical",
          category: "security",
          problem_summary: "敏感信息泄露",
          source_quote: "密码: 123456",
          state: "open",
        },
        {
          finding_id: "f-002",
          severity: "low",
          category: "format",
          problem_summary: "格式不规范",
          state: "open",
          confidence: 0.85,
        },
      ],
      decisionLabel: "Approved",
    });

    expect(report).toContain("# 审核报告");
    expect(report).toContain("ticket-001");
    expect(report).toContain("coll-001");
    expect(report).toContain("report.pdf");
    expect(report).toContain("[Critical]");
    expect(report).toContain("敏感信息泄露");
    expect(report).toContain("[Low]");
    expect(report).toContain("格式不规范");
    expect(report).toContain("85%");
    expect(report).toContain("Approved");
  });

  it("边界: 没有 findings 时显示'暂无发现'", () => {
    const report = generateMarkdownReport({
      ticket: { ticket_id: "t-001", status: "pending" },
    });
    expect(report).toContain("暂无发现");
  });

  it("边界: 只有 ticket 没有 document", () => {
    const report = generateMarkdownReport({
      ticket: { ticket_id: "t-002", doc_id: "doc-002" },
    });
    expect(report).toContain("t-002");
    expect(report).toContain("doc-002");
  });
});
