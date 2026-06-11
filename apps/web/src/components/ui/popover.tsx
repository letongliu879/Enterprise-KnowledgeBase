"use client";

import * as React from "react";
import * as BasePopover from "@base-ui/react/popover";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { dropdownMenu } from "@/lib/animations";

const PopoverProvider = BasePopover.Popover.Root;

const PopoverTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof BasePopover.Popover.Trigger>
>(({ className, ...props }, ref) => (
  <BasePopover.Popover.Trigger
    ref={ref}
    className={cn("cursor-pointer", className)}
    {...props}
  />
));
PopoverTrigger.displayName = "PopoverTrigger";

const PopoverContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof BasePopover.Popover.Popup>
>(({ className, children, ...props }, ref) => (
  <BasePopover.Popover.Portal>
    <BasePopover.Popover.Positioner sideOffset={4} align="start">
      <BasePopover.Popover.Popup
        ref={ref}
        className={cn(
          "z-50 rounded-xl border border-white/[0.06] bg-card shadow-lg outline-none",
          className
        )}
        {...props}
      >
        <AnimatePresence>
          <motion.div
            variants={dropdownMenu}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </BasePopover.Popover.Popup>
    </BasePopover.Popover.Positioner>
  </BasePopover.Popover.Portal>
));
PopoverContent.displayName = "PopoverContent";

const PopoverArrow = BasePopover.Popover.Arrow;

export { PopoverProvider, PopoverTrigger, PopoverContent, PopoverArrow };
