"use client";

import { motion, AnimatePresence } from "framer-motion";
import { WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useNetworkStatus } from "@/hooks/use-network-status";

export function OfflineToast() {
  const isOnline = useNetworkStatus();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Avoid SSR/client mismatch: only render after mount.
  if (!mounted) return null;

  return (
    <AnimatePresence>
      {!isOnline && (
        <motion.div
          initial={{ opacity: 0, y: -40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -40 }}
          transition={{ duration: 0.25 }}
          className="fixed top-0 left-0 right-0 z-[100] flex items-center justify-center"
        >
          <div className="mt-4 flex items-center gap-2 rounded-xl bg-amber-500/90 px-4 py-2 text-sm font-medium text-white shadow-lg backdrop-blur-sm">
            <WifiOff className="h-4 w-4" />
            <span>网络异常，正在重试...</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
