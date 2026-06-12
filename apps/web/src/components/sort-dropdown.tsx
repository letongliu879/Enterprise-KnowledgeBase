"use client";

import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
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
      <PopoverTrigger
        render={(
          { className: triggerClassName, ...props },
          state
        ) => (
          <button
            type="button"
            {...props}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-[min(var(--radius-md),12px)] border border-white/10 bg-white/[0.03] px-2.5 text-xs font-medium whitespace-nowrap transition-all hover:bg-white/[0.08] hover:text-foreground hover:border-primary/30",
              state.open && "bg-white/[0.08] text-foreground",
              className,
              triggerClassName
            )}
          >
            <ArrowUpDown className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{currentLabel}</span>
          </button>
        )}
      />
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
