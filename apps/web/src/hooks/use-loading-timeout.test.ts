import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLoadingTimeout } from "./use-loading-timeout";

describe("useLoadingTimeout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("GLB-003: isLoading=false 时 timedOut 为 false", () => {
    const { result } = renderHook(() =>
      useLoadingTimeout({ isLoading: false })
    );
    expect(result.current.timedOut).toBe(false);
  });

  it("GLB-003: isLoading=true 且在 timeoutMs 内完成时不触发 timedOut", () => {
    const { result, rerender } = renderHook(
      ({ isLoading }) => useLoadingTimeout({ isLoading }),
      { initialProps: { isLoading: true } }
    );

    act(() => { vi.advanceTimersByTime(5000); });
    expect(result.current.timedOut).toBe(false);

    rerender({ isLoading: false });
    act(() => { vi.advanceTimersByTime(6000); });
    expect(result.current.timedOut).toBe(false);
  });

  it("GLB-003: isLoading=true 超过 timeoutMs 后 timedOut 为 true", () => {
    const { result } = renderHook(() =>
      useLoadingTimeout({ isLoading: true, timeoutMs: 10000 })
    );

    act(() => { vi.advanceTimersByTime(9999); });
    expect(result.current.timedOut).toBe(false);

    act(() => { vi.advanceTimersByTime(1); });
    expect(result.current.timedOut).toBe(true);
  });

  it("GLB-003: reset() 清除 timedOut 状态", () => {
    const { result } = renderHook(() =>
      useLoadingTimeout({ isLoading: true, timeoutMs: 100 })
    );

    act(() => { vi.advanceTimersByTime(100); });
    expect(result.current.timedOut).toBe(true);

    act(() => { result.current.reset(); });
    expect(result.current.timedOut).toBe(false);
  });

  it("GLB-003: 自定义 timeoutMs 生效", () => {
    const { result } = renderHook(() =>
      useLoadingTimeout({ isLoading: true, timeoutMs: 3000 })
    );

    act(() => { vi.advanceTimersByTime(2999); });
    expect(result.current.timedOut).toBe(false);

    act(() => { vi.advanceTimersByTime(1); });
    expect(result.current.timedOut).toBe(true);
  });
});
