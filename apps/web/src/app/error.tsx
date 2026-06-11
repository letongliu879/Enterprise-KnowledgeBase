"use client";

import { useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertTriangle, Home, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center text-center px-4"
      >
        <div className="glass rounded-3xl p-8 mb-8 border-red-500/20">
          <AlertTriangle className="h-16 w-16 text-red-400/60" />
        </div>
        <h1 className="text-7xl font-bold text-foreground/20 mb-2">500</h1>
        <h2 className="text-2xl font-semibold text-foreground mb-3">出错了</h2>
        <p className="text-muted-foreground max-w-sm mb-2">
          应用程序遇到了意外错误，请稍后重试。
        </p>
        {error.digest && (
          <p className="text-xs text-muted-foreground/50 font-mono mb-8">
            Error ID: {error.digest}
          </p>
        )}
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={reset}>
            <RotateCcw className="h-4 w-4 mr-2" />
            重试
          </Button>
          <Link href="/">
            <Button className="shadow-glow">
              <Home className="h-4 w-4 mr-2" />
              回到首页
            </Button>
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
