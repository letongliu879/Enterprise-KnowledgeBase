"use client";

import * as React from "react";
import { Check, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  indeterminate?: boolean;
  onCheckedChange?: (checked: boolean) => void;
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, indeterminate, onCheckedChange, onChange, ...props }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      onCheckedChange?.(e.target.checked);
      onChange?.(e);
    };
    return (
      <span className={cn("relative inline-flex items-center", className)}>
        <input
          type="checkbox"
          ref={ref}
          className="peer sr-only"
          onChange={handleChange}
          {...props}
        />
        <span
          className={cn(
            "flex h-4 w-4 shrink-0 items-center justify-center rounded-md border border-white/20 bg-white/5 transition-colors",
            "peer-checked:border-primary peer-checked:bg-primary",
            "peer-focus-visible:ring-2 peer-focus-visible:ring-primary/30",
            "peer-disabled:opacity-50"
          )}
        >
          <Check className="h-3 w-3 text-primary-foreground opacity-0 peer-checked:opacity-100" />
          {indeterminate && (
            <Minus className="h-3 w-3 text-primary-foreground absolute opacity-0 peer-indeterminate:opacity-100" />
          )}
        </span>
      </span>
    );
  }
);
Checkbox.displayName = "Checkbox";
