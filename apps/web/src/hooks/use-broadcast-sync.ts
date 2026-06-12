"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";

const BROADCAST_CHANNEL_NAME = "ekb-workbench-sync";

/**
 * Broadcast channel event payloads.
 * The `type` field routes messages to the correct handler on the receiving tab.
 */
export type BroadcastSyncEvent =
  | { type: "collection"; id: string | null }
  | { type: "scope"; scope: unknown }
  | { type: "token"; token: string | null }
  | { type: "apiKey"; key: string | null }
  | { type: "theme"; theme: "dark" | "light" | "system" }
  | { type: "language"; lang: "zh" | "en" }
  | { type: "sidebarOpen"; open: boolean }
  | { type: "uiDensity"; density: "compact" | "comfortable" };

function getBroadcastChannel(): BroadcastChannel | null {
  if (typeof window !== "undefined" && "BroadcastChannel" in window) {
    return new BroadcastChannel(BROADCAST_CHANNEL_NAME);
  }
  return null;
}

/**
 * useBroadcastSync — synchronises Zustand store changes across browser tabs
 * via BroadcastChannel.
 *
 * Call this once at the AppShell level. It subscribes to selected store
 * fields and broadcasts changes, and listens for incoming broadcasts to
 * update the local store.
 *
 * The four "auth‑adjacent" fields (currentCollectionId, accessScope,
 * demoToken, demoApiKey) are already synced inline in the store setters.
 * This hook adds sync for preferences fields that were previously
 * tab‑local only: theme, language, sidebarOpen, uiDensity.
 */
export function useBroadcastSync() {
  const bcRef = useRef<BroadcastChannel | null>(null);

  // ── Subscribe to store changes and broadcast ───────────────────────
  useEffect(() => {
    const unsubTheme = useAppStore.subscribe(
      (state) => state.theme,
      (theme) => {
        const bc = getBroadcastChannel();
        if (bc) bc.postMessage({ type: "theme", theme } satisfies BroadcastSyncEvent);
      }
    );
    const unsubLang = useAppStore.subscribe(
      (state) => state.language,
      (language) => {
        const bc = getBroadcastChannel();
        if (bc) bc.postMessage({ type: "language", lang: language } satisfies BroadcastSyncEvent);
      }
    );
    const unsubSidebar = useAppStore.subscribe(
      (state) => state.sidebarOpen,
      (open) => {
        const bc = getBroadcastChannel();
        if (bc) bc.postMessage({ type: "sidebarOpen", open } satisfies BroadcastSyncEvent);
      }
    );
    const unsubDensity = useAppStore.subscribe(
      (state) => state.uiDensity,
      (density) => {
        const bc = getBroadcastChannel();
        if (bc) bc.postMessage({ type: "uiDensity", density } satisfies BroadcastSyncEvent);
      }
    );

    return () => {
      unsubTheme();
      unsubLang();
      unsubSidebar();
      unsubDensity();
    };
  }, []);

  // ── Listen for incoming broadcasts ─────────────────────────────────
  useEffect(() => {
    const bc = getBroadcastChannel();
    bcRef.current = bc;
    if (!bc) return;

    const handler = (event: MessageEvent<BroadcastSyncEvent>) => {
      const { type } = event.data ?? {};
      if (!type) return;

      // Skip events we sent ourselves (BroadcastChannel delivers to all
      // tabs including the sender). The store already has the latest
      // value for auth‑adjacent setters, so only update if different.
      const current = useAppStore.getState();

      switch (type as BroadcastSyncEvent["type"]) {
        case "collection": {
          const { id } = event.data as BroadcastSyncEvent & { type: "collection" };
          if (id !== current.currentCollectionId) {
            useAppStore.setState({ currentCollectionId: id });
          }
          break;
        }
        case "scope": {
          const { scope } = event.data as BroadcastSyncEvent & { type: "scope" };
          useAppStore.setState({ accessScope: scope as typeof current.accessScope });
          break;
        }
        case "token": {
          const { token } = event.data as BroadcastSyncEvent & { type: "token" };
          if (token !== current.demoToken) {
            useAppStore.setState({ demoToken: token });
          }
          break;
        }
        case "apiKey": {
          const { key } = event.data as BroadcastSyncEvent & { type: "apiKey" };
          if (key !== current.demoApiKey) {
            useAppStore.setState({ demoApiKey: key });
          }
          break;
        }
        case "theme": {
          const { theme } = event.data as BroadcastSyncEvent & { type: "theme" };
          if (theme !== current.theme) {
            useAppStore.setState({ theme });
            // Apply theme to <html> immediately
            applyThemeClass(theme);
          }
          break;
        }
        case "language": {
          const { lang } = event.data as BroadcastSyncEvent & { type: "language" };
          if (lang !== current.language) {
            useAppStore.setState({ language: lang });
          }
          break;
        }
        case "sidebarOpen": {
          const { open } = event.data as BroadcastSyncEvent & { type: "sidebarOpen" };
          if (open !== current.sidebarOpen) {
            useAppStore.setState({ sidebarOpen: open });
          }
          break;
        }
        case "uiDensity": {
          const { density } = event.data as BroadcastSyncEvent & { type: "uiDensity" };
          if (density !== current.uiDensity) {
            useAppStore.setState({ uiDensity: density });
          }
          break;
        }
      }
    };

    bc.addEventListener("message", handler);
    return () => {
      bc.removeEventListener("message", handler);
      bc.close();
    };
  }, []);
}

// ── Helpers ──────────────────────────────────────────────────────────

function applyThemeClass(theme: "dark" | "light" | "system") {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else if (theme === "light") {
    root.classList.remove("dark");
  } else {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (prefersDark) root.classList.add("dark");
    else root.classList.remove("dark");
  }
}
