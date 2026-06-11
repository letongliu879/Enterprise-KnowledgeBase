"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  Search,
  ChevronLeft,
  BarChart3,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { SortDropdown } from "@/components/sort-dropdown";
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

function getPriorityConfig(priority?: string | null) {
  switch (priority) {
    case "P0":
      return { label: "P0", className: "bg-red-500/15 text-red-400 border-red-500/30" };
    case "P1":
      return { label: "P1", className: "bg-orange-500/15 text-orange-400 border-orange-500/30" };
    case "P2":
      return { label: "P2", className: "bg-blue-500/15 text-blue-400 border-blue-500/30" };
    default:
      return null;
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

function formatDuration(ms: number): string {
  if (ms < 60000) return `${Math.floor(ms / 1000)}秒`;
  if (ms < 3600000) return `${Math.floor(ms / 60000)}分钟`;
  if (ms < 86400000) return `${Math.floor(ms / 3600000)}小时`;
  return `${Math.floor(ms / 86400000)}天`;
}

const PAGE_SIZE = 20;

const SORT_OPTIONS = [
  { value: "updated_at", label: "更新时间" },
  { value: "created_at", label: "创建时间" },
  { value: "filename", label: "文件名" },
];

export default function ReviewQueuePage() {
  const queryClient = useQueryClient();
  const [collectionFilter, setCollectionFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const [assigneeFilter, setAssigneeFilter] = useState("ALL");
  const [selectedTicketIds, setSelectedTicketIds] = useState<Set<string>>(new Set());
  const [autoRefresh, setAutoRefresh] = useState(false);

  const { data: me } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
  });
  const userId = me?.user_id ?? "";
  const userTenantId = me?.tenant_id ?? "";

  const { data: collectionResponse, isLoading: collectionsLoading } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["tickets", page, PAGE_SIZE],
    queryFn: () => workbenchApi.listTickets({ page, page_size: PAGE_SIZE }),
  });

  // Auto-refresh toggle (5s interval)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      refetch();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, refetch]);

  const collections = collectionResponse?.items ?? [];
  const tickets = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const normalizedStatusFilter = normalizeStatus(
    statusFilter === "ALL" ? undefined : statusFilter
  );

  // Client-side filtering and sorting
  const filteredTickets = useMemo(() => {
    let result = tickets.filter((ticket) => {
      const matchesCollection =
        collectionFilter === "ALL" ||
        String(ticket.collection_id || "") === collectionFilter;
      const matchesStatus =
        !normalizedStatusFilter ||
        normalizeStatus(ticket.status) === normalizedStatusFilter;
      const matchesSearch =
        !searchQuery.trim() ||
        ticket.ticket_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ticket.filename?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ticket.doc_id?.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesPriority =
        priorityFilter === "ALL" || ticket.priority === priorityFilter;
      const matchesAssignee =
        assigneeFilter === "ALL" ||
        (assigneeFilter === "mine" && ticket.assignee_user_id === userId) ||
        (assigneeFilter === "unassigned" && !ticket.assignee_user_id);
      return (
        matchesCollection &&
        matchesStatus &&
        matchesSearch &&
        matchesPriority &&
        matchesAssignee
      );
    });

    // Client-side sort
    result = [...result].sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case "updated_at":
          cmp =
            new Date(a.updated_at || a.created_at).getTime() -
            new Date(b.updated_at || b.created_at).getTime();
          break;
        case "created_at":
          cmp =
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
        case "filename":
          cmp = (a.filename || "").localeCompare(b.filename || "", "zh-CN");
          break;
        default:
          cmp = 0;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return result;
  }, [
    tickets,
    collectionFilter,
    normalizedStatusFilter,
    searchQuery,
    priorityFilter,
    assigneeFilter,
    userId,
    sortBy,
    sortDir,
  ]);

  // Queue stats (computed from loaded data)
  const stats = useMemo(() => {
    const pending = tickets.filter((t) => normalizeStatus(t.status) === "pending").length;
    const processed = tickets.filter((t) => normalizeStatus(t.status) !== "pending").length;

    // Average processing duration for processed tickets (updated_at - created_at)
    const processedTickets = tickets.filter(
      (t) => normalizeStatus(t.status) !== "pending" && t.updated_at
    );
    let avgDuration = "-";
    if (processedTickets.length > 0) {
      const totalMs = processedTickets.reduce((sum, t) => {
        const created = new Date(t.created_at).getTime();
        const updated = new Date(t.updated_at!).getTime();
        return sum + (updated - created);
      }, 0);
      avgDuration = formatDuration(Math.floor(totalMs / processedTickets.length));
    }

    return { pending, processed, avgDuration };
  }, [tickets]);

  // Batch decision mutation
  const batchDecide = useMutation({
    mutationFn: async ({
      action,
      ticketIds,
    }: {
      action: "APPROVE" | "REJECT";
      ticketIds: string[];
    }) => {
      const results: Array<{ ticket_id: string; success: boolean; error?: string }> = [];
      for (const ticketId of ticketIds) {
        try {
          const ticket = tickets.find((t) => t.ticket_id === ticketId);
          await workbenchApi.decideTicket(ticketId, {
            decision_request_id: `batch_${Date.now()}_${ticketId}`,
            action,
            tenant_id: ticket?.collection_id ? "" : "",
            collection_id: ticket?.collection_id ?? "",
          });
          results.push({ ticket_id: ticketId, success: true });
        } catch (err) {
          results.push({
            ticket_id: ticketId,
            success: false,
            error: isApiError(err) ? err.message : String(err),
          });
        }
      }
      return results;
    },
    onSuccess: (results) => {
      const succeeded = results.filter((r) => r.success).length;
      const failed = results.filter((r) => !r.success).length;
      if (succeeded > 0) {
        toast.success(`批量操作完成：${succeeded} 个成功`);
      }
      if (failed > 0) {
        toast.error(`${failed} 个失败`);
      }
      setSelectedTicketIds(new Set());
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "批量操作失败");
    },
  });

  const handleSortChange = useCallback((value: string, direction: "asc" | "desc") => {
    setSortBy(value);
    setSortDir(direction);
  }, []);

  const handleSelectTicket = useCallback((ticketId: string, checked: boolean) => {
    setSelectedTicketIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(ticketId);
      } else {
        next.delete(ticketId);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback((checked: boolean) => {
    if (checked) {
      const pendingIds = filteredTickets
        .filter((t) => normalizeStatus(t.status) === "pending")
        .map((t) => t.ticket_id);
      setSelectedTicketIds(new Set(pendingIds));
    } else {
      setSelectedTicketIds(new Set());
    }
  }, [filteredTickets]);

  const isAllSelected =
    filteredTickets.filter((t) => normalizeStatus(t.status) === "pending").length > 0 &&
    filteredTickets
      .filter((t) => normalizeStatus(t.status) === "pending")
      .every((t) => selectedTicketIds.has(t.ticket_id));

  const isIndeterminate =
    !isAllSelected &&
    filteredTickets.some(
      (t) => normalizeStatus(t.status) === "pending" && selectedTicketIds.has(t.ticket_id)
    );

  const selectedPendingIds = useMemo(() => {
    return Array.from(selectedTicketIds).filter(
      (id) => normalizeStatus(tickets.find((t) => t.ticket_id === id)?.status) === "pending"
    );
  }, [selectedTicketIds, tickets]);

  const hasActiveFilters =
    collectionFilter !== "ALL" ||
    statusFilter !== "ALL" ||
    priorityFilter !== "ALL" ||
    assigneeFilter !== "ALL" ||
    searchQuery.trim().length > 0;

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

      {/* Queue stats bar */}
      <motion.div
        variants={staggerItem}
        className="flex flex-wrap items-center gap-3 rounded-xl border bg-card/60 p-3"
      >
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">队列统计</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-3 py-1.5">
          <span className="text-xs text-muted-foreground">待复核</span>
          <span className="text-sm font-semibold text-amber-400">{stats.pending}</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-lg bg-emerald-500/10 px-3 py-1.5">
          <span className="text-xs text-muted-foreground">已处理</span>
          <span className="text-sm font-semibold text-emerald-400">{stats.processed}</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-lg bg-blue-500/10 px-3 py-1.5">
          <span className="text-xs text-muted-foreground">平均处理时长</span>
          <span className="text-sm font-semibold text-blue-400">{stats.avgDuration}</span>
        </div>
        <div className="ml-auto">
          <Switch
            label="自动刷新"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh((e.target as HTMLInputElement).checked)}
          />
        </div>
      </motion.div>

      {/* Filters and search */}
      <motion.div
        variants={staggerItem}
        className="flex flex-wrap items-center gap-2"
      >
        {/* Search */}
        <div className="relative flex items-center">
          <Search className="absolute left-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="搜索 ticket / 文件名 / doc_id"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 w-52 rounded-full border border-white/10 bg-white/5 pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        </div>

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

        {/* Priority filter */}
        <Select
          value={priorityFilter}
          onValueChange={(value) => setPriorityFilter(value ?? "ALL")}
        >
          <SelectTrigger className="w-32 h-8 glass rounded-full border-white/10 text-xs">
            <AlertCircle className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="优先级" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">全部优先级</SelectItem>
            <SelectItem value="P0">P0</SelectItem>
            <SelectItem value="P1">P1</SelectItem>
            <SelectItem value="P2">P2</SelectItem>
          </SelectContent>
        </Select>

        {/* Assignee filter */}
        <Select
          value={assigneeFilter}
          onValueChange={(value) => setAssigneeFilter(value ?? "ALL")}
        >
          <SelectTrigger className="w-36 h-8 glass rounded-full border-white/10 text-xs">
            <Filter className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="分配" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">全部</SelectItem>
            <SelectItem value="mine">我的待办</SelectItem>
            <SelectItem value="unassigned">未分配</SelectItem>
          </SelectContent>
        </Select>

        {/* Sort */}
        <SortDropdown
          options={SORT_OPTIONS}
          value={sortBy}
          direction={sortDir}
          onChange={handleSortChange}
          className="h-8"
        />

        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 rounded-full hover:bg-white/[0.06]"
            onClick={() => {
              setCollectionFilter("ALL");
              setStatusFilter("ALL");
              setPriorityFilter("ALL");
              setAssigneeFilter("ALL");
              setSearchQuery("");
            }}
          >
            <RotateCcw className="mr-1 h-3 w-3" />
            清除筛选
          </Button>
        )}
      </motion.div>

      {/* Batch action bar */}
      {selectedPendingIds.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 rounded-xl border bg-card/60 p-3"
        >
          <span className="text-sm text-muted-foreground">
            已选择 <strong className="text-foreground">{selectedPendingIds.length}</strong> 个待复核工单
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button
              size="sm"
              variant="default"
              className="h-7 text-xs"
              onClick={() =>
                batchDecide.mutate({ action: "APPROVE", ticketIds: selectedPendingIds })
              }
              disabled={batchDecide.isPending}
            >
              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
              批量批准
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="h-7 text-xs"
              onClick={() =>
                batchDecide.mutate({ action: "REJECT", ticketIds: selectedPendingIds })
              }
              disabled={batchDecide.isPending}
            >
              <XCircle className="mr-1 h-3.5 w-3.5" />
              批量拒绝
            </Button>
          </div>
        </motion.div>
      )}

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
          variant="review"
        />
      )}

      {!isLoading && !error && filteredTickets.length > 0 && (
        <div className="space-y-2">
          {/* Select all header */}
          <div className="flex items-center gap-2 px-1">
            <Checkbox
              indeterminate={isIndeterminate}
              checked={isAllSelected}
              onChange={(e) =>
                handleSelectAll((e.target as HTMLInputElement).checked)
              }
            />
            <span className="text-xs text-muted-foreground">
              {selectedTicketIds.size > 0
                ? `已选择 ${selectedTicketIds.size} 项`
                : "全选待复核"}
            </span>
          </div>

          {filteredTickets.map((ticket, index) => {
            const config = getTicketStatusConfig(ticket.status);
            const StatusIcon = config.icon;
            const displayTitle =
              ticket.filename?.trim() ||
              ticket.title?.trim() ||
              ticket.doc_id?.trim() ||
              ticket.ticket_id;
            const priorityConfig = getPriorityConfig(ticket.priority);
            const isPending = normalizeStatus(ticket.status) === "pending";

            return (
              <motion.div
                key={ticket.ticket_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04 }}
              >
                <Link href={`/review/${ticket.ticket_id}`} className="block">
                <Card interactive className="relative overflow-hidden">
                  <div
                    className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${config.dotColor}`}
                    style={{ opacity: 0.5 }}
                  />

                  <CardContent className="flex items-center gap-4 p-4 pl-5">
                    {isPending && (
                      <Checkbox
                        checked={selectedTicketIds.has(ticket.ticket_id)}
                        onChange={(e) => {
                          e.stopPropagation();
                          handleSelectTicket(
                            ticket.ticket_id,
                            (e.target as HTMLInputElement).checked
                          );
                        }}
                        className="shrink-0"
                      />
                    )}
                    {!isPending && <div className="w-4 shrink-0" />}

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
                        {priorityConfig && (
                          <Badge
                            variant="outline"
                            className={`h-5 text-[10px] ${priorityConfig.className}`}
                          >
                            {priorityConfig.label}
                          </Badge>
                        )}
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

      {/* Pagination */}
      {!isLoading && !error && totalPages > 1 && (
        <motion.div
          variants={staggerItem}
          className="flex items-center justify-center gap-2 pt-4"
        >
          <Button
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <Button
              key={p}
              variant={p === page ? "default" : "outline"}
              size="sm"
              className="h-8 min-w-[2rem] px-2 text-xs"
              onClick={() => setPage(p)}
            >
              {p}
            </Button>
          ))}
          <Button
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <span className="ml-2 text-xs text-muted-foreground">
            共 {total} 条
          </span>
        </motion.div>
      )}
    </motion.div>
  );
}
