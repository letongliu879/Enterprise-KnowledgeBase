"use client";

import { useEffect, useRef, useCallback } from "react";

interface HotkeyConfig {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
  handler: (e: KeyboardEvent) => void;
  preventDefault?: boolean;
  stopPropagation?: boolean;
}

export function useHotkeys(configs: HotkeyConfig[], deps: React.DependencyList = []) {
  const configsRef = useRef(configs);

  useEffect(() => {
    configsRef.current = configs;
  }, [configs]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    for (const config of configsRef.current) {
      const keyMatches = e.key === config.key;
      const ctrlMatches = config.ctrl ? e.ctrlKey : !e.ctrlKey || config.key === "Control";
      const metaMatches = config.meta ? e.metaKey : !e.metaKey || config.key === "Meta";
      const shiftMatches = config.shift ? e.shiftKey : !e.shiftKey || config.key === "Shift";
      const altMatches = config.alt ? e.altKey : !e.altKey || config.key === "Alt";

      if (keyMatches && ctrlMatches && metaMatches && shiftMatches && altMatches) {
        if (config.preventDefault) e.preventDefault();
        if (config.stopPropagation) e.stopPropagation();
        config.handler(e);
        return;
      }
    }
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown, ...deps]);
}

export function useEscapeKey(handler: () => void, active = true) {
  useEffect(() => {
    if (!active) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handler();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [handler, active]);
}
