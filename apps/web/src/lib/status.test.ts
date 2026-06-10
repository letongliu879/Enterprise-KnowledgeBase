import { describe, it, expect } from "vitest";
import {
  normalizeStatus,
  formatTicketStatusLabel,
  formatReviewDecisionLabel,
  formatNextActionLabel,
  formatFailureStageLabel,
} from "./status";

describe("status - normalizeStatus", () => {
  it("happy path: 已知状态转小写并去空格", () => {
    expect(normalizeStatus("Pending")).toBe("pending");
    expect(normalizeStatus("APPROVED")).toBe("approved");
  });

  it("空值: null 返回空串", () => {
    expect(normalizeStatus(null)).toBe("");
  });

  it("空值: undefined 返回空串", () => {
    expect(normalizeStatus(undefined)).toBe("");
  });

  it("空值: 空串返回空串", () => {
    expect(normalizeStatus("")).toBe("");
  });

  it("边界: 未知字符串返回小写", () => {
    expect(normalizeStatus("UNKNOWN")).toBe("unknown");
  });

  it("边界: 含前后空格 trimming", () => {
    expect(normalizeStatus("  Pending  ")).toBe("pending");
  });
});

describe("status - formatTicketStatusLabel", () => {
  it("happy path: 已知状态返回对应 label", () => {
    expect(formatTicketStatusLabel("pending")).toBe("Pending");
    expect(formatTicketStatusLabel("approved")).toBe("Approved");
    expect(formatTicketStatusLabel("failed")).toBe("Failed");
    expect(formatTicketStatusLabel("system_decided")).toBe("System Decided");
  });

  it("空值: null 返回 Unknown", () => {
    expect(formatTicketStatusLabel(null)).toBe("Unknown");
  });

  it("空值: undefined 返回 Unknown", () => {
    expect(formatTicketStatusLabel(undefined)).toBe("Unknown");
  });

  it("空值: 空串返回 Unknown", () => {
    expect(formatTicketStatusLabel("")).toBe("Unknown");
  });

  it("边界: 未知字符串返回原样（小写）", () => {
    expect(formatTicketStatusLabel("UNKNOWN")).toBe("unknown");
  });
});

describe("status - formatReviewDecisionLabel", () => {
  it("happy path: 已知 decision 返回对应 label", () => {
    expect(formatReviewDecisionLabel("approve")).toBe("Approve");
    expect(formatReviewDecisionLabel("approved")).toBe("Approved");
    expect(formatReviewDecisionLabel("request_changes")).toBe("Request Changes");
  });

  it("空值: null 返回 Unknown", () => {
    expect(formatReviewDecisionLabel(null)).toBe("Unknown");
  });

  it("空值: undefined 返回 Unknown", () => {
    expect(formatReviewDecisionLabel(undefined)).toBe("Unknown");
  });

  it("空值: 空串返回 Unknown", () => {
    expect(formatReviewDecisionLabel("")).toBe("Unknown");
  });

  it("边界: 未知字符串返回原样（小写）", () => {
    expect(formatReviewDecisionLabel("UNKNOWN")).toBe("unknown");
  });
});

describe("status - formatNextActionLabel", () => {
  it("happy path: 已知 action 返回对应 label", () => {
    expect(formatNextActionLabel("review")).toBe("Needs Review");
    expect(formatNextActionLabel("approve")).toBe("Awaiting Approval");
    expect(formatNextActionLabel("publish")).toBe("Ready to Publish");
  });

  it("空值: null 返回 Unknown", () => {
    expect(formatNextActionLabel(null)).toBe("Unknown");
  });

  it("空值: undefined 返回 Unknown", () => {
    expect(formatNextActionLabel(undefined)).toBe("Unknown");
  });

  it("空值: 空串返回 Unknown", () => {
    expect(formatNextActionLabel("")).toBe("Unknown");
  });

  it("边界: 未知字符串返回原样（小写）", () => {
    expect(formatNextActionLabel("UNKNOWN")).toBe("unknown");
  });
});

describe("status - formatFailureStageLabel", () => {
  it("happy path: 已知 stage 返回对应 label", () => {
    expect(formatFailureStageLabel("intake")).toBe("Intake");
    expect(formatFailureStageLabel("parsing")).toBe("Parsing");
    expect(formatFailureStageLabel("publishing")).toBe("Publishing");
  });

  it("空值: null 返回 Unknown", () => {
    expect(formatFailureStageLabel(null)).toBe("Unknown");
  });

  it("空值: undefined 返回 Unknown", () => {
    expect(formatFailureStageLabel(undefined)).toBe("Unknown");
  });

  it("空值: 空串返回 Unknown", () => {
    expect(formatFailureStageLabel("")).toBe("Unknown");
  });

  it("边界: 未知字符串返回原样（小写）", () => {
    expect(formatFailureStageLabel("NOT_A_STAGE")).toBe("not_a_stage");
  });
});
