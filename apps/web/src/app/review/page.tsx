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
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
        label: "已驳回",
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
        label: status,
      };
  }
}

function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;
  return date.toLocaleDateString("zh-CN");
}

export default function ReviewQueuePage() {
  const [collectionFilter, setCollectionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const { data, isLoading, error } = useQuery({
    queryKey: ["tickets", collectionFilter, statusFilter],
    queryFn: () =>
      workbenchApi.listTickets({
        collection_id: collectionFilter || undefined,
        status: statusFilter === "ALL" ? undefined : statusFilter,
      }),
  });

  const tickets = data?.items ?? [];

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div variants={staggerItem}>
        <h1 className="text-2xl font-semibold tracking-tight">人工复核队列</h1>
        <p className="text-sm text-muted-foreground mt-1">
          自动入库代理拦截的文档，等待人工复核。
        </p>
      </motion.div>

      {/* Filters */}
      <motion.div
        variants={staggerItem}
        className="flex flex-wrap items-center gap-2"
      >
        <div className="flex items-center gap-2 glass rounded-full px-1 py-1">
          <Filter className="h-3.5 w-3.5 text-muted-foreground ml-2" />
          <Input
            placeholder="知识库集合..."
            value={collectionFilter}
            onChange={(e) => setCollectionFilter(e.target.value)}
            className="w-36 h-7 bg-transparent border-0 focus-visible:ring-0 focus-visible:shadow-none px-0 text-sm"
          />
        </div>

        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v ?? "ALL")}
        >
          <SelectTrigger className="w-32 h-8 glass rounded-full border-white/10 text-xs">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-400" />
                全部
              </div>
            </SelectItem>
            <SelectItem value="PENDING">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400" />
                待复核
              </div>
            </SelectItem>
            <SelectItem value="APPROVED">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                已批准
              </div>
            </SelectItem>
            <SelectItem value="REJECTED">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-400" />
                已驳回
              </div>
            </SelectItem>
            <SelectItem value="RETURNED">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-orange-400" />
                已退回
              </div>
            </SelectItem>
          </SelectContent>
        </Select>

        {(collectionFilter || statusFilter !== "ALL") && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 rounded-full hover:bg-white/[0.06]"
            onClick={() => {
              setCollectionFilter("");
              setStatusFilter("ALL");
            }}
          >
            清除筛选
          </Button>
        )}
      </motion.div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[72px] rounded-xl" />
          ))}
        </div>
      )}

      {/* Error */}
      {error &&
        (isBackendGap(error) ? (
          <BackendGap
            feature="Review Queue (Tickets)"
            endpoint={error.endpoint}
          />
        ) : (
          <div className="text-red-400 text-sm glass rounded-xl p-4 border-red-500/20">
            {isApiError(error) ? error.message : getErrorMessage(error)}
          </div>
        ))}

      {/* Empty */}
      {!isLoading &&
        !error &&
        tickets.length === 0 && (
          <EmptyState
            icon={Inbox}
            title="暂无复核工单"
            description="所有文档已处理完毕。上传新文件以生成复核工单。"
          />
        )}

      {/* Ticket List */}
      {!isLoading &&
        !error &&
        tickets.length > 0 && (
          <div className="space-y-2">
            {tickets.map((ticket, i) => {
              const config = getTicketStatusConfig(ticket.status);
              const StatusIcon = config.icon;

              return (
                <motion.div
                  key={ticket.ticket_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Link href={`/review/${ticket.ticket_id}`}>
                    <Card
                      interactive
                      className="relative overflow-hidden"
                    >
                      {/* Status color bar */}
                      <div
                        className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${config.dotColor}`}
                        style={{ opacity: 0.5 }}
                      />

                      <CardContent className="p-4 flex items-center gap-4 pl-5">
                        {/* Status icon */}
                        <div
                          className={`flex items-center justify-center w-10 h-10 rounded-xl shrink-0 ${config.bgColor}`}
                        >
                          <StatusIcon
                            className={`h-5 w-5 ${config.color}`}
                          />
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <FileText className="h-3.5 w-3.5 text-muted-foreground/40" />
                            <span className="text-sm font-medium truncate">
                              {ticket.doc_id ?? ticket.ticket_id}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 mt-1.5">
                            <Badge
                              variant="outline"
                              className="text-[10px] h-5 border-white/10"
                            >
                              {ticket.collection_id}
                            </Badge>
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

                        {/* Status */}
                        <div className="flex items-center gap-2 shrink-0">
                          <Badge
                            variant="outline"
                            className={`text-[10px] h-6 border ${config.borderColor} ${config.bgColor}`}
                          >
                            {config.label === "待复核" && (
                              <span className="relative flex h-2 w-2 mr-1">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-400" />
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
