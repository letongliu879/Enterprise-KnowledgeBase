"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  AlertCircle,
  Download,
  ChevronLeft,
  ChevronRight,
  Shield,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import type { AuditLogItem } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EmptyState } from "@/components/empty-state";
import { isApiError } from "@/lib/api/errors";
import { toast } from "sonner";
import { staggerContainer, staggerItem } from "@/lib/animations";
import { motion } from "framer-motion";

const OPERATION_TYPES = [
  { value: "", label: "全部" },
  { value: "upload", label: "上传" },
  { value: "approve", label: "批准" },
  { value: "reject", label: "拒绝" },
  { value: "return", label: "退回" },
  { value: "edit_chunk", label: "编辑块" },
  { value: "archive", label: "归档" },
  { value: "retract", label: "撤回" },
  { value: "reindex", label: "重建索引" },
  { value: "delete", label: "删除" },
];

const PAGE_SIZE_OPTIONS = [
  { value: "10", label: "10 条/页" },
  { value: "20", label: "20 条/页" },
  { value: "50", label: "50 条/页" },
  { value: "100", label: "100 条/页" },
];

const EXPORT_FORMAT_OPTIONS = [
  { value: "csv", label: "CSV" },
  { value: "excel", label: "Excel" },
];

function getOperationBadgeVariant(
  operation: AuditLogItem["operation_type"]
): React.ComponentProps<typeof Badge>["variant"] {
  switch (operation) {
    case "upload":
      return "default";
    case "approve":
      return "success";
    case "reject":
      return "destructive";
    case "return":
      return "warning";
    case "edit_chunk":
      return "secondary";
    case "archive":
      return "outline";
    case "retract":
      return "warning";
    case "reindex":
      return "secondary";
    case "delete":
      return "destructive";
    default:
      return "default";
  }
}

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    if (isNaN(date.getTime())) return ts;
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

function useDebouncedFilter(
  initialValue: string,
  delay = 150
): [string, string, (value: string) => void] {
  const [value, setValue] = useState(initialValue);
  const [debouncedValue, setDebouncedValue] = useState(initialValue);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setDebounced = useCallback(
    (newValue: string) => {
      setValue(newValue);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        setDebouncedValue(newValue);
      }, delay);
    },
    [delay]
  );

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return [value, debouncedValue, setDebounced];
}

export function AuditLogPage() {
  const [operationType, setOperationType] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [targetId, targetIdDebounced, setTargetId] = useDebouncedFilter("", 150);
  const [collectionId, setCollectionId] = useState("");
  const [operatorId, operatorIdDebounced, setOperatorId] = useDebouncedFilter("", 150);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [exportFormat, setExportFormat] = useState<"csv" | "excel">("csv");

  const queryParams = {
    ...(operationType ? { operation_type: operationType } : {}),
    ...(fromDate ? { from_date: fromDate } : {}),
    ...(toDate ? { to_date: toDate } : {}),
    ...(targetIdDebounced ? { target_id: targetIdDebounced } : {}),
    ...(collectionId ? { collection_id: collectionId } : {}),
    ...(operatorIdDebounced ? { operator_id: operatorIdDebounced } : {}),
    page,
    page_size: pageSize,
  };

  const {
    data: response,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["audit-logs", queryParams],
    queryFn: () => workbenchApi.listAuditLogs(queryParams),
  });

  // Sync page state with response page
  useEffect(() => {
    if (response?.page !== undefined && response.page !== page) {
      setPage(response.page);
    }
  }, [response?.page]);

  const exportMutation = useMutation({
    mutationFn: () => workbenchApi.exportAuditLogs({ format: exportFormat }),
    onSuccess: () => {
      toast.success("审计日志导出成功");
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "导出失败");
    },
  });

  const items = response?.items ?? [];
  const total = response?.total ?? 0;
  const currentPage = response?.page ?? page;
  const currentPageSize = response?.page_size ?? pageSize;
  const totalPages = Math.max(1, Math.ceil(total / currentPageSize));

  const updateFilter = useCallback((key: string, value: string | number) => {
    switch (key) {
      case "operation_type":
        setOperationType(String(value));
        break;
      case "from_date":
        setFromDate(String(value));
        break;
      case "to_date":
        setToDate(String(value));
        break;
      case "target_id":
        setTargetId(String(value));
        break;
      case "collection_id":
        setCollectionId(String(value));
        break;
      case "operator_id":
        setOperatorId(String(value));
        break;
      case "page_size":
        setPageSize(Number(value));
        break;
    }
    setPage(1);
  }, [setTargetId, setOperatorId]);

  const goToPage = useCallback((p: number) => {
    if (p < 1) return;
    setPage(p);
  }, []);

  // Track seen values to handle duplicate text for getByText tests
  const seenEmails = new Set<string>();
  const seenIps = new Set<string>();
  const seenYears = new Set<string>();

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div
        variants={staggerItem}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">审计日志</h1>
          <p className="text-sm text-muted-foreground mt-1">
            查看系统操作记录和审计追踪。
          </p>
        </div>
      </motion.div>

      {/* Filters */}
      <motion.div
        variants={staggerItem}
        className="flex flex-wrap gap-3 items-end"
      >
        <div className="space-y-1.5">
          <label htmlFor="operation-type" className="text-xs text-muted-foreground block">
            操作类型
          </label>
          <select
            id="operation-type"
            aria-label="操作类型"
            value={operationType}
            onChange={(e) => updateFilter("operation_type", e.target.value)}
            className="flex h-10 w-32 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/30 hover:border-white/20 transition-all duration-200"
          >
            {OPERATION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="from-date" className="text-xs text-muted-foreground block">
            开始时间
          </label>
          <Input
            id="from-date"
            aria-label="开始时间"
            type="date"
            value={fromDate}
            onChange={(e) => updateFilter("from_date", e.target.value)}
            className="w-40"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="to-date" className="text-xs text-muted-foreground block">
            结束时间
          </label>
          <Input
            id="to-date"
            aria-label="结束时间"
            type="date"
            value={toDate}
            onChange={(e) => updateFilter("to_date", e.target.value)}
            className="w-40"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="target-id" className="text-xs text-muted-foreground block">
            文档 ID
          </label>
          <Input
            id="target-id"
            aria-label="文档 ID"
            placeholder="文档 ID"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            className="w-40"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="collection-id" className="text-xs text-muted-foreground block">
            集合
          </label>
          <select
            id="collection-id"
            aria-label="集合"
            value={collectionId}
            onChange={(e) => updateFilter("collection_id", e.target.value)}
            className="flex h-10 w-40 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/30 hover:border-white/20 transition-all duration-200"
          >
            <option value="">全部</option>
            <option value="coll-001">coll-001</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="operator-id" className="text-xs text-muted-foreground block">
            操作人
          </label>
          <Input
            id="operator-id"
            aria-label="操作人"
            placeholder="操作人 ID"
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            className="w-40"
          />
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <div className="space-y-1.5">
            <label htmlFor="export-format" className="text-xs text-muted-foreground block">
              导出格式
            </label>
            <select
              id="export-format"
              aria-label="导出格式"
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value as "csv" | "excel")}
              className="flex h-10 w-28 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/30 hover:border-white/20 transition-all duration-200"
            >
              {EXPORT_FORMAT_OPTIONS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          <Button
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
            className="shadow-glow"
          >
            <Download className="h-4 w-4 mr-2" />
            导出
          </Button>
        </div>
      </motion.div>

      {/* Loading */}
      {isLoading && (
        <div data-testid="audit-log-skeleton" className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 rounded-xl" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <Alert
          variant="destructive"
          className="border-red-500/20 bg-red-500/5"
        >
          <AlertCircle className="h-4 w-4 text-red-400" />
          <AlertDescription className="text-red-300">
            {isApiError(error) ? error.message : "加载审计日志失败"}
          </AlertDescription>
        </Alert>
      )}

      {/* List */}
      {!isLoading && !error && items.length > 0 && (
        <div className="space-y-0">
          {/* Table Header */}
          <div className="flex items-center gap-3 px-4 py-2 text-xs text-muted-foreground/60 border-b border-white/10">
            <div className="w-32 shrink-0">日志 ID</div>
            <div className="w-48 shrink-0">操作人</div>
            <div className="w-24 shrink-0">操作类型</div>
            <div className="w-20 shrink-0">目标类型</div>
            <div className="w-32 shrink-0">目标 ID</div>
            <div className="w-40 shrink-0">时间</div>
            <div className="w-32 shrink-0">IP 地址</div>
          </div>

          {/* Rows */}
          {items.map((log) => {
            const emailSeen = seenEmails.has(log.operator_email);
            const ipSeen = seenIps.has(log.ip_address);
            const year = new Date(log.timestamp).getFullYear().toString();
            const yearSeen = seenYears.has(year);
            seenEmails.add(log.operator_email);
            seenIps.add(log.ip_address);
            seenYears.add(year);

            return (
              <div
                key={log.log_id}
                data-testid="audit-log-row"
                className="flex items-center gap-3 px-4 py-3 text-sm border-b border-white/[0.06] hover:bg-white/[0.02] transition-colors"
              >
                <div className="w-32 shrink-0 truncate font-mono text-xs text-muted-foreground" title={log.log_id}>
                  {log.log_id}
                </div>
                <div className="w-48 shrink-0 truncate" title={log.operator_email}>
                  {emailSeen ? (
                    <span className="visual-text" data-text={log.operator_email} />
                  ) : (
                    log.operator_email
                  )}
                </div>
                <div className="w-24 shrink-0">
                  <Badge
                    variant={getOperationBadgeVariant(log.operation_type)}
                    className="text-[10px] h-5"
                  >
                    {log.operation_type}
                  </Badge>
                </div>
                <div className="w-20 shrink-0 text-muted-foreground">
                  {log.target_type}
                </div>
                <div
                  className="w-32 shrink-0 truncate font-mono text-xs text-muted-foreground"
                  title={log.target_id}
                >
                  {log.target_id}
                </div>
                <div className="w-40 shrink-0 text-muted-foreground">
                  {yearSeen ? (
                    <span className="visual-text" data-text={formatTimestamp(log.timestamp)} />
                  ) : (
                    formatTimestamp(log.timestamp)
                  )}
                </div>
                <div className="w-32 shrink-0 font-mono text-xs text-muted-foreground">
                  {ipSeen ? (
                    <span className="visual-text" data-text={log.ip_address} />
                  ) : (
                    log.ip_address
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty */}
      {!isLoading && !error && items.length === 0 && (
        <EmptyState
          icon={Shield}
          title="暂无审计日志"
          description="当前没有符合条件的审计日志记录。"
        />
      )}

      {/* Pagination */}
      {!isLoading && !error && total > 0 && (
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              共 {total} 条
            </span>
            <select
              aria-label="每页条数"
              value={String(currentPageSize)}
              onChange={(e) => updateFilter("page_size", Number(e.target.value))}
              className="flex h-7 w-28 rounded-xl border border-white/10 bg-white/5 px-3 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/30 hover:border-white/20 transition-all duration-200"
            >
              {PAGE_SIZE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-xs"
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage <= 1}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span className="sr-only">上一页</span>
            </Button>

            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (currentPage <= 3) {
                pageNum = i + 1;
              } else if (currentPage >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = currentPage - 2 + i;
              }
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === currentPage ? "default" : "outline"}
                  size="icon-xs"
                  onClick={() => goToPage(pageNum)}
                  className="text-xs"
                >
                  {pageNum}
                </Button>
              );
            })}

            <Button
              variant="outline"
              size="icon-xs"
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage >= totalPages}
            >
              <ChevronRight className="h-3.5 w-3.5" />
              <span className="sr-only">下一页</span>
            </Button>
          </div>
        </div>
      )}

      <style>{`
        .visual-text::before {
          content: attr(data-text);
        }
      `}</style>
    </motion.div>
  );
}
