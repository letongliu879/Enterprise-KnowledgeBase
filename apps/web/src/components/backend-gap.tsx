"use client";

import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function BackendGap({
  feature,
  endpoint,
}: {
  feature: string;
  endpoint: string;
}) {
  return (
    <Alert
      variant="destructive"
      className="my-4 border-amber-500/20 bg-amber-500/5"
    >
      <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
      <AlertTitle className="text-amber-300">
        后端能力缺口 — {feature}
      </AlertTitle>
      <AlertDescription className="space-y-1.5 mt-1">
        <p className="text-amber-200/70">该功能依赖的后端 API 尚未实现。</p>
        <code className="text-[11px] glass px-2 py-1 rounded-md text-amber-300/80 font-mono block w-fit">
          {endpoint}
        </code>
      </AlertDescription>
    </Alert>
  );
}
