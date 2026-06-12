"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Clock,
  Database,
  FileText,
  FileSpreadsheet,
  Presentation,
  RotateCcw,
  Search,
  Trash2,
  AlertTriangle,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { workbenchApi } from "@/lib/api/client";
import type { TrashItem } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { BackendGap } from "@/components/backend-gap";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { isBackendGap, isApiError } from "@/lib/api/errors";
import { staggerContainer, staggerItem } from "@/lib/animations";
import { SortDropdown } from "@/components/sort-dropdown";

const SORT_OPTIONS = [
  { value: "deleted_at", label: "删除时间" },
  { value: "filename", label: "文件名" },
  { value: "auto_purge_at", label: "自动清理时间" },
];

function formatRelativeTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
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

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function getDocIcon(filename?: string | null) {
  if (!filename) return { icon: FileText, color: "text-muted-foreground", bg: "bg-white/[0.03]" };
  const ext = filename.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "pdf":
      return { icon: FileText, color: "text-red-400", bg: "bg-red-500/10" };
    case "doc":
    case "docx":
      return { icon: FileText, color: "text-blue-400", bg: "bg-blue-500/10" };
    case "ppt":
    case "pptx":
      return { icon: Presentation, color: "text-orange-400", bg: "bg-orange-500/10" };
    case "xls":
    case "xlsx":
    case "csv":
      return { icon: FileSpreadsheet, color: "text-emerald-400", bg: "bg-emerald-500/10" };
    default:
      return { icon: FileText, color: "text-muted-foreground", bg: "bg-white/[0.03]" };
  }
}

function daysUntil(dateString: string): number {
  const ms = new Date(dateString).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86400000));
}

export default function TrashPage() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("deleted_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [actionItem, setActionItem] = useState<TrashItem | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["trash"],
    queryFn: () => workbenchApi.listTrashItems(),
  });

  const restore = useMutation({
    mutationFn: (docId: string) => workbenchApi.restoreDocument(docId),
    onSuccess: async () => {
      toast.success("文档已恢复");
      setRestoreDialogOpen(false);
      setActionItem(null);
      await queryClient.invalidateQueries({ queryKey: ["trash"] });
      await queryClient.invalidateQueries({ queryKey: ["workbench-documents"] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "恢复失败");
    },
  });

  const remove = useMutation({
    mutationFn: (docId: string) => workbenchApi.permanentlyDeleteDocument(docId),
    onSuccess: async () => {
      toast.success("文档已永久删除");
      setDeleteDialogOpen(false);
      setActionItem(null);
      await queryClient.invalidateQueries({ queryKey: ["trash"] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "删除失败");
    },
  });

  const items = useMemo(() => data?.items ?? [], [data]);

  const filtered = useMemo(() => {
    let result = [...items];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (item) =>
          (item.filename ?? "").toLowerCase().includes(q) ||
          item.doc_id.toLowerCase().includes(q) ||
          item.collection_id.toLowerCase().includes(q)
      );
    }
    result.sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case "filename":
          comparison = (a.filename ?? "").localeCompare(b.filename ?? "");
          break;
        case "auto_purge_at":
          comparison = new Date(a.auto_purge_at).getTime() - new Date(b.auto_purge_at).getTime();
          break;
        case "deleted_at":
        default:
          comparison = new Date(a.deleted_at).getTime() - new Date(b.deleted_at).getTime();
          break;
      }
      return sortDir === "asc" ? comparison : -comparison;
    });
    return result;
  }, [items, searchQuery, sortBy, sortDir]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === filtered.length && filtered.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((item) => item.doc_id)));
    }
  };

  const handleBatchRestore = () => {
    Promise.all(Array.from(selectedIds).map((id) => workbenchApi.restoreDocument(id)))
      .then(async () => {
        toast.success(`已恢复 ${selectedIds.size} 个文档`);
        setSelectedIds(new Set());
        await queryClient.invalidateQueries({ queryKey: ["trash"] });
        await queryClient.invalidateQueries({ queryKey: ["workbench-documents"] });
      })
      .catch((err) => {
        toast.error(isApiError(err) ? err.message : "批量恢复失败");
      });
  };

  const handleBatchDelete = () => {
    Promise.all(Array.from(selectedIds).map((id) => workbenchApi.permanentlyDeleteDocument(id)))
      .then(async () => {
        toast.success(`已永久删除 ${selectedIds.size} 个文档`);
        setSelectedIds(new Set());
        await queryClient.invalidateQueries({ queryKey: ["trash"] });
      })
      .catch((err) => {
        toast.error(isApiError(err) ? err.message : "批量删除失败");
      });
  };

  if (error) {
    if (isBackendGap(error)) {
      return <BackendGap feature="回收站" endpoint={error.endpoint} />;
    }
    return (
      <EmptyState
        icon={AlertTriangle}
        title="加载失败"
        description={isApiError(error) ? error.message : String(error)}
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border bg-card/92 p-5 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">回收站</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              已删除文档将保留 30 天，之后自动永久清理
            </p>
          </div>
          {selectedIds.size > 0 ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={handleBatchRestore}>
                <RotateCcw className="mr-2 h-4 w-4" />
                恢复 {selectedIds.size} 项
              </Button>
              <Button variant="destructive" onClick={handleBatchDelete}>
                <Trash2 className="mr-2 h-4 w-4" />
                永久删除 {selectedIds.size} 项
              </Button>
            </div>
          ) : null}
        </div>
      </section>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索文件名、文档 ID、集合 ID"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <SortDropdown
          options={SORT_OPTIONS}
          value={sortBy}
          direction={sortDir}
          onChange={setSortBy}
          onDirectionChange={setSortDir}
        />
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-2xl" data-testid="trash-skeleton" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Trash2}
          title="回收站为空"
          description="没有已删除的文档，删除的文档将在这里显示"
        />
      ) : (
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
          className="space-y-3"
        >
          <Card className="rounded-2xl border-dashed bg-muted/20">
            <CardContent className="flex items-center gap-3 py-3">
              <Checkbox
                checked={selectedIds.size === filtered.length && filtered.length > 0}
                onCheckedChange={toggleAll}
              />
              <span className="text-sm text-muted-foreground">
                已选择 {selectedIds.size} / {filtered.length} 项
              </span>
            </CardContent>
          </Card>
          {filtered.map((item) => {
            const { icon: Icon, color, bg } = getDocIcon(item.filename);
            const remainingDays = daysUntil(item.auto_purge_at);
            return (
              <motion.div key={item.doc_id} variants={staggerItem}>
                <Card className="rounded-2xl transition-shadow hover:shadow-sm">
                  <CardContent className="flex items-center gap-4 py-4">
                    <Checkbox
                      checked={selectedIds.has(item.doc_id)}
                      onCheckedChange={() => toggleSelect(item.doc_id)}
                    />
                    <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${bg}`}>
                      <Icon className={`h-5 w-5 ${color}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {item.filename || item.doc_id}
                      </p>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-mono">{item.doc_id}</span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Database className="h-3 w-3" />
                          {item.collection_id}
                        </span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          删除于 {formatRelativeTime(item.deleted_at)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant={remainingDays <= 7 ? "destructive" : "outline"} className="text-[10px]">
                        {remainingDays} 天后清理
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setActionItem(item);
                          setRestoreDialogOpen(true);
                        }}
                      >
                        <RotateCcw className="mr-1 h-3.5 w-3.5" />
                        恢复
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive hover:bg-destructive/10"
                        onClick={() => {
                          setActionItem(item);
                          setDeleteDialogOpen(true);
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </motion.div>
      )}

      <Dialog open={restoreDialogOpen} onOpenChange={setRestoreDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>恢复文档</DialogTitle>
            <DialogDescription>
              确认恢复「{actionItem?.filename || actionItem?.doc_id}」到原集合？
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRestoreDialogOpen(false)}>取消</Button>
            <Button
              onClick={() => actionItem && restore.mutate(actionItem.doc_id)}
              disabled={restore.isPending}
            >
              恢复
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              永久删除文档
            </DialogTitle>
            <DialogDescription>
              此操作不可撤销。确认永久删除「{actionItem?.filename || actionItem?.doc_id}」？
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>取消</Button>
            <Button
              variant="destructive"
              onClick={() => actionItem && remove.mutate(actionItem.doc_id)}
              disabled={remove.isPending}
            >
              永久删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
