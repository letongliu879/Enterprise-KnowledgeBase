"use client";

import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  PopoverProvider,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface SortOption {
  value: string;
  label: string;
}

interface SortDropdownProps {
  options: SortOption[];
  value: string;
  direction: "asc" | "desc";
  onChange: (value: string, direction: "asc" | "desc") => void;
  className?: string;
}

export function SortDropdown({ options, value, direction, onChange, className }: SortDropdownProps) {
  const currentLabel = options.find((o) => o.value === value)?.label || "排序";

  return (
    <PopoverProvider>
      <PopoverTrigger>
        <Button variant="outline" size="sm" className={cn("h-8 gap-1.5 text-xs", className)}>
          <ArrowUpDown className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{currentLabel}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-48 p-1.5">
        <div className="space-y-0.5">
          {options.map((option) => {
            const isActive = option.value === value;
            return (
              <button
                key={option.value}
                onClick={() => {
                  if (isActive) {
                    onChange(option.value, direction === "asc" ? "desc" : "asc");
                  } else {
                    onChange(option.value, "desc");
                  }
                }}
                className={cn(
                  "flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
              >
                <span>{option.label}</span>
                {isActive && (
                  direction === "asc" ? (
                    <ArrowUp className="h-3.5 w-3.5" />
                  ) : (
                    <ArrowDown className="h-3.5 w-3.5" />
                  )
                )}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </PopoverProvider>
  );
}
