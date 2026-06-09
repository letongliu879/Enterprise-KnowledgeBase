import { useSyncExternalStore } from "react";

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (callback) => {
      if (typeof window === "undefined") {
        return () => {};
      }

      const media = window.matchMedia(query);
      const listener = () => callback();
      media.addEventListener("change", listener);
      return () => media.removeEventListener("change", listener);
    },
    () => {
      if (typeof window === "undefined") {
        return false;
      }

      return window.matchMedia(query).matches;
    },
    () => false
  );
}

export function useIsMobile(): boolean {
  return useMediaQuery("(max-width: 767px)");
}

export function useIsTablet(): boolean {
  return useMediaQuery("(min-width: 768px) and (max-width: 1023px)");
}

export function useIsDesktop(): boolean {
  return useMediaQuery("(min-width: 1024px)");
}
