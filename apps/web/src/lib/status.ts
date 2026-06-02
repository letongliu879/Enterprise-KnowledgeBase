export function normalizeStatus(status?: string | null): string {
  return String(status || "").toLowerCase().trim();
}

export function formatTicketStatusLabel(status?: string | null): string {
  const normalized = normalizeStatus(status);
  const labels: Record<string, string> = {
    pending: "Pending",
    approved: "Approved",
    rejected: "Rejected",
    published: "Published",
    failed: "Failed",
    uploading: "Uploading",
    parsing: "Parsing",
    reviewing: "Reviewing",
    indexing: "Indexing",
    archived: "Archived",
    retracted: "Retracted",
    system_decided: "System Decided",
  };
  return labels[normalized] || normalized || "Unknown";
}

export function formatReviewDecisionLabel(decision?: string | null): string {
  const normalized = normalizeStatus(decision);
  const labels: Record<string, string> = {
    approve: "Approve",
    approved: "Approved",
    reject: "Reject",
    rejected: "Rejected",
    return: "Return",
    review: "Review",
    pass: "Pass",
    fail: "Fail",
    quarantine: "Quarantine",
    request_changes: "Request Changes",
  };
  return labels[normalized] || normalized || "Unknown";
}

export function formatNextActionLabel(action?: string | null): string {
  const normalized = normalizeStatus(action);
  const labels: Record<string, string> = {
    review: "Needs Review",
    approve: "Awaiting Approval",
    revise: "Needs Revision",
    publish: "Ready to Publish",
    reprocess: "Reprocess Required",
  };
  return labels[normalized] || normalized || "Unknown";
}

export function formatFailureStageLabel(stage?: string | null): string {
  const normalized = normalizeStatus(stage);
  const labels: Record<string, string> = {
    intake: "Intake",
    parsing: "Parsing",
    review: "Review",
    indexing: "Indexing",
    publishing: "Publishing",
    retrieval: "Retrieval",
    unknown: "Unknown",
  };
  return labels[normalized] || normalized || "Unknown";
}
