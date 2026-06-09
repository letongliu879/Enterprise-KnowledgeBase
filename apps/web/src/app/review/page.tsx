"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Inbox,
  AlertCircle,
  Clock,
  CheckCircle2,
  XCircle,
  Filter,
  ChevronRight,
  FileText,
  ArrowLeft,
  Database,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { BackendGap } from "@/components/backend-gap";
import { isBackendGap, isApiError, getErrorMessage } from "@/lib/api/errors";
import { normalizeStatus } from "@/lib/status";
import { staggerContainer, staggerItem } from "@/lib/animations";

function getTicketStatusConfig(status: string) {
  const normalized = normalizeStatus(status);
  switch (normalized) {
    case "pending":
      return {
        icon: Clock,
        color: "text-amber-400",
        bgColor: "bg-amber-500/10",
        borderColor: "border-amber-500/20",
        dotColor: "bg-amber-400",
        label: "待复核",
      };
    case "approved":
      return {
        icon: CheckCircle2,
        color: "text-emerald-400",
        bgColor: "bg-emerald-500/10",
        borderColor: "border-emerald-500/20",
        dotColor: "bg-emerald-400",
        label: "已批准",
      };
    case "rejected":
      return {
        icon: XCircle,
        color: "text-red-400",
        bgColor: "bg-red-500/10",
        borderColor: "border-red-500/20",
        dotColor: "bg-red-400",
        label: "已拒绝",
      };
    case "returned":
      return {
        icon: ArrowLeft,
        color: "text-orange-400",
        bgColor: "bg-orange-500/10",
        borderColor: "border-orange-500/20",
        dotColor: "bg-orange-400",
        label: "已退回",
      };
    default:
      return {
        icon: AlertCircle,
        color: "text-slate-400",
        bgColor: "bg-slate-500/10",
        borderColor: "border-slate-500/20",
        dotColor: "bg-slate-400",
        label: status || "未知",
      };
  }
}

function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return "-";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffHours < 24) return `${diffHours} 小时前`;
  if (diffDays < 7) return `${diffDays} 天前`;
  return date.toLocaleDateString("zh-CN");
}

export default function ReviewQueuePage() {
  const [collectionFilter, setCollectionFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const { data: me } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";

  const { data: collectionResponse, isLoading: collectionsLoading } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["tickets"],
    queryFn: () => workbenchApi.listTickets({ page_size: 100 }),
  });

  const collections = collectionResponse?.items ?? [];
  const tickets = data?.items ?? [];
  const normalizedStatusFilter = normalizeStatus(
    statusFilter === "ALL" ? undefined : statusFilter
  );

  const filteredTickets = tickets.filter((ticket) => {
    const matchesCollection =
      collectionFilter === "ALL" ||
      String(ticket.collection_id || "") === collectionFilter;
    const matchesStatus =
      !normalizedStatusFilter ||
      normalizeStatus(ticket.status) === normalizedStatusFilter;
    return matchesCollection && matchesStatus;
  });

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      <motion.div variants={staggerItem}>
        <h1 className="text-2xl font-semibold tracking-tight">人工复核队列</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          自动入库代理拦截的文档会在这里等待人工复核。
        </p>
      </motion.div>

      <motion.div
        variants={staggerItem}
        className="flex flex-wrap items-center gap-2"
      >
        <Select
          value={collectionFilter}
          onValueChange={(value) => setCollectionFilter(value ?? "ALL")}
          disabled={collectionsLoading}
        >
          <SelectTrigger className="w-52 h-8 glass rounded-full border-white/10 text-xs">
            <Database className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="知识库集合" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">全部集合</SelectItem>
            {collections.map((collection) => (
              <SelectItem
                key={collection.collection_id}
                value={collection.collection_id}
              >
                <div className="flex items-center gap-2">
                  <span>{collection.name}</span>
                  <span className="text-[10px] text-muted-foreground">
                    {collection.collection_id}
                  </span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={statusFilter}
          onValueChange={(value) => setStatusFilter(value ?? "ALL")}
        >
          <SelectTrigger className="w-36 h-8 glass rounded-full border-white/10 text-xs">
            <Filter className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">全部状态</SelectItem>
            <SelectItem value="PENDING">待复核</SelectItem>
            <SelectItem value="APPROVED">已批准</SelectItem>
            <SelectItem value="REJECTED">已拒绝</SelectItem>
            <SelectItem value="RETURNED">已退回</SelectItem>
          </SelectContent>
        </Select>

        {(collectionFilter !== "ALL" || statusFilter !== "ALL") && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 rounded-full hover:bg-white/[0.06]"
            onClick={() => {
              setCollectionFilter("ALL");
              setStatusFilter("ALL");
            }}
          >
            清除筛选
          </Button>
        )}
      </motion.div>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-[72px] rounded-xl" />
          ))}
        </div>
      )}

      {error &&
        (isBackendGap(error) ? (
          <BackendGap
            feature="Review Queue (Tickets)"
            endpoint={error.endpoint}
          />
        ) : (
          <div className="glass rounded-xl border border-red-500/20 p-4 text-sm text-red-400">
            {isApiError(error) ? error.message : getErrorMessage(error)}
          </div>
        ))}

      {!isLoading && !error && filteredTickets.length === 0 && (
        <EmptyState
          icon={Inbox}
          title="暂无复核工单"
          description="当前没有需要人工处理的复核任务。"
        />
      )}

      {!isLoading && !error && filteredTickets.length > 0 && (
        <div className="space-y-2">
          {filteredTickets.map((ticket, index) => {
            const config = getTicketStatusConfig(ticket.status);
            const StatusIcon = config.icon;
            const displayTitle =
              ticket.filename?.trim() ||
              ticket.title?.trim() ||
              ticket.doc_id?.trim() ||
              ticket.ticket_id;

            return (
              <motion.div
                key={ticket.ticket_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04 }}
              >
                <Link href={`/review/${ticket.ticket_id}`}>
                  <Card interactive className="relative overflow-hidden">
                    <div
                      className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${config.dotColor}`}
                      style={{ opacity: 0.5 }}
                    />

                    <CardContent className="flex items-center gap-4 p-4 pl-5">
                      <div
                        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${config.bgColor}`}
                      >
                        <StatusIcon className={`h-5 w-5 ${config.color}`} />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <FileText className="h-3.5 w-3.5 text-muted-foreground/40" />
                          <span className="truncate text-sm font-medium">
                            {displayTitle}
                          </span>
                        </div>
                        <div className="mt-1.5 flex items-center gap-3">
                          <Badge
                            variant="outline"
                            className="h-5 border-white/10 text-[10px]"
                          >
                            {ticket.collection_id}
                          </Badge>
                          <span className="font-mono text-[11px] text-muted-foreground/50">
                            {ticket.ticket_id}
                          </span>
                          <span
                            className="text-[11px] text-muted-foreground/50"
                            title={
                              ticket.updated_at
                                ? new Date(ticket.updated_at).toLocaleString()
                                : undefined
                            }
                          >
                            {formatRelativeTime(ticket.updated_at)}
                          </span>
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        <Badge
                          variant="outline"
                          className={`h-6 border text-[10px] ${config.borderColor} ${config.bgColor}`}
                        >
                          {config.label === "待复核" && (
                            <span className="relative mr-1 flex h-2 w-2">
                              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                              <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-400" />
                            </span>
                          )}
                          <span className={config.color}>{config.label}</span>
                        </Badge>
                        <ChevronRight className="h-4 w-4 text-muted-foreground/40 transition-transform duration-200 group-hover/card:translate-x-0.5" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
