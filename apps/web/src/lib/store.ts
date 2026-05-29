import { create } from "zustand";
import { persist } from "zustand/middleware";

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
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentCollectionId: null,
      setCurrentCollectionId: (id) => set({ currentCollectionId: id }),

      accessScope: null,
      setAccessScope: (scope) => set({ accessScope: scope }),

      demoToken: null,
      setDemoToken: (token) => set({ demoToken: token }),

      demoApiKey: null,
      setDemoApiKey: (key) => set({ demoApiKey: key }),
    }),
    {
      name: "ekb-workbench-store",
      partialize: (state) => ({
        currentCollectionId: state.currentCollectionId,
        accessScope: state.accessScope,
        demoToken: state.demoToken,
        demoApiKey: state.demoApiKey,
      }),
    }
  )
);
