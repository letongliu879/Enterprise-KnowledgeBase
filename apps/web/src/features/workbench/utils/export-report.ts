"use client";

import type { Finding } from "@/features/workbench/types/finding";
import type { WorkspaceTicketView } from "@/lib/api/types";

interface ExportData {
  ticket?: WorkspaceTicketView | Record<string, unknown> | null;
  findings?: Finding[];
  document?: {
    filename?: string | null;
    doc_id?: string | null;
  } | null;
  decisionLabel?: string;
}

export function generateMarkdownReport(data: ExportData): string {
  const { ticket, findings, document, decisionLabel } = data;

  const lines: string[] = [];

  lines.push("# 审核报告\n");
  lines.push(`**生成时间**: ${new Date().toLocaleString("zh-CN")}\n`);

  // Basic info
  lines.push("## 基本信息\n");
  lines.push(`| 字段 | 值 |`);
  lines.push(`|------|----|`);
  lines.push(`| 工单 ID | ${ticket?.ticket_id || "-"} |`);
  lines.push(`| 集合 ID | ${ticket?.collection_id || "-"} |`);
  lines.push(`| 文档 ID | ${document?.doc_id || ticket?.doc_id || "-"} |`);
  lines.push(`| 文件名 | ${document?.filename || ticket?.filename || "-"} |`);
  lines.push(`| 状态 | ${ticket?.status || "-"} |`);
  lines.push(`| 决策 | ${decisionLabel || ticket?.decision || "待决策"} |`);
  lines.push(`| 创建时间 | ${ticket?.created_at ? String(ticket.created_at) : "-"} |`);
  if (ticket?.decision_reason) {
    lines.push(`| 决策原因 | ${ticket.decision_reason} |`);
  }
  lines.push("");

  // Findings
  if (findings && findings.length > 0) {
    lines.push("## Agent 审核发现\n");
    const severityOrder = ["critical", "high", "medium", "low", "info"];
    const severityLabel: Record<string, string> = {
      critical: "Critical", high: "High", medium: "Medium", low: "Low", info: "Info",
    };
    const sorted = [...findings].sort(
      (a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity)
    );

    for (const finding of sorted) {
      const label = severityLabel[finding.severity] || finding.severity;
      lines.push(`### [${label}] ${finding.problem_summary}`);
      if (finding.category) lines.push(`\n- **分类**: ${finding.category}`);
      if (finding.confidence !== undefined) lines.push(`\n- **置信度**: ${Math.round(finding.confidence * 100)}%`);
      if (finding.source_quote) lines.push(`\n> ${finding.source_quote}`);
      lines.push("");
    }
  } else {
    lines.push("## Agent 审核发现\n\n暂无发现。\n");
  }

  return lines.join("\n");
}

export function downloadAsFile(content: string, filename: string, mimeType: string = "text/markdown") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function handleExportReport(data: ExportData) {
  const markdown = generateMarkdownReport(data);
  const filename = `review-report-${data.ticket?.ticket_id || "unknown"}-${new Date().toISOString().split("T")[0]}.md`;
  downloadAsFile(markdown, filename);
}
