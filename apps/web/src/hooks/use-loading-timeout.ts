"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface UseLoadingTimeoutOptions {
  isLoading: boolean;
  timeoutMs?: number;
}

interface UseLoadingTimeoutReturn {
  timedOut: boolean;
  reset: () => void;
}

/**
 * useLoadingTimeout — monitors an async loading state and flags if it exceeds a threshold.
 *
 * When `isLoading` remains true for longer than `timeoutMs`, `timedOut` becomes true.
 * The timeout resets whenever `isLoading` transitions back to false, or when `reset()` is called.
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useQuery(...);
 * const { timedOut, reset } = useLoadingTimeout({ isLoading, timeoutMs: 10000 });
 *
 * if (timedOut) return <ErrorState onRetry={reset} />;
 * return <LoadingSkeleton />;
 * ```
 */
export function useLoadingTimeout({
  isLoading,
  timeoutMs = 10000,
}: UseLoadingTimeoutOptions): UseLoadingTimeoutReturn {
  const [timedOut, setTimedOut] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    setTimedOut(false);
    clearTimer();
  }, [clearTimer]);

  useEffect(() => {
    if (!isLoading) {
      // Not loading — clear timeout and reset state
      clearTimer();
      return;
    }

    // Start the timeout if not already running
    if (timerRef.current === null) {
      timerRef.current = setTimeout(() => {
        setTimedOut(true);
      }, timeoutMs);
    }

    return clearTimer;
  }, [isLoading, timeoutMs, clearTimer]);

  return { timedOut, reset };
}
