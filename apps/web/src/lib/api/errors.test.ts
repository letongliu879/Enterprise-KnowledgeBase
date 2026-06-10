import { describe, it, expect } from "vitest";
import {
  ApiClientError,
  BackendGapError,
  isBackendGap,
  isApiError,
  getErrorMessage,
} from "./errors";

describe("errors - ApiClientError 构造", () => {
  it("happy path: 正常构造 ApiClientError", () => {
    const err = new ApiClientError("ERR_001", "something went wrong", 500, "origin");
    expect(err.name).toBe("ApiClientError");
    expect(err.code).toBe("ERR_001");
    expect(err.message).toBe("something went wrong");
    expect(err.status).toBe(500);
    expect(err.downstream).toBe("origin");
  });

  it("空值: 省略可选参数也能构造", () => {
    const err = new ApiClientError("ERR_002", "minimal");
    expect(err.status).toBeUndefined();
    expect(err.downstream).toBeUndefined();
  });

  it("边界: message 为空字符串", () => {
    const err = new ApiClientError("ERR_003", "", 400);
    expect(err.message).toBe("");
  });
});

describe("errors - BackendGapError 构造", () => {
  it("happy path: 正常构造 BackendGapError", () => {
    const err = new BackendGapError("feature-a", "/api/a", "not ready");
    expect(err.name).toBe("BackendGapError");
    expect(err.feature).toBe("feature-a");
    expect(err.endpoint).toBe("/api/a");
    expect(err.message).toBe("not ready");
  });

  it("空值: 使用默认 message", () => {
    const err = new BackendGapError("feature-b", "/api/b");
    expect(err.message).toBe("Backend API not yet implemented");
  });

  it("边界: feature 和 endpoint 含特殊字符", () => {
    const err = new BackendGapError("功能 🚀", "/api/测试?x=1", "");
    expect(err.feature).toBe("功能 🚀");
    expect(err.endpoint).toBe("/api/测试?x=1");
  });
});

describe("errors - isBackendGap 类型守卫", () => {
  it("happy path: 传 BackendGapError 返回 true", () => {
    expect(isBackendGap(new BackendGapError("f", "/e"))).toBe(true);
  });

  it("空值: 传普通 Error 返回 false", () => {
    expect(isBackendGap(new Error("oops"))).toBe(false);
  });

  it("边界: 传 null、undefined、字符串、对象返回 false", () => {
    expect(isBackendGap(null)).toBe(false);
    expect(isBackendGap(undefined)).toBe(false);
    expect(isBackendGap("error")).toBe(false);
    expect(isBackendGap({ feature: "f" })).toBe(false);
  });
});

describe("errors - isApiError 类型守卫", () => {
  it("happy path: 传 ApiClientError 返回 true", () => {
    expect(isApiError(new ApiClientError("C", "M"))).toBe(true);
  });

  it("空值: 传普通 Error 返回 false", () => {
    expect(isApiError(new Error("oops"))).toBe(false);
  });

  it("边界: 传 null、undefined、数字返回 false", () => {
    expect(isApiError(null)).toBe(false);
    expect(isApiError(undefined)).toBe(false);
    expect(isApiError(42)).toBe(false);
  });
});

describe("errors - getErrorMessage 接收 Error", () => {
  it("happy path: 普通 Error 返回 message", () => {
    expect(getErrorMessage(new Error("plain error"))).toBe("plain error");
  });

  it("空值: Error message 为空字符串", () => {
    expect(getErrorMessage(new Error(""))).toBe("");
  });

  it("边界: Error message 超长", () => {
    const longMsg = "x".repeat(5000);
    expect(getErrorMessage(new Error(longMsg))).toBe(longMsg);
  });
});

describe("errors - getErrorMessage 接收 ApiClientError", () => {
  it("happy path: 返回 ApiClientError 的 message", () => {
    const err = new ApiClientError("C", "api failed", 500);
    expect(getErrorMessage(err)).toBe("api failed");
  });
});

describe("errors - getErrorMessage 接收 BackendGapError", () => {
  it("happy path: 返回 BackendGapError 的 message", () => {
    const err = new BackendGapError("f", "/e", "gap msg");
    expect(getErrorMessage(err)).toBe("gap msg");
  });
});

describe("errors - getErrorMessage 接收字符串", () => {
  it("happy path: 直接返回字符串", () => {
    expect(getErrorMessage("string error")).toBe("string error");
  });

  it("空值: 空字符串", () => {
    expect(getErrorMessage("")).toBe("");
  });

  it("边界: 含特殊字符", () => {
    expect(getErrorMessage("错误 🚀")).toBe("错误 🚀");
  });
});

describe("errors - getErrorMessage 接收普通对象", () => {
  it("happy path: 对象含 message 字段返回该字段", () => {
    expect(getErrorMessage({ message: "obj msg" })).toBe("obj msg");
  });

  it("happy path: 对象含 error 字段返回该字段", () => {
    expect(getErrorMessage({ error: "err msg" })).toBe("err msg");
  });

  it("happy path: 对象含 detail 字段返回该字段", () => {
    expect(getErrorMessage({ detail: "detailed" })).toBe("detailed");
  });

  it("边界: 无已知字段则 JSON 序列化", () => {
    expect(getErrorMessage({ foo: "bar" })).toBe('{"foo":"bar"}');
  });
});

describe("errors - getErrorMessage 接收 null / undefined", () => {
  it("空值: null 返回 \"null\"", () => {
    expect(getErrorMessage(null)).toBe("null");
  });

  it("空值: undefined 返回 \"undefined\"", () => {
    expect(getErrorMessage(undefined)).toBe("undefined");
  });
});
