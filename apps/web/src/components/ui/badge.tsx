import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex h-6 w-fit shrink-0 items-center justify-center gap-1.5 overflow-hidden rounded-full px-3 py-0.5 text-xs font-semibold whitespace-nowrap transition-all duration-200 border backdrop-blur-sm",
  {
    variants: {
      variant: {
        default: "bg-gradient-to-r from-primary to-primary/80 text-primary-foreground border-primary/20 shadow-glow",
        secondary:
          "bg-secondary/80 text-secondary-foreground border-white/10 hover:bg-secondary",
        destructive:
          "bg-gradient-to-r from-destructive/20 to-destructive/10 text-destructive border-destructive/20 hover:shadow-[0_0_15px_rgba(239,68,68,0.15)]",
        outline:
          "bg-transparent text-foreground border-white/15 hover:bg-white/[0.04] hover:border-white/25",
        ghost:
          "bg-transparent text-muted-foreground border-transparent hover:bg-white/[0.04] hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline border-transparent bg-transparent",
        success:
          "bg-gradient-to-r from-emerald-500/20 to-emerald-500/10 text-emerald-400 border-emerald-500/20",
        warning:
          "bg-gradient-to-r from-amber-500/20 to-amber-500/10 text-amber-400 border-amber-500/20",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
