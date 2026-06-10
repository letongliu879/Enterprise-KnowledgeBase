import { describe, it, expect } from "vitest";
import { cn } from "./utils";

describe("utils - cn 合并冲突 class", () => {
  it("happy path: 后出现的 class 覆盖先出现的", () => {
    expect(cn("px-4", "px-2")).toBe("px-2");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("边界: 多个冲突 class，最后一个生效", () => {
    expect(cn("px-4", "px-6", "px-8")).toBe("px-8");
  });
});

describe("utils - cn 条件 class", () => {
  it("happy path: true 条件包含 class，false 排除", () => {
    expect(cn("base", true && "active", false && "hidden")).toBe("base active");
  });

  it("空值: 0、空串在条件中不输出额外 class", () => {
    expect(cn("base", 0, "")).toBe("base");
  });

  it("边界: 混合条件与正常 class", () => {
    const isActive = true;
    const isDisabled = false;
    expect(cn("btn", isActive && "btn-active", isDisabled && "btn-disabled")).toBe("btn btn-active");
  });
});

describe("utils - cn 无参数", () => {
  it("happy path: 无参数返回空字符串", () => {
    expect(cn()).toBe("");
  });
});

describe("utils - cn 重复 class", () => {
  it("happy path: 重复 class 去重", () => {
    expect(cn("px-4", "px-4")).toBe("px-4");
  });

  it("边界: 大量重复不影响结果", () => {
    expect(cn("m-2", "m-2", "m-2", "m-2")).toBe("m-2");
  });
});

describe("utils - cn 合并不冲突 class", () => {
  it("happy path: 不冲突的 class 全部保留", () => {
    expect(cn("px-4", "py-2", "text-sm")).toBe("px-4 py-2 text-sm");
  });

  it("边界: 自定义 className 追加到末尾", () => {
    expect(cn("rounded-md border", "custom-class")).toBe("rounded-md border custom-class");
  });
});
