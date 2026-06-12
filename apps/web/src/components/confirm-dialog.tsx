"use client";

/**
 * ConfirmDialog — standardised confirmation modal for destructive or
 * high-impact operations.
 *
 * Usage guidelines:
 *   - DESTRUCTIVE (delete, archive, revert): use variant="destructive"
 *     to show a red confirm button and alert-triangle icon.
 *   - DEFAULT (save, publish, confirm): use variant="default" (or omit)
 *     for the primary-action glow button.
 *   - Always pass `consequence` for destructive operations so users
 *     understand what they're about to lose ("此操作不可撤销").
 *   - Pass `isLoading` to show a loading state and prevent double-clicks.
 *   - The dialog closes on Escape, overlay click, and the cancel button.
 *
 * @example
 * ```tsx
 * <ConfirmDialog
 *   open={deleteDialogOpen}
 *   onOpenChange={setDeleteDialogOpen}
 *   title="确认删除"
 *   description="将永久删除此文档，无法恢复。"
 *   consequence="此操作不可撤销"
 *   confirmLabel="确认删除"
 *   variant="destructive"
 *   isLoading={isDeleting}
 *   onConfirm={handleDelete}
 * />
 * ```
 */

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  consequence?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "destructive";
  isLoading?: boolean;
  onConfirm: () => void;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  consequence,
  confirmLabel = "确认",
  cancelLabel = "取消",
  variant = "default",
  isLoading = false,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="glass-strong rounded-2xl border-white/10 max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            {variant === "destructive" && (
              <AlertTriangle className="h-5 w-5 text-red-400" />
            )}
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription className="text-muted-foreground">
              {description}
            </DialogDescription>
          )}
          {consequence && (
            <p className="text-xs text-red-400/80 mt-1">{consequence}</p>
          )}
        </DialogHeader>
        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            {cancelLabel}
          </Button>
          <Button
            variant={variant === "destructive" ? "destructive" : "default"}
            onClick={onConfirm}
            disabled={isLoading}
            className={variant !== "destructive" ? "shadow-glow" : undefined}
          >
            {isLoading ? "处理中..." : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
