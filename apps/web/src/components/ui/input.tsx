import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-10 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm",
        "placeholder:text-muted-foreground/50",
        "focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/30",
        "focus:shadow-[0_0_15px_rgba(99,102,241,0.15)]",
        "hover:border-white/20",
        "transition-all duration-200",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive/50 aria-invalid:ring-destructive/20",
        className
      )}
      {...props}
    />
  )
}

export { Input }
