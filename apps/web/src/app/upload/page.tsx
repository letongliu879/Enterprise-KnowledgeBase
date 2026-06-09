"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery, useMutation, useInfiniteQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileText,
  FileSpreadsheet,
  Presentation,
  AlertCircle,
  Archive,
  Ban,
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
  FileCheck,
  Trash2,
  RotateCcw,
  Database,
  TrendingUp,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EmptyState } from "@/components/empty-state";
import { isApiError, getErrorMessage } from "@/lib/api/errors";
import { toast } from "sonner";
import { staggerContainer, staggerItem } from "@/lib/animations";
import type { UploadStatus } from "@/lib/api/types";

const SUPPORTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/csv",
];

const TYPE_CONFIG: Record<
  string,
  { label: string; icon: typeof FileText; color: string }
> = {
  "application/pdf": {
    label: "PDF",
    icon: FileText,
    color: "text-red-400",
  },
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
    label: "DOCX",
    icon: FileText,
    color: "text-blue-400",
  },
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
    label: "PPTX",
    icon: Presentation,
    color: "text-orange-400",
  },
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
    label: "XLSX",
    icon: FileSpreadsheet,
    color: "text-emerald-400",
  },
  "text/csv": {
    label: "CSV",
    icon: FileSpreadsheet,
    color: "text-cyan-400",
  },
};

type FileStatus = UploadStatus | "queued";

const S_UPLOADING: FileStatus = "uploading";

interface FileItem {
  id: string;
  file: File;
  status: FileStatus;
  error?: string;
  uploadId?: string;
}

function getFileTypeConfig(file: File) {
  const config = TYPE_CONFIG[file.type];
  if (config) return config;
  if (file.name.endsWith(".pdf"))
    return { label: "PDF", icon: FileText, color: "text-red-400" };
  return { label: "FILE", icon: FileText, color: "text-muted-foreground" };
}

function getStatusConfig(status: FileStatus) {
  switch (status) {
    case "queued":
      return {
        icon: Clock,
        color: "text-slate-400",
        bgColor: "bg-slate-500/10",
        borderColor: "border-slate-500/20",
        label: "正在排队",
      };
    case "uploading":
      return {
        icon: Loader2,
        color: "text-primary",
        bgColor: "bg-primary/10",
        borderColor: "border-primary/20",
        label: "正在上传",
        animate: true,
      };
    case "ready":
      return {
        icon: Loader2,
        color: "text-blue-400",
        bgColor: "bg-blue-500/10",
        borderColor: "border-blue-500/20",
        label: "正在等待处理",
        animate: true,
      };
    case "uploaded":
      return {
        icon: CheckCircle2,
        color: "text-blue-400",
        bgColor: "bg-blue-500/10",
        borderColor: "border-blue-500/20",
        label: "已上传",
      };
    case "duplicate":
      return {
        icon: AlertCircle,
        color: "text-orange-400",
        bgColor: "bg-orange-500/10",
        borderColor: "border-orange-500/20",
        label: "重复文件",
      };
    case "parsing":
      return {
        icon: Loader2,
        color: "text-blue-400",
        bgColor: "bg-blue-500/10",
        borderColor: "border-blue-500/20",
        label: "正在解析",
        animate: true,
      };
    case "reviewing":
      return {
        icon: AlertCircle,
        color: "text-amber-400",
        bgColor: "bg-amber-500/10",
        borderColor: "border-amber-500/20",
        label: "正在等待复核",
      };
    case "approved":
    case "published":
      return {
        icon: ShieldCheck,
        color: "text-emerald-400",
        bgColor: "bg-emerald-500/10",
        borderColor: "border-emerald-500/20",
        label: status === "approved" ? "已批准" : "已发布",
      };
    case "indexing":
      return {
        icon: Loader2,
        color: "text-purple-400",
        bgColor: "bg-purple-500/10",
        borderColor: "border-purple-500/20",
        label: "正在构建索引",
        animate: true,
      };
    case "archived":
      return {
        icon: Archive,
        color: "text-slate-400",
        bgColor: "bg-slate-500/10",
        borderColor: "border-slate-500/20",
        label: "已归档",
      };
    case "retracted":
      return {
        icon: Ban,
        color: "text-orange-400",
        bgColor: "bg-orange-500/10",
        borderColor: "border-orange-500/20",
        label: "已撤回",
      };
    case "rejected":
      return {
        icon: XCircle,
        color: "text-red-400",
        bgColor: "bg-red-500/10",
        borderColor: "border-red-500/20",
        label: "已驳回",
      };
    case "failed":
      return {
        icon: AlertTriangle,
        color: "text-red-400",
        bgColor: "bg-red-500/10",
        borderColor: "border-red-500/20",
        label: "处理失败",
      };
  }
}

const MAX_CONCURRENT_UPLOADS = 3;

export default function UploadPage() {
  const { currentCollectionId, accessScope } = useAppStore();
  const [files, setFiles] = useState<FileItem[]>([]);
  const filesRef = useRef<FileItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadQueueRef = useRef<string[]>([]);
  const activeUploadsRef = useRef(0);

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  // Poll active file statuses (only when files are in progress).
  const hasActiveFiles = files.some((f) =>
    ["queued", "uploading", "ready", "uploaded", "parsing", "reviewing", "approved", "publishing", "indexing"].includes(f.status)
  );

  const { data: tasks } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => workbenchApi.listTasks({ sort_by: "created_at", sort_order: "desc" }),
    refetchInterval: hasActiveFiles ? 5000 : 30000,
  });

  useEffect(() => {
    if (!tasks?.items?.length) return;
    const taskMap = new Map(tasks.items.map((t) => [t.upload_id, t]));
    setFiles((prev) =>
      prev.map((f) => {
        if (!f.uploadId || f.status === "failed" || f.status === "rejected")
          return f;
        const task = taskMap.get(f.uploadId);
        if (!task) return f;
        const statusChanged = task.status !== f.status;
        if (!statusChanged) return f;
        return { ...f, status: task.status };
      })
    );
  }, [tasks]);

  // Recent tasks with infinite scroll.
  const {
    data: recentTasksData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: recentTasksLoading,
  } = useInfiniteQuery({
    queryKey: ["recent-tasks"],
    queryFn: ({ pageParam = 0 }) =>
      workbenchApi.listTasks({
        sort_by: "created_at",
        sort_order: "desc",
        offset: pageParam,
        limit: 20,
      }),
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((s, p) => s + p.items.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
    initialPageParam: 0,
  });
  const recentTasks = recentTasksData?.pages.flatMap((p) => p.items) ?? [];
  const sentinelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) fetchNextPage(); },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const createUpload = useMutation({
    mutationFn: async (item: FileItem) => {
      if (!currentCollectionId) throw new Error("No collection selected");
      const res = await workbenchApi.createUpload({
        collection_id: currentCollectionId,
        filename: item.file.name,
        mime_type: item.file.type || "application/octet-stream",
        size_bytes: item.file.size,
        access_scope_json: accessScope,
      });
      return res;
    },
    onSuccess: (data, item) => {
      const uploadId = String(data.upload_id || "");
      setFiles((prev) =>
        prev.map((f) =>
          f.id === item.id ? { ...f, uploadId, status: S_UPLOADING } : f
        )
      );
      uploadContent.mutate({ ...item, uploadId });
    },
    onError: (err, item) => {
      const msg = isApiError(err) ? err.message : getErrorMessage(err);
      setFiles((prev) =>
        prev.map((f) =>
          f.id === item.id ? { ...f, status: "failed", error: msg } : f
        )
      );
      activeUploadsRef.current = Math.max(0, activeUploadsRef.current - 1);
      processUploadQueue();
      toast.error(`创建上传会话失败: ${item.file.name}`);
    },
  });

  const uploadContent = useMutation({
    mutationFn: async (item: FileItem) => {
      if (!item.uploadId) throw new Error("No upload_id");
      const res = await workbenchApi.uploadFileContent(
        item.uploadId,
        item.file,
        accessScope
      );
      return res;
    },
    onSuccess: (_data, item) => {
      setFiles((prev) =>
        prev.map((f) =>
          f.id === item.id ? { ...f, status: S_UPLOADING } : f
        )
      );
      activeUploadsRef.current = Math.max(0, activeUploadsRef.current - 1);
      processUploadQueue();
      toast.success(`已上传: ${item.file.name}`);
    },
    onError: (err, item) => {
      const msg = isApiError(err) ? err.message : getErrorMessage(err);
      setFiles((prev) =>
        prev.map((f) =>
          f.id === item.id ? { ...f, status: "failed", error: msg } : f
        )
      );
      activeUploadsRef.current = Math.max(0, activeUploadsRef.current - 1);
      processUploadQueue();
      toast.error(`上传文件失败: ${item.file.name}`);
    },
  });

  const startUpload = (item: FileItem) => {
    activeUploadsRef.current += 1;
    setFiles((prev) =>
      prev.map((f) => (f.id === item.id ? { ...f, status: "uploading" } : f))
    );
    createUpload.mutate(item);
  };

  const processUploadQueue = () => {
    const activeCount = activeUploadsRef.current;
    if (activeCount >= MAX_CONCURRENT_UPLOADS) return;

    const slots = MAX_CONCURRENT_UPLOADS - activeCount;
    const queuedIds = uploadQueueRef.current.splice(0, slots);

    queuedIds.forEach((id) => {
      const item = filesRef.current.find((f) => f.id === id);
      if (item) startUpload(item);
    });
  };

  const enqueueUploads = (items: FileItem[]) => {
    filesRef.current = [...filesRef.current, ...items];
    setFiles((prev) => [...prev, ...items]);
    items.forEach((item) => uploadQueueRef.current.push(item.id));
    processUploadQueue();
  };

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (!currentCollectionId || !accessScope) {
        toast.error("请先选择知识库集合并配置权限范围");
        return;
      }
      const dropped = Array.from(e.dataTransfer.files);
      const valid = dropped.filter(
        (f) => SUPPORTED_TYPES.includes(f.type) || f.name.endsWith(".pdf")
      );
      const newItems: FileItem[] = valid.map((file) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        file,
        status: "queued",
      }));
      enqueueUploads(newItems);
    },
    [currentCollectionId, accessScope]
  );

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    if (!currentCollectionId || !accessScope) {
      toast.error("请先选择知识库集合并配置权限范围");
      return;
    }
    const selected = Array.from(e.target.files);
    const valid = selected.filter(
      (f) => SUPPORTED_TYPES.includes(f.type) || f.name.endsWith(".pdf")
    );
    const newItems: FileItem[] = valid.map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
      status: "queued",
    }));
    enqueueUploads(newItems);
    e.target.value = "";
  };

  const removeFile = (id: string) => {
    filesRef.current = filesRef.current.filter((f) => f.id !== id);
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const retryFile = (item: FileItem) => {
    const updated = {
      ...item,
      status: "queued" as FileStatus,
      error: undefined,
      uploadId: undefined,
    };
    filesRef.current = filesRef.current.map((f) =>
      f.id === item.id ? updated : f
    );
    setFiles((prev) => prev.map((f) => (f.id === item.id ? updated : f)));
    uploadQueueRef.current.push(item.id);
    processUploadQueue();
  };

  const stats = {
    total: files.length,
    active: files.filter((f) =>
      ["uploading", "parsing", "reviewing", "approved", "published"].includes(
        f.status
      )
    ).length,
    approved: files.filter(
      (f) => f.status === "approved" || f.status === "published"
    ).length,
    reviewing: files.filter((f) => f.status === "reviewing").length,
    failed: files.filter(
      (f) => f.status === "failed" || f.status === "rejected"
    ).length,
  };

  const canUpload = currentCollectionId && accessScope;

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div variants={staggerItem} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">批量入库</h1>
          <p className="text-sm text-muted-foreground mt-1">
            将文档批量上传至指定知识库集合，并附带权限范围治理。
          </p>
        </div>
        <Badge
          variant={canUpload ? "success" : "destructive"}
          className="h-7 px-3"
        >
          {canUpload ? (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
              就绪
            </>
          ) : (
            <>
              <AlertTriangle className="h-3.5 w-3.5 mr-1" />
              缺少集合或权限范围
            </>
          )}
        </Badge>
      </motion.div>

      {/* Alert */}
      <AnimatePresence>
        {!canUpload && (
          <motion.div
            variants={staggerItem}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                上传前必须在顶部选择知识库集合，并在设置中配置权限范围。
              </AlertDescription>
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Drop Zone */}
          <motion.div variants={staggerItem}>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          onClick={() => canUpload && inputRef.current?.click()}
          className={
            "relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 overflow-hidden " +
            (canUpload
              ? isDragging
                ? "border-primary bg-primary/5 animate-border-gradient cursor-pointer"
                : "border-border hover:border-primary/50 hover:bg-accent cursor-pointer"
              : "border-border opacity-50 cursor-not-allowed grayscale")
          }
        >
          {/* Background glow effect */}
          <div
            className={
              "absolute inset-0 bg-gradient-to-br from-primary/[0.05] to-transparent transition-opacity duration-300 " +
              (isDragging ? "opacity-100" : "opacity-0")
            }
          />

          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.pptx,.xlsx,.csv"
            className="hidden"
            onChange={onFileSelect}
          />

          <div className="relative">
            <div
              className={
                "inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4 transition-all duration-300 " +
                (isDragging
                  ? "bg-primary/10 shadow-glow"
                  : "bg-muted")
              }
            >
              <Upload
                className={
                  "h-8 w-8 transition-colors duration-300 " +
                  (isDragging ? "text-primary" : "text-muted-foreground")
                }
              />
            </div>
            <p className="text-sm font-medium text-foreground">
              拖拽文件至此，或点击选择
            </p>
            <p className="text-xs text-muted-foreground/60 mt-1.5">
              支持 PDF、DOCX、PPTX、XLSX、CSV 格式
            </p>
          </div>
        </div>
      </motion.div>

      {/* Batch Stats — Dashboard Metrics */}
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            variants={staggerItem}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                {
                  label: "总数",
                  value: stats.total,
                  icon: Database,
                  color: "text-foreground",
                  bgColor: "bg-white/[0.03]",
                },
                {
                  label: "处理中",
                  value: stats.active,
                  icon: TrendingUp,
                  color: "text-blue-400",
                  bgColor: "bg-blue-500/10",
                },
                {
                  label: "已入库",
                  value: stats.approved,
                  icon: ShieldCheck,
                  color: "text-emerald-400",
                  bgColor: "bg-emerald-500/10",
                },
                {
                  label: "待复核",
                  value: stats.reviewing,
                  icon: AlertCircle,
                  color: "text-amber-400",
                  bgColor: "bg-amber-500/10",
                },
                {
                  label: "失败",
                  value: stats.failed,
                  icon: AlertTriangle,
                  color: "text-red-400",
                  bgColor: "bg-red-500/10",
                },
              ].map((stat) => (
                <Card
                  key={stat.label}
                  className={cn(
                    "p-4 border-border",
                    stat.bgColor
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <stat.icon className={cn("h-4 w-4", stat.color)} />
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground/60">
                      {stat.label}
                    </span>
                  </div>
                  <p className={cn("text-2xl font-bold", stat.color)}>
                    {stat.value}
                  </p>
                </Card>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* File List */}
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            variants={staggerItem}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-3"
          >
            <h3 className="text-sm font-medium text-muted-foreground/80">
              当前上传 ({files.length})
            </h3>
            <div className="space-y-2">
              <AnimatePresence>
                {files.map((item, index) => {
                  const config = getStatusConfig(item.status);
                  const fileType = getFileTypeConfig(item.file);
                  const StatusIcon = config.icon;

                  return (
                    <motion.div
                      key={item.id}
                      layout
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 20 }}
                      transition={{ delay: index * 0.03 }}
                    >
                      <Card
                        interactive
                        className="relative overflow-hidden"
                      >
                        {/* Status color bar */}
                        <div
                          className={cn(
                            "absolute left-0 top-0 bottom-0 w-1 rounded-l-xl",
                            config.borderColor.replace("border-", "bg-")
                          )}
                        />

                        <CardContent className="p-3 pl-4">
                          <div className="flex items-center gap-3">
                            {/* File type icon */}
                            <div
                              className={cn(
                                "flex items-center justify-center w-10 h-10 rounded-xl shrink-0",
                                "bg-muted"
                              )}
                            >
                              <fileType.icon
                                className={cn("h-5 w-5", fileType.color)}
                              />
                            </div>

                            {/* File info */}
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">
                                {item.file.name}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {fileType.label} ·{" "}
                                {(item.file.size / 1024).toFixed(1)} KB
                              </p>
                              {item.error && (
                                <p className="text-xs text-red-500 mt-1">
                                  {item.error}
                                </p>
                              )}
                            </div>

                            {/* Status badge */}
                            <Badge
                              variant="outline"
                              className={cn(
                                "gap-1.5 shrink-0 border",
                                config.borderColor,
                                config.bgColor
                              )}
                            >
                              <StatusIcon
                                className={cn(
                                  "h-3.5 w-3.5",
                                  config.color,
                                  config.animate && "animate-spin"
                                )}
                              />
                              <span className={cn("text-xs", config.color)}>
                                {config.label}
                              </span>
                            </Badge>

                            {/* Actions */}
                            <div className="flex items-center gap-1 shrink-0">
                              {item.status === "failed" && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8 rounded-lg hover:bg-accent"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    retryFile(item);
                                  }}
                                  title="重试"
                                >
                                  <RotateCcw className="h-3.5 w-3.5 text-muted-foreground" />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 rounded-lg hover:bg-red-500/10 hover:text-red-400"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  removeFile(item.id);
                                }}
                                title="删除"
                              >
                                <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                              </Button>
                            </div>
                          </div>

                          {/* Progress bar for uploading */}
                          {(item.status === "uploading" ||
                            item.status === "parsing" ||
                            item.status === "indexing") && (
                            <div className="mt-2 h-1 rounded-full bg-white/[0.04] overflow-hidden">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-primary/60 to-primary animate-shimmer"
                                style={{ width: "60%" }}
                              />
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Recent Tasks — infinite scroll, newest first */}
      <motion.div variants={staggerItem} className="pt-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-muted-foreground">
            最近任务
          </h3>
          <span className="text-[11px] text-muted-foreground/60">
            按上传时间倒序
          </span>
        </div>

        {recentTasksLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-14 rounded-xl border border-border bg-muted animate-shimmer"
              />
            ))}
          </div>
        ) : recentTasks.length > 0 ? (
          <>
            <div className="space-y-1 max-h-[480px] overflow-y-auto pr-1">
              {recentTasks.map((task) => {
                const config = getStatusConfig(task.status as FileStatus);
                const StatusIcon = config.icon;
                return (
                  <div
                    key={String(task.upload_id)}
                    className="flex items-start gap-3 py-2 group"
                  >
                    <div className="relative shrink-0 mt-1">
                      <div
                        className={cn(
                          "w-2.5 h-2.5 rounded-full border-2",
                          config.borderColor,
                          config.bgColor
                        )}
                      />
                    </div>
                    <div className="flex-1 min-w-0 flex items-center gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {String(task.filename)}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {String(task.collection_id)} ·{" "}
                          {getStatusLabel(task.status as FileStatus)}
                        </p>
                      </div>
                      <Badge
                        variant="outline"
                        className={cn(
                          "gap-1 shrink-0 border",
                          config.borderColor,
                          config.bgColor
                        )}
                      >
                        <StatusIcon
                          className={cn(
                            "h-3 w-3",
                            config.color,
                            config.animate && "animate-spin"
                          )}
                        />
                        <span className={cn("text-[10px]", config.color)}>
                          {config.label}
                        </span>
                      </Badge>
                    </div>
                  </div>
                );
              })}
              {/* Sentinel for intersection observer */}
              <div ref={sentinelRef} className="h-4" />
              {isFetchingNextPage && (
                <div className="flex justify-center py-3">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              )}
              {!hasNextPage && recentTasks.length > 0 && (
                <p className="text-[11px] text-center text-muted-foreground/50 pt-2">
                  共 {recentTasksData?.pages[0]?.total ?? 0} 条记录
                </p>
              )}
            </div>
          </>
        ) : (
          <EmptyState
            icon={Upload}
            title="暂无任务"
            description="上传文件后将在此显示任务进度。"
          />
        )}
      </motion.div>
    </motion.div>
  );
}

function cn(...inputs: (string | undefined | false | null)[]) {
  return inputs.filter(Boolean).join(" ");
}

function getStatusLabel(status: FileStatus): string {
  const labels: Record<FileStatus, string> = {
    queued: "正在排队",
    uploading: "正在上传",
    ready: "正在等待处理",
    uploaded: "已上传",
    duplicate: "重复文件",
    parsing: "正在解析",
    reviewing: "正在等待复核",
    approved: "已批准",
    published: "已发布",
    indexing: "正在构建索引",
    archived: "已归档",
    retracted: "已撤回",
    rejected: "已驳回",
    failed: "处理失败",
  };
  return labels[status];
}
