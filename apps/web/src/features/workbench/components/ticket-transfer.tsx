"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRightLeft, UserCheck, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { workbenchApi } from "@/lib/api/client";
import { isApiError, isBackendGap } from "@/lib/api/errors";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

interface TicketTransferDialogProps {
  ticketId: string;
  currentAssigneeId?: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTransferred: () => void;
}

export function TicketTransferDialog({
  ticketId,
  currentAssigneeId,
  open,
  onOpenChange,
  onTransferred,
}: TicketTransferDialogProps) {
  const [assigneeId, setAssigneeId] = useState("");
  const [reason, setReason] = useState("");

  const mockUsers = [
    { user_id: "user-001", display_name: "张三" },
    { user_id: "user-002", display_name: "李四" },
    { user_id: "user-003", display_name: "王五" },
    { user_id: "user-004", display_name: "赵六" },
  ];

  const transferMutation = useMutation({
    mutationFn: () =>
      workbenchApi.transferTicket(ticketId, {
        assignee_user_id: assigneeId,
        reason: reason || undefined,
      }),
    onSuccess: () => {
      toast.success("工单已转让");
      setAssigneeId("");
      setReason("");
      onOpenChange(false);
      onTransferred();
    },
    onError: (err) => {
      if (isBackendGap(err)) {
        toast.error("后端暂不支持转让操作");
      } else {
        toast.error(isApiError(err) ? err.message : "转让失败");
      }
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowRightLeft className="h-5 w-5" />
            转让工单
          </DialogTitle>
          <DialogDescription>将工单转让给其他审核员处理。</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>选择审核员</Label>
            <Select value={assigneeId} onValueChange={(value) => value && setAssigneeId(value)}>
              <SelectTrigger>
                <SelectValue placeholder="请选择审核员" />
              </SelectTrigger>
              <SelectContent>
                {mockUsers
                  .filter((u) => u.user_id !== currentAssigneeId)
                  .map((user) => (
                    <SelectItem key={user.user_id} value={user.user_id}>
                      <span className="flex items-center gap-2">
                        <UserCheck className="h-3.5 w-3.5 text-muted-foreground" />
                        {user.display_name}
                      </span>
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>转让原因（可选）</Label>
            <Textarea
              placeholder="输入转让原因..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="min-h-20"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={transferMutation.isPending}>
            取消
          </Button>
          <Button
            onClick={() => transferMutation.mutate()}
            disabled={!assigneeId || transferMutation.isPending}
          >
            {transferMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                转让中...
              </>
            ) : (
              "确认转让"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
