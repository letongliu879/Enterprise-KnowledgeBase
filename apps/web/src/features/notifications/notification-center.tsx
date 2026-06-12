"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { workbenchApi } from "@/lib/api/client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import type { NotificationItem } from "@/lib/api/types";

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: unreadCountData } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => workbenchApi.getUnreadCount(),
  });

  const { data: notificationsData, isLoading, error, refetch } = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => workbenchApi.getNotifications(),
    enabled: open,
  });

  const markRead = useMutation({
    mutationFn: (id: string) => workbenchApi.markNotificationRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const markAllRead = useMutation({
    mutationFn: () => workbenchApi.readAllNotifications(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.setQueryData(["notifications", "unread-count"], { count: 0 });
    },
  });

  const handleNotificationClick = (notification: NotificationItem) => {
    if (!notification.is_read) {
      markRead.mutate(notification.notification_id);
    }
    if (notification.link) {
      router.push(notification.link);
    }
    setOpen(false);
  };

  const unreadCount = unreadCountData?.count ?? 0;
  const notifications: NotificationItem[] = notificationsData?.items ?? [];

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        aria-label="Notifications"
        onClick={() => setOpen((prev) => !prev)}
        className="h-8 w-8 rounded-xl hover:bg-accent transition-colors relative"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] text-white font-medium">
            {unreadCount}
          </span>
        )}
      </Button>

      <AnimatePresence>
        {open && (
          <motion.div
            data-testid="notification-panel"
            initial={{ opacity: 0, y: -8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
            transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
            className="absolute right-0 mt-2 w-80 rounded-2xl border border-white/[0.06] glass backdrop-blur-sm shadow-lg z-50 overflow-hidden"
            role="dialog"
            aria-label="通知面板"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
              <span className="font-medium text-sm">Notifications</span>
              {unreadCount > 0 && (
                <button
                  onClick={() => markAllRead.mutate()}
                  className="text-xs text-primary hover:text-primary/80 transition-colors"
                >
                  全部已读
                </button>
              )}
            </div>

            {isLoading && (
              <div data-testid="notification-skeleton" className="p-4 space-y-3">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-5/6" />
              </div>
            )}

            {error && (
              <div className="p-4">
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>加载失败</AlertTitle>
                  <AlertDescription>加载通知失败</AlertDescription>
                </Alert>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2 w-full"
                  onClick={() => refetch()}
                >
                  重试
                </Button>
              </div>
            )}

            {!isLoading && !error && notifications.length === 0 && (
              <EmptyState icon={Bell} title="暂无通知" />
            )}

            {!isLoading && !error && notifications.length > 0 && (
              <ul className="max-h-96 overflow-auto">
                {notifications.map((n) => (
                  <li
                    key={n.notification_id}
                    data-testid={n.is_read ? "notification-item-read" : "notification-item-unread"}
                    onClick={() => handleNotificationClick(n)}
                    className={`cursor-pointer px-4 py-3 border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.04] transition-colors ${
                      n.is_read ? "opacity-60" : ""
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <div className="mt-0.5">
                        <Bell className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{n.title}</p>
                        <p className="text-xs text-muted-foreground truncate">{n.message}</p>
                        <p className="text-xs text-muted-foreground/60 mt-1">{n.created_at}</p>
                      </div>
                      {!n.is_read && (
                        <span className="mt-1.5 h-2 w-2 rounded-full bg-blue-500 shrink-0" />
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
