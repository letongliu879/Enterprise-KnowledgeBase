"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface RadioGroupProps {
  value: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

export function RadioGroup({ value, onValueChange, children, className }: RadioGroupProps) {
  return (
    <div className={cn("flex items-center gap-1 rounded-xl bg-muted p-1", className)} role="radiogroup">
      {React.Children.map(children, (child) => {
        if (!React.isValidElement(child)) return child;
        return React.cloneElement(child as React.ReactElement<RadioItemProps>, {
          checked: (child.props as RadioItemProps).value === value,
          onChange: () => onValueChange((child.props as RadioItemProps).value),
        });
      })}
    </div>
  );
}

interface RadioItemProps {
  value: string;
  label: string;
  checked?: boolean;
  onChange?: () => void;
}

export function RadioItem({ value, label, checked, onChange }: RadioItemProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      onClick={onChange}
      className={cn(
        "relative rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200",
        checked
          ? "bg-card text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      )}
    >
      {label}
      <input type="radio" value={value} checked={checked} className="sr-only" readOnly />
    </button>
  );
}
