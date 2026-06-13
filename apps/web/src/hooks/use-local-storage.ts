"use client";

import { useState, useCallback } from "react";

function getLocalStorage(): Storage | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const storage = window.localStorage;
    const testKey = "__ekb_ls_test__";
    storage.setItem(testKey, "1");
    storage.removeItem(testKey);
    return storage;
  } catch {
    return undefined;
  }
}

export function useLocalStorage<T>(key: string, initialValue: T) {
  const [storedValue, setStoredValue] = useState<T>(() => {
    const storage = getLocalStorage();
    if (!storage) return initialValue;
    try {
      const item = storage.getItem(key);
      return item ? (JSON.parse(item) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setValue = useCallback(
    (value: T | ((val: T) => T)) => {
      const storage = getLocalStorage();
      try {
        setStoredValue((prev) => {
          const valueToStore = value instanceof Function ? value(prev) : value;
          if (storage) {
            storage.setItem(key, JSON.stringify(valueToStore));
          }
          return valueToStore;
        });
      } catch {
        // ignore
      }
    },
    [key]
  );

  const removeValue = useCallback(() => {
    const storage = getLocalStorage();
    try {
      setStoredValue(initialValue);
      if (storage) {
        storage.removeItem(key);
      }
    } catch {
      // ignore
    }
  }, [key, initialValue]);

  return [storedValue, setValue, removeValue] as const;
}
