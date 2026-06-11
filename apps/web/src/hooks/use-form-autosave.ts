"use client";

import { useEffect, useRef, useCallback } from "react";
import { useLocalStorage } from "./use-local-storage";

interface UseFormAutosaveOptions<T> {
  key: string;
  value: T;
  debounceMs?: number;
  onRestore?: (value: T) => void;
}

export function useFormAutosave<T>({ key, value, debounceMs = 1000, onRestore }: UseFormAutosaveOptions<T>) {
  const [savedValue, setSavedValue, clearSaved] = useLocalStorage<T | null>(key, null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasRestored = useRef(false);

  // Auto-save with debounce
  useEffect(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setSavedValue(value);
    }, debounceMs);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [value, debounceMs, setSavedValue]);

  // Restore once on mount
  useEffect(() => {
    if (!hasRestored.current && savedValue !== null && onRestore) {
      hasRestored.current = true;
      onRestore(savedValue);
    }
  }, [savedValue, onRestore]);

  const clear = useCallback(() => {
    clearSaved();
    hasRestored.current = false;
  }, [clearSaved]);

  return { savedValue, clear };
}
