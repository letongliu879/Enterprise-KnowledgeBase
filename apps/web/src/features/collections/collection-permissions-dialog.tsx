"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Shield, Info } from "lucide-react";

interface CollectionPermissionsDialogProps {
  open: boolean;
  onClose: () => void;
  collectionId: string;
  tenantId: string;
}

export function CollectionPermissionsDialog({ open, onClose, collectionId, tenantId }: CollectionPermissionsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>集合权限</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="rounded-2xl border bg-muted/10 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">集合 ID</span>
              <span className="text-sm font-mono">{collectionId}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">租户 ID</span>
              <span className="text-sm font-mono">{tenantId}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">默认访问</span>
              <Badge variant="secondary">内部</Badge>
            </div>
          </div>

          <div className="rounded-xl border bg-amber-50/50 dark:bg-amber-950/20 p-3 flex gap-2">
            <Info className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 dark:text-amber-200">
              权限配置功能需要后端 API 支持。当前显示的是基本信息。详细的角色和用户级别权限管理将在后续版本中提供。
            </p>
          </div>

          <div className="flex justify-end">
            <Button variant="outline" onClick={onClose}>关闭</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
