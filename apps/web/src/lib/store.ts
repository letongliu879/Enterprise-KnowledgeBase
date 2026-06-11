import { create } from "zustand";
import { persist, subscribeWithSelector } from "zustand/middleware";

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
}

const BROADCAST_CHANNEL_NAME = "ekb-workbench-sync";

function getBroadcastChannel() {
  if (typeof window !== "undefined" && "BroadcastChannel" in window) {
    return new BroadcastChannel(BROADCAST_CHANNEL_NAME);
  }
  return null;
}

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
}
