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
    <Alert variant="destructive" className="my-4">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>后端能力缺口 — {feature}</AlertTitle>
      <AlertDescription className="space-y-1">
        <p>该功能依赖的后端 API 尚未实现。</p>
        <code className="text-xs bg-destructive/10 px-1.5 py-0.5 rounded">
          {endpoint}
        </code>
      </AlertDescription>
    </Alert>
  );
}
