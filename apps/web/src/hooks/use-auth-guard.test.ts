import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";

vi.hoisted(() => {
  const store: Record<string, string> = {};
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => { store[key] = value; },
      removeItem: (key: string) => { delete store[key]; },
    },
    writable: true,
    configurable: true,
  });
});

import { useAuthGuard } from "./use-auth-guard";
import { useAppStore } from "@/lib/store";

describe("useAuthGuard", () => {
  beforeEach(() => {
    useAppStore.setState({ demoToken: null, demoApiKey: null });
  });

  it("SHE-033: 无 JWT 无 API Key 时 isAuthenticated 为 false", () => {
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.tokenMissing).toBe(true);
  });

  it("SHE-033: 3 段 JWT 时 isAuthenticated 为 true", () => {
    useAppStore.setState({ demoToken: "header.payload.sig" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.hasJwtToken).toBe(true);
  });

  it("SHE-033: 非 3 段字符串不被视为有效 JWT", () => {
    useAppStore.setState({ demoToken: "invalid-token" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.hasJwtToken).toBe(false);
  });

  it("SHE-033: API Key 存在时 isAuthenticated 为 true", () => {
    useAppStore.setState({ demoApiKey: "ak_test_123" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.hasApiKey).toBe(true);
  });

  it("SHE-033: JWT 和 API Key 同时存在时 isAuthenticated 为 true", () => {
    useAppStore.setState({ demoToken: "h.p.s", demoApiKey: "key-123" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.hasJwtToken).toBe(true);
    expect(result.current.hasApiKey).toBe(true);
  });

  it("SHE-033: 无凭证时 message 为引导文案", () => {
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.message).toBe("请先配置 JWT 令牌或 API 密钥");
  });

  it("SHE-033: 有 API Key 无 JWT 时提示缺少 JWT", () => {
    useAppStore.setState({ demoApiKey: "ak_xxx" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.message).toBe("缺少 JWT 令牌，部分功能可能受限");
  });

  it("SHE-033: 完全认证时 message 为 null", () => {
    useAppStore.setState({ demoToken: "h.p.s", demoApiKey: "ak_xxx" });
    const { result } = renderHook(() => useAuthGuard());
    expect(result.current.message).toBeNull();
  });
});
