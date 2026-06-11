import { create } from "zustand";
import { persist, subscribeWithSelector } from "zustand/middleware";

interface NotificationPrefs {
  site: Record<string, boolean>;
  email: { enabled: boolean; events: Record<string, boolean> };
  dnd: { enabled: boolean; start: string; end: string };
}

interface AppState {
  currentCollectionId: string | null;
  setCurrentCollectionId: (id: string | null) => void;

  accessScope: {
    scope_type: "internal" | "external";
    department?: string;
    role?: string;
    user?: string;
    group?: string;
    agent_type_id?: string;
    api_key?: string;
    customer?: string;
    app?: string;
  } | null;
  setAccessScope: (
    scope: {
      scope_type: "internal" | "external";
      department?: string;
      role?: string;
      user?: string;
      group?: string;
      agent_type_id?: string;
      api_key?: string;
      customer?: string;
      app?: string;
    } | null
  ) => void;

  demoToken: string | null;
  setDemoToken: (token: string | null) => void;

  demoApiKey: string | null;
  setDemoApiKey: (key: string | null) => void;

  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;

  uiDensity: "compact" | "comfortable";
  setUiDensity: (density: "compact" | "comfortable") => void;

  theme: "dark" | "light" | "system";
  setTheme: (theme: "dark" | "light" | "system") => void;

  language: "zh" | "en";
  setLanguage: (lang: "zh" | "en") => void;

  notificationPrefs: NotificationPrefs;
  setNotificationPrefs: (prefs: NotificationPrefs) => void;
  setSiteNotification: (key: string, value: boolean) => void;
  setEmailEnabled: (enabled: boolean) => void;
  setEmailNotification: (key: string, value: boolean) => void;
  setDnd: (dnd: { enabled: boolean; start: string; end: string }) => void;
}

const BROADCAST_CHANNEL_NAME = "ekb-workbench-sync";

function getBroadcastChannel() {
  if (typeof window !== "undefined" && "BroadcastChannel" in window) {
    return new BroadcastChannel(BROADCAST_CHANNEL_NAME);
  }
  return null;
}

const defaultNotificationPrefs: NotificationPrefs = {
  site: { upload: true, review: true, decision: true, system: true },
  email: {
    enabled: false,
    events: { upload: false, review: true, decision: true, system: false },
  },
  dnd: { enabled: false, start: "22:00", end: "08:00" },
};

export const useAppStore = create<AppState>()(
  subscribeWithSelector(
    persist(
      (set) => ({
        currentCollectionId: null,
        setCurrentCollectionId: (id) => {
          set({ currentCollectionId: id });
          const bc = getBroadcastChannel();
          if (bc) bc.postMessage({ type: "collection", id });
        },

        accessScope: null,
        setAccessScope: (scope) => {
          set({ accessScope: scope });
          const bc = getBroadcastChannel();
          if (bc) bc.postMessage({ type: "scope", scope });
        },

        demoToken: null,
        setDemoToken: (token) => {
          set({ demoToken: token });
          const bc = getBroadcastChannel();
          if (bc) bc.postMessage({ type: "token", token });
        },

        demoApiKey: null,
        setDemoApiKey: (key) => {
          set({ demoApiKey: key });
          const bc = getBroadcastChannel();
          if (bc) bc.postMessage({ type: "apiKey", key });
        },

        sidebarOpen: true,
        setSidebarOpen: (open) => set({ sidebarOpen: open }),

        uiDensity: "comfortable",
        setUiDensity: (density) => set({ uiDensity: density }),

        theme: "dark",
        setTheme: (theme) => set({ theme }),

        language: "zh",
        setLanguage: (language) => set({ language }),

        notificationPrefs: defaultNotificationPrefs,
        setNotificationPrefs: (prefs) =>
          set({ notificationPrefs: prefs }),
        setSiteNotification: (key, value) =>
          set((state) => ({
            notificationPrefs: {
              ...state.notificationPrefs,
              site: { ...state.notificationPrefs.site, [key]: value },
            },
          })),
        setEmailEnabled: (enabled) =>
          set((state) => ({
            notificationPrefs: {
              ...state.notificationPrefs,
              email: { ...state.notificationPrefs.email, enabled },
            },
          })),
        setEmailNotification: (key, value) =>
          set((state) => ({
            notificationPrefs: {
              ...state.notificationPrefs,
              email: {
                ...state.notificationPrefs.email,
                events: { ...state.notificationPrefs.email.events, [key]: value },
              },
            },
          })),
        setDnd: (dnd) =>
          set((state) => ({
            notificationPrefs: { ...state.notificationPrefs, dnd },
          })),
      }),
      {
        name: "ekb-workbench-store",
        partialize: (state) => ({
          currentCollectionId: state.currentCollectionId,
          accessScope: state.accessScope,
          demoToken: state.demoToken,
          demoApiKey: state.demoApiKey,
          sidebarOpen: state.sidebarOpen,
          uiDensity: state.uiDensity,
          theme: state.theme,
          language: state.language,
          notificationPrefs: state.notificationPrefs,
        }),
      }
    )
  )
);

// Subscribe to cross-tab sync events
if (typeof window !== "undefined") {
  const bc = getBroadcastChannel();
  if (bc) {
    bc.onmessage = (event) => {
      const { type, id, scope, token, key } = event.data || {};
      if (type === "collection" && id !== useAppStore.getState().currentCollectionId) {
        useAppStore.setState({ currentCollectionId: id });
      }
      if (type === "scope") {
        useAppStore.setState({ accessScope: scope });
      }
      if (type === "token") {
        useAppStore.setState({ demoToken: token });
      }
      if (type === "apiKey") {
        useAppStore.setState({ demoApiKey: key });
      }
    };
  }

  // Sync theme from store on load
  const stored = localStorage.getItem("ekb-workbench-store");
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      const t = parsed.state?.theme as "dark" | "light" | "system" | undefined;
      if (t) {
        const root = document.documentElement;
        if (t === "dark") root.classList.add("dark");
        else if (t === "light") root.classList.remove("dark");
        else {
          const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
          if (prefersDark) root.classList.add("dark");
          else root.classList.remove("dark");
        }
      }
    } catch {
      // ignore
    }
  }
}
