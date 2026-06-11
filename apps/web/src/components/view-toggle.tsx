"use client";

import { List, LayoutGrid, Grid3x3 } from "lucide-react";
import { cn } from "@/lib/utils";

type ViewMode = "list" | "card" | "grid";

interface ViewToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
  className?: string;
}

const views: { mode: ViewMode; icon: typeof List; label: string }[] = [
  { mode: "list", icon: List, label: "列表" },
  { mode: "card", icon: LayoutGrid, label: "卡片" },
  { mode: "grid", icon: Grid3x3, label: "网格" },
];

export function ViewToggle({ value, onChange, className }: ViewToggleProps) {
  return (
    <div className={cn("flex items-center rounded-xl bg-muted p-1", className)}>
      {views.map(({ mode, icon: Icon, label }) => (
        <button
          key={mode}
          type="button"
          onClick={() => onChange(mode)}
          title={label}
          className={cn(
            "flex items-center justify-center rounded-lg p-1.5 transition-all duration-200",
            value === mode
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </div>
  );
}
