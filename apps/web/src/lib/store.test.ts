import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "./store";

describe("store - set/get currentCollectionId", () => {
  beforeEach(() => {
    localStorage.removeItem("ekb-workbench-store");
    useAppStore.setState({
      currentCollectionId: null,
      accessScope: null,
      demoToken: null,
      demoApiKey: null,
    });
  });

  it("happy path: 正常设置和获取 currentCollectionId", () => {
    useAppStore.getState().setCurrentCollectionId("coll-123");
    expect(useAppStore.getState().currentCollectionId).toBe("coll-123");
  });

  it("空值: 设置 null 清空 currentCollectionId", () => {
    useAppStore.getState().setCurrentCollectionId("coll-123");
    useAppStore.getState().setCurrentCollectionId(null);
    expect(useAppStore.getState().currentCollectionId).toBeNull();
  });

  it("边界: 超长字符串作为 collectionId 能正确存储", () => {
    const longId = "a".repeat(1000);
    useAppStore.getState().setCurrentCollectionId(longId);
    expect(useAppStore.getState().currentCollectionId).toBe(longId);
  });
});

describe("store - set/get accessScope", () => {
  beforeEach(() => {
    localStorage.removeItem("ekb-workbench-store");
    useAppStore.setState({
      currentCollectionId: null,
      accessScope: null,
      demoToken: null,
      demoApiKey: null,
    });
  });

  it("happy path: 正常设置和获取 accessScope", () => {
    const scope = { scope_type: "internal" as const, department: "eng" };
    useAppStore.getState().setAccessScope(scope);
    expect(useAppStore.getState().accessScope).toEqual(scope);
  });

  it("空值: 设置 null 清空 accessScope", () => {
    useAppStore.getState().setAccessScope({ scope_type: "internal" });
    useAppStore.getState().setAccessScope(null);
    expect(useAppStore.getState().accessScope).toBeNull();
  });

  it("边界: 含特殊字符的字段值能正确存储", () => {
    const scope = {
      scope_type: "external" as const,
      department: "测试部 🚀",
      user: "user@example.com",
    };
    useAppStore.getState().setAccessScope(scope);
    expect(useAppStore.getState().accessScope).toEqual(scope);
  });
});

describe("store - set/get demoToken", () => {
  beforeEach(() => {
    localStorage.removeItem("ekb-workbench-store");
    useAppStore.setState({
      currentCollectionId: null,
      accessScope: null,
      demoToken: null,
      demoApiKey: null,
    });
  });

  it("happy path: 正常设置和获取 demoToken", () => {
    useAppStore.getState().setDemoToken("token-abc");
    expect(useAppStore.getState().demoToken).toBe("token-abc");
  });

  it("空值: 设置 null 清空 demoToken", () => {
    useAppStore.getState().setDemoToken("token-abc");
    useAppStore.getState().setDemoToken(null);
    expect(useAppStore.getState().demoToken).toBeNull();
  });
});

describe("store - set/get demoApiKey", () => {
  beforeEach(() => {
    localStorage.removeItem("ekb-workbench-store");
    useAppStore.setState({
      currentCollectionId: null,
      accessScope: null,
      demoToken: null,
      demoApiKey: null,
    });
  });

  it("happy path: 正常设置和获取 demoApiKey", () => {
    useAppStore.getState().setDemoApiKey("key-xyz");
    expect(useAppStore.getState().demoApiKey).toBe("key-xyz");
  });

  it("空值: 设置 null 清空 demoApiKey", () => {
    useAppStore.getState().setDemoApiKey("key-xyz");
    useAppStore.getState().setDemoApiKey(null);
    expect(useAppStore.getState().demoApiKey).toBeNull();
  });
});

describe("store - persist partialize", () => {
  beforeEach(() => {
    localStorage.removeItem("ekb-workbench-store");
    useAppStore.setState({
      currentCollectionId: null,
      accessScope: null,
      demoToken: null,
      demoApiKey: null,
    });
  });

  it("happy path: persist 保存数据字段到 localStorage", () => {
    useAppStore.getState().setCurrentCollectionId("persisted-coll");
    useAppStore.getState().setDemoToken("persisted-token");

    const raw = localStorage.getItem("ekb-workbench-store");
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.state.currentCollectionId).toBe("persisted-coll");
    expect(parsed.state.demoToken).toBe("persisted-token");
  });

  it("边界: persist 不包含 setter 函数", () => {
    useAppStore.getState().setCurrentCollectionId("coll-1");

    const raw = localStorage.getItem("ekb-workbench-store");
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.state).not.toHaveProperty("setCurrentCollectionId");
    expect(parsed.state).not.toHaveProperty("setAccessScope");
    expect(parsed.state).not.toHaveProperty("setDemoToken");
    expect(parsed.state).not.toHaveProperty("setDemoApiKey");
  });
});

describe("store - 多次 set 覆盖", () => {
  beforeEach(() => {
    localStorage.removeItem("ekb-workbench-store");
    useAppStore.setState({
      currentCollectionId: null,
      accessScope: null,
      demoToken: null,
      demoApiKey: null,
    });
  });

  it("happy path: 多次 set 同一字段，后值覆盖前值", () => {
    useAppStore.getState().setCurrentCollectionId("first");
    useAppStore.getState().setCurrentCollectionId("second");
    useAppStore.getState().setCurrentCollectionId("third");
    expect(useAppStore.getState().currentCollectionId).toBe("third");
  });

  it("边界: 不同字段的 set 互不干扰", () => {
    useAppStore.getState().setCurrentCollectionId("coll-a");
    useAppStore.getState().setDemoToken("token-b");
    useAppStore.getState().setDemoApiKey("key-c");

    const state = useAppStore.getState();
    expect(state.currentCollectionId).toBe("coll-a");
    expect(state.demoToken).toBe("token-b");
    expect(state.demoApiKey).toBe("key-c");
  });
});
