"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileText,
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
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EmptyState } from "@/components/empty-state";
import { isApiError, getErrorMessage } from "@/lib/api/errors";
import { toast } from "sonner";
import type { UploadStatus } from "@/lib/api/types";

const SUPPORTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/csv",
];

const TYPE_LABELS: Record<string, string> = {
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
  "text/csv": "CSV",
};

type FileStatus = UploadStatus | "queued";

const S_UPLOADING: FileStatus = "uploading";

interface FileItem {
  id: string;
  file: File;
  status: FileStatus;
  progress: number;
  error?: string;
  uploadId?: string;
}

function getStatusIcon(status: FileStatus) {
  switch (status) {
    case "queued":
      return <Clock className="h-4 w-4 text-muted-foreground" />;
    case "uploading":
      return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
    case "uploaded":
      return <CheckCircle2 className="h-4 w-4 text-blue-500" />;
    case "duplicate":
      return <AlertCircle className="h-4 w-4 text-orange-500" />;
    case "parsing":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case "reviewing":
      return <AlertCircle className="h-4 w-4 text-amber-500" />;
    case "approved":
    case "published":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
    case "indexing":
      return <Loader2 className="h-4 w-4 animate-spin text-purple-500" />;
    case "archived":
      return <Archive className="h-4 w-4 text-slate-500" />;
    case "retracted":
      return <Ban className="h-4 w-4 text-orange-500" />;
    case "rejected":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "failed":
      return <AlertCircle className="h-4 w-4 text-red-500" />;
  }
}

function getStatusLabel(status: FileStatus) {
  const labels: Record<FileStatus, string> = {
    queued: "待上传",
    uploading: "上传中",
    uploaded: "已上传",
    duplicate: "重复文件",
    parsing: "解析中",
    reviewing: "待复核",
    approved: "已批准",
    published: "已发布",
    indexing: "索引构建中",
    archived: "已归档",
    retracted: "已撤回",
    rejected: "已驳回",
    failed: "失败",
  };
  return labels[status];
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

  // Keep ref in sync with state to avoid closure staleness in queue processing
  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => workbenchApi.listTasks(),
    refetchInterval: 5000,
  });

  // Reconcile local file status and progress with backend task state
  useEffect(() => {
    if (!tasks?.items?.length) return;
    const taskMap = new Map(tasks.items.map((t) => [t.upload_id, t]));
    setFiles((prev) =>
      prev.map((f) => {
        if (!f.uploadId || f.status === "failed" || f.status === "rejected") return f;
        const task = taskMap.get(f.uploadId);
        if (!task) return f;
        const statusChanged = task.status !== f.status;
        const progressChanged = task.progress_pct !== f.progress;
        if (!statusChanged && !progressChanged) return f;
        return { ...f, status: task.status, progress: task.progress_pct };
      })
    );
  }, [tasks]);

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
          f.id === item.id
            ? { ...f, uploadId, status: S_UPLOADING, progress: 50 }
            : f
        )
      );
      // Chain: send actual file bytes
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
      const res = await workbenchApi.uploadFileContent(item.uploadId, item.file, accessScope);
      return res;
    },
    onSuccess: (_data, item) => {
      // Bytes sent; real status transitions come from backend task polling
      setFiles((prev) =>
        prev.map((f) =>
          f.id === item.id
            ? { ...f, status: S_UPLOADING, progress: 100 }
            : f
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
    // Update ref immediately so processUploadQueue sees the new items
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
        progress: 0,
      }));
      enqueueUploads(newItems);
    },
    [currentCollectionId, accessScope, enqueueUploads]
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
      progress: 0,
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
      progress: 0,
      error: undefined,
      uploadId: undefined,
    };
    // Sync ref before setFiles so processUploadQueue sees the reset status
    filesRef.current = filesRef.current.map((f) => (f.id === item.id ? updated : f));
    setFiles((prev) => prev.map((f) => (f.id === item.id ? updated : f)));
    uploadQueueRef.current.push(item.id);
    processUploadQueue();
  };

  const stats = {
    total: files.length,
    active: files.filter((f) =>
      ["uploading", "parsing", "reviewing", "approved", "published"].includes(f.status)
    ).length,
    approved: files.filter((f) => f.status === "approved" || f.status === "published").length,
    reviewing: files.filter((f) => f.status === "reviewing").length,
    failed: files.filter((f) => f.status === "failed" || f.status === "rejected").length,
  };

  const canUpload = currentCollectionId && accessScope;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">批量入库</h1>
          <p className="text-sm text-muted-foreground mt-1">
            将文档批量上传至指定知识库集合，并附带权限范围治理。
          </p>
        </div>
        <Badge variant={canUpload ? "default" : "destructive"}>
          {canUpload ? "就绪" : "缺少集合或权限范围"}
        </Badge>
      </div>

      {!canUpload && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            上传前必须在顶部选择知识库集合，并在设置中配置权限范围。
          </AlertDescription>
        </Alert>
      )}

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => canUpload && inputRef.current?.click()}
        className={
          "border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer " +
          (isDragging
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/20 hover:border-muted-foreground/40")
        }
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.pptx,.xlsx,.csv"
          className="hidden"
          onChange={onFileSelect}
        />
        <Upload className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
        <p className="text-sm font-medium">
          拖拽文件至此，或点击选择
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          支持 PDF、DOCX、PPTX、XLSX、CSV 格式
        </p>
      </div>

      {/* Batch stats */}
      {files.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">批次汇总</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-5 gap-4">
              {[
                { label: "总数", value: stats.total, color: "" },
                { label: "处理中", value: stats.active, color: "text-blue-600" },
                { label: "已入库", value: stats.approved, color: "text-emerald-600" },
                { label: "待复核", value: stats.reviewing, color: "text-amber-600" },
                { label: "失败", value: stats.failed, color: "text-red-600" },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* File list */}
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-2"
          >
            <h3 className="text-sm font-medium">文件</h3>
            {files.map((item) => (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="flex items-center gap-3 rounded-lg border p-3 bg-card"
              >
                <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {TYPE_LABELS[item.file.type] || item.file.name.split(".").pop()?.toUpperCase()}{" "}
                    · {(item.file.size / 1024).toFixed(1)} KB
                  </p>
                  {item.status === "uploading" && (
                    <Progress value={item.progress} className="h-1 mt-2" />
                  )}
                  {item.error && (
                    <p className="text-xs text-red-500 mt-1">{item.error}</p>
                  )}
                </div>
                <Badge variant="outline" className="gap-1 shrink-0">
                  {getStatusIcon(item.status)}
                  <span className="text-xs">{getStatusLabel(item.status)}</span>
                </Badge>
                {item.status === "failed" && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0"
                    onClick={() => retryFile(item)}
                    title="重试"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  onClick={() => removeFile(item.id)}
                  title="删除"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Recent tasks from backend */}
      <div className="pt-4">
        <h3 className="text-sm font-medium mb-3">最近任务</h3>
        {tasksLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-12 rounded-lg border bg-card animate-pulse" />
            ))}
          </div>
        ) : tasks && tasks.items.length > 0 ? (
          <div className="space-y-2">
            {tasks.items.slice(0, 5).map((task) => (
              <div
                key={String(task.upload_id)}
                className="flex items-center gap-3 rounded-lg border p-3 bg-card hover:bg-accent/50 transition-colors"
              >
                <FileCheck className="h-4 w-4 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{String(task.filename)}</p>
                  <p className="text-xs text-muted-foreground">
                    {String(task.collection_id)} · {String(task.status)}
                  </p>
                </div>
                <Badge variant="outline">{String(task.status)}</Badge>
                <Progress
                  value={Number(task.progress_pct || 0)}
                  className="w-24 h-1.5"
                />
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Upload}
            title="暂无任务"
            description="上传文件后将在此显示任务进度。"
          />
        )}
      </div>
    </div>
  );
}
