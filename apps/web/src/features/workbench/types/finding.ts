// features/workbench/types/finding.ts

export type FindingSeverity = "critical" | "high" | "medium" | "low" | "info";

export type FindingState = "open" | "resolved";

export interface Finding {
  finding_id: string;
  severity: FindingSeverity;
  category: string;
  problem_summary: string;
  source_quote?: string;
  evidence_id?: string;
  doc_id?: string;
  page_from?: number;
  page_to?: number;
  state: FindingState;
  confidence?: number;
}

export interface AgentReviewResponse {
  ticket_id: string;
  findings: Finding[];
  source?: "projection" | "approval";
}
