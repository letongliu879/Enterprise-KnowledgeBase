"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { FileQuestion, Home, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center text-center px-4"
      >
        <div className="glass rounded-3xl p-8 mb-8">
          <FileQuestion className="h-16 w-16 text-primary/40" />
        </div>
        <h1 className="text-7xl font-bold text-foreground/20 mb-2">404</h1>
        <h2 className="text-2xl font-semibold text-foreground mb-3">页面不存在</h2>
        <p className="text-muted-foreground max-w-sm mb-8">
          您访问的页面可能已被移除、重命名，或者从未存在过。
        </p>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => history.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回上一页
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
