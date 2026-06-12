"use client";

import { useEffect, useState } from "react";
import { Clock, AlertTriangle, Timer } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReviewTimerProps {
  createdAt: string;
  className?: string;
}

function getElapsedMs(createdAt: string): number {
  return Date.now() - new Date(createdAt).getTime();
}

function formatElapsed(ms: number): string {
  const totalMinutes = Math.floor(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (totalMinutes < 1) return "刚刚";
  if (totalMinutes < 60) return `${totalMinutes} 分钟`;
  if (hours < 24) return `${hours} 小时 ${minutes} 分钟`;
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return `${days} 天 ${remainingHours} 小时`;
}

function getSeverity(ms: number): "low" | "medium" | "high" {
  const hours = ms / 3600000;
  if (hours >= 24) return "high";
  if (hours >= 4) return "medium";
  return "low";
}

export function ReviewTimer({ createdAt, className }: ReviewTimerProps) {
  const [elapsed, setElapsed] = useState(() => getElapsedMs(createdAt));

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(getElapsedMs(createdAt));
    }, 60000);
    return () => clearInterval(timer);
  }, [createdAt]);

  const severity = getSeverity(elapsed);

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-xl border px-3 py-2 text-sm",
        severity === "high" && "border-red-500/30 bg-red-500/10 text-red-400",
        severity === "medium" && "border-amber-500/30 bg-amber-500/10 text-amber-400",
        severity === "low" && "border-muted bg-muted/30 text-muted-foreground",
        className
      )}
    >
      {severity === "high" ? (
        <AlertTriangle className="h-4 w-4 shrink-0" />
      ) : (
        <Clock className="h-4 w-4 shrink-0" />
      )}
      <span className="font-medium">
        {severity === "high" ? "已超时 " : "等待 "}
        {formatElapsed(elapsed)}
      </span>
      {severity === "high" && (
        <Timer className="h-3.5 w-3.5 shrink-0 animate-pulse" />
      )}
    </div>
  );
}
