"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Archive,
  ChevronRight,
  Database,
  FileSpreadsheet,
  FileText,
  Filter,
  Layers,
  Presentation,
  RotateCcw,
  Search,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { workbenchApi } from "@/lib/api/client";
import type { BatchDocumentActionResult } from "@/lib/api/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { BackendGap } from "@/components/backend-gap";
import { isBackendGap, isApiError, getErrorMessage } from "@/lib/api/errors";
import { normalizeStatus } from "@/lib/status";
import { staggerContainer, staggerItem } from "@/lib/animations";

type BatchAction = "archive" | "retract" | "reindex";

function getDocIcon(filename?: string | null) {
  if (!filename) {
    return {
      icon: FileText,
      color: "text-muted-foreground",
      bg: "bg-white/[0.03]",
      type: "unknown",
    };
  }

  const ext = filename.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "pdf":
      return { icon: FileText, color: "text-red-400", bg: "bg-red-500/10", type: "pdf" };
    case "doc":
    case "docx":
      return { icon: FileText, color: "text-blue-400", bg: "bg-blue-500/10", type: "doc" };
    case "ppt":
    case "pptx":
      return { icon: Presentation, color: "text-orange-400", bg: "bg-orange-500/10", type: "ppt" };
    case "xls":
    case "xlsx":
    case "csv":
      return { icon: FileSpreadsheet, color: "text-emerald-400", bg: "bg-emerald-500/10", type: "sheet" };
    default:
      return {
        icon: FileText,
        color: "text-muted-foreground",
        bg: "bg-white/[0.03]",
        type: ext || "unknown",
      };
  }
}

function getStateConfig(state?: string | null) {
  const normalized = normalizeStatus(state);
  switch (normalized) {
    case "active":
      return {
        label: "Active",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
        border: "border-emerald-500/20",
      };
    case "pending":
      return {
        label: "Pending",
        color: "text-amber-400",
        bg: "bg-amber-500/10",
        border: "border-amber-500/20",
      };
    case "archived":
      return {
        label: "Archived",
        color: "text-slate-400",
        bg: "bg-slate-500/10",
        border: "border-slate-500/20",
      };
    default:
      return {
        label: state || "Unknown",
        color: "text-muted-foreground",
        bg: "bg-white/[0.03]",
        border: "border-white/10",
      };
  }
}

function formatRelativeTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("zh-CN");
}

export default function DocumentsPage() {
  const queryClient = useQueryClient();
  const [collectionFilter, setCollectionFilter] = useState("ALL");
  const [stateFilter, setStateFilter] = useState("ALL");
  const [reviewFilter, setReviewFilter] = useState("ALL");
  const [fileTypeFilter, setFileTypeFilter] = useState("ALL");
  const [staleFilter, setStaleFilter] = useState("ALL");
  const [indexFilter, setIndexFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [batchAction, setBatchAction] = useState<BatchAction | null>(null);
  const [batchReason, setBatchReason] = useState("");
  const [indexProfileId, setIndexProfileId] = useState("ragflow");
  const [lastBatchResult, setLastBatchResult] = useState<BatchDocumentActionResult | null>(null);

  const { data: me } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";
  const canManageLifecycle = Boolean(
    me?.roles?.includes("knowledge_admin") || me?.roles?.includes("platform_admin")
  );

  const { data: collectionResponse, isLoading: collectionsLoading } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["documents"],
    queryFn: () =>
      workbenchApi.listDocuments({
        limit: 200,
        order_by: "projection_updated_at",
        order_dir: "desc",
      }),
  });

  const collections = collectionResponse?.items ?? [];
  const normalizedSearchQuery = searchQuery.trim().toLowerCase();

  const filteredDocuments = useMemo(() => {
    const documentItems = data?.items ?? [];
    return documentItems.filter((doc) => {
      const fileInfo = getDocIcon(doc.filename);
      const matchesSearch =
        !normalizedSearchQuery ||
        String(doc.filename || "").toLowerCase().includes(normalizedSearchQuery) ||
        String(doc.doc_id || "").toLowerCase().includes(normalizedSearchQuery);
      const matchesCollection =
        collectionFilter === "ALL" ||
        String(doc.collection_id || "") === collectionFilter;
      const matchesState =
        stateFilter === "ALL" ||
        normalizeStatus(doc.document_state) === normalizeStatus(stateFilter);
      const matchesReview =
        reviewFilter === "ALL" ||
        normalizeStatus(doc.ticket_status) === normalizeStatus(reviewFilter);
      const matchesFileType =
        fileTypeFilter === "ALL" || fileInfo.type === fileTypeFilter;
      const matchesStale =
        staleFilter === "ALL" ||
        (staleFilter === "STALE" ? Boolean(doc.is_stale) : !doc.is_stale);
      const matchesIndex =
        indexFilter === "ALL" ||
        (indexFilter === "INDEXED" ? Boolean(doc.has_active_index) : !doc.has_active_index);

      return (
        matchesSearch &&
        matchesCollection &&
        matchesState &&
        matchesReview &&
        matchesFileType &&
        matchesStale &&
        matchesIndex
      );
    });
  }, [
    collectionFilter,
    data?.items,
    fileTypeFilter,
    indexFilter,
    normalizedSearchQuery,
    reviewFilter,
    staleFilter,
    stateFilter,
  ]);

  const allVisibleSelected =
    filteredDocuments.length > 0 &&
    filteredDocuments.every((doc) => selectedDocIds.has(doc.doc_id));

  const toggleSelection = (docId: string) => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  };

  const toggleSelectAllVisible = () => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) {
        filteredDocuments.forEach((doc) => next.delete(doc.doc_id));
      } else {
        filteredDocuments.forEach((doc) => next.add(doc.doc_id));
      }
      return next;
    });
  };

  const batchMutation = useMutation({
    mutationFn: async () => {
      const doc_ids = Array.from(selectedDocIds);
      if (batchAction === "archive") {
        return workbenchApi.batchArchiveDocuments({ doc_ids, reason: batchReason });
      }
      if (batchAction === "retract") {
        return workbenchApi.batchRetractDocuments({ doc_ids, reason: batchReason });
      }
      return workbenchApi.batchReindexDocuments({
        doc_ids,
        reason: batchReason,
        index_profile_id: indexProfileId || undefined,
      });
    },
    onSuccess: async (result) => {
      setLastBatchResult(result);
      setBatchAction(null);
      setBatchReason("");
      setSelectedDocIds(new Set());
      toast.success(`Batch completed: ${result.succeeded}/${result.total} succeeded`);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (mutationError) => {
      toast.error(isApiError(mutationError) ? mutationError.message : getErrorMessage(mutationError));
    },
  });

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      <motion.div variants={staggerItem} className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Document Library</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage document health, review linkage, index status, and lifecycle operations.
          </p>
        </div>
        {canManageLifecycle ? (
          <Badge variant="outline" className="h-7 px-3">
            Admin lifecycle enabled
          </Badge>
        ) : null}
      </motion.div>

      <motion.div variants={staggerItem} className="flex flex-wrap items-center gap-2">
        <div className="glass flex items-center gap-2 rounded-full px-1 py-1">
          <Search className="ml-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search by filename or doc id..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="h-7 w-56 border-0 bg-transparent px-0 text-sm focus-visible:ring-0 focus-visible:shadow-none"
          />
        </div>

        <Select
          value={collectionFilter}
          onValueChange={(value) => setCollectionFilter(value ?? "ALL")}
          disabled={collectionsLoading}
        >
          <SelectTrigger className="w-48 h-8 glass rounded-full border-white/10 text-xs">
            <Database className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="Collection" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">All collections</SelectItem>
            {collections.map((collection) => (
              <SelectItem key={collection.collection_id} value={collection.collection_id}>
                {collection.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={stateFilter} onValueChange={(value) => setStateFilter(value ?? "ALL")}>
          <SelectTrigger className="w-36 h-8 glass rounded-full border-white/10 text-xs">
            <Filter className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="State" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">All states</SelectItem>
            <SelectItem value="ACTIVE">Active</SelectItem>
            <SelectItem value="PENDING">Pending</SelectItem>
            <SelectItem value="ARCHIVED">Archived</SelectItem>
          </SelectContent>
        </Select>

        <Select value={reviewFilter} onValueChange={(value) => setReviewFilter(value ?? "ALL")}>
          <SelectTrigger className="w-36 h-8 glass rounded-full border-white/10 text-xs">
            <ShieldAlert className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="Review" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">All review</SelectItem>
            <SelectItem value="PENDING">Pending</SelectItem>
            <SelectItem value="APPROVED">Approved</SelectItem>
            <SelectItem value="REJECTED">Rejected</SelectItem>
          </SelectContent>
        </Select>

        <Select value={fileTypeFilter} onValueChange={(value) => setFileTypeFilter(value ?? "ALL")}>
          <SelectTrigger className="w-36 h-8 glass rounded-full border-white/10 text-xs">
            <FileText className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">All types</SelectItem>
            <SelectItem value="pdf">PDF</SelectItem>
            <SelectItem value="doc">Document</SelectItem>
            <SelectItem value="ppt">Presentation</SelectItem>
            <SelectItem value="sheet">Spreadsheet</SelectItem>
          </SelectContent>
        </Select>

        <Select value={staleFilter} onValueChange={(value) => setStaleFilter(value ?? "ALL")}>
          <SelectTrigger className="w-32 h-8 glass rounded-full border-white/10 text-xs">
            <SelectValue placeholder="Stale" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">All freshness</SelectItem>
            <SelectItem value="STALE">Stale only</SelectItem>
            <SelectItem value="FRESH">Fresh only</SelectItem>
          </SelectContent>
        </Select>

        <Select value={indexFilter} onValueChange={(value) => setIndexFilter(value ?? "ALL")}>
          <SelectTrigger className="w-36 h-8 glass rounded-full border-white/10 text-xs">
            <Layers className="mr-1 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="Index" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">All index</SelectItem>
            <SelectItem value="INDEXED">Indexed</SelectItem>
            <SelectItem value="NOT_INDEXED">Not indexed</SelectItem>
          </SelectContent>
        </Select>

        <span className="ml-auto text-xs text-muted-foreground/50">
          {filteredDocuments.length} visible
        </span>
      </motion.div>

      {canManageLifecycle && selectedDocIds.size > 0 ? (
        <motion.div variants={staggerItem}>
          <Card className="rounded-2xl border-dashed">
            <CardContent className="flex flex-wrap items-center gap-3 p-4">
              <Badge variant="secondary">{selectedDocIds.size} selected</Badge>
              <Button variant="outline" size="sm" onClick={() => setBatchAction("archive")}>
                <Archive className="mr-1 h-3.5 w-3.5" />
                Archive
              </Button>
              <Button variant="destructive" size="sm" onClick={() => setBatchAction("retract")}>
                <XCircle className="mr-1 h-3.5 w-3.5" />
                Retract
              </Button>
              <Button size="sm" onClick={() => setBatchAction("reindex")}>
                <RotateCcw className="mr-1 h-3.5 w-3.5" />
                Reindex
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto"
                onClick={() => setSelectedDocIds(new Set())}
              >
                Clear selection
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      ) : null}

      {lastBatchResult ? (
        <motion.div variants={staggerItem}>
          <Card className="rounded-2xl">
            <CardContent className="space-y-3 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">Total {lastBatchResult.total}</Badge>
                <Badge variant="secondary">Succeeded {lastBatchResult.succeeded}</Badge>
                <Badge variant={lastBatchResult.failed > 0 ? "destructive" : "outline"}>
                  Failed {lastBatchResult.failed}
                </Badge>
              </div>
              <div className="space-y-2">
                {lastBatchResult.items.slice(0, 8).map((item) => (
                  <div
                    key={`${item.doc_id}:${item.error_code || item.new_state || "ok"}`}
                    className="flex flex-wrap items-center gap-2 rounded-xl border bg-muted/10 p-3 text-sm"
                  >
                    <span className="font-mono">{item.doc_id}</span>
                    <Badge variant={item.success ? "secondary" : "destructive"}>
                      {item.success ? item.new_state || "ok" : item.error_code || "ERROR"}
                    </Badge>
                    {!item.success && item.error_message ? (
                      <span className="text-muted-foreground">{item.error_message}</span>
                    ) : null}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      ) : null}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-[96px] rounded-xl" />
          ))}
        </div>
      ) : null}

      {error &&
        (isBackendGap(error) ? (
          <BackendGap feature="Document Library" endpoint={error.endpoint} />
        ) : (
          <div className="glass rounded-xl border border-red-500/20 p-4 text-sm text-red-400">
            {isApiError(error) ? error.message : getErrorMessage(error)}
          </div>
        ))}

      {!isLoading && !error && filteredDocuments.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No documents"
          description="No documents match the current filters."
        />
      ) : null}

      {!isLoading && !error && filteredDocuments.length > 0 ? (
        <div className="space-y-2">
          <div className="flex items-center gap-3 rounded-xl border bg-muted/10 px-4 py-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={allVisibleSelected}
              onChange={toggleSelectAllVisible}
              disabled={!canManageLifecycle}
            />
            <span>Select visible</span>
          </div>
          {filteredDocuments.map((doc, index) => {
            const iconConfig = getDocIcon(doc.filename);
            const stateConfig = getStateConfig(doc.document_state);
            const Icon = iconConfig.icon;
            const completeness =
              doc.has_source_file && doc.has_parse_snapshot ? "Complete" : "Partial";

            return (
              <motion.div
                key={doc.doc_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.03 }}
              >
                <Card interactive className="relative overflow-hidden">
                  <CardContent className="flex items-center gap-4 p-4">
                    <input
                      type="checkbox"
                      checked={selectedDocIds.has(doc.doc_id)}
                      disabled={!canManageLifecycle}
                      onChange={() => toggleSelection(doc.doc_id)}
                    />

                    <div
                      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${iconConfig.bg}`}
                    >
                      <Icon className={`h-5 w-5 ${iconConfig.color}`} />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Link href={`/documents/${doc.doc_id}`} className="truncate text-sm font-medium hover:underline">
                          {doc.filename || doc.doc_id}
                        </Link>
                        {doc.ticket_status ? (
                          <Badge variant="secondary" className="h-5 text-[10px]">
                            Review {doc.ticket_status}
                          </Badge>
                        ) : null}
                        {doc.has_active_index ? (
                          <Badge variant="outline" className="h-5 text-[10px]">
                            Indexed
                          </Badge>
                        ) : null}
                      </div>

                      <div className="mt-1.5 flex flex-wrap items-center gap-3">
                        <Badge variant="outline" className="h-5 border-white/10 text-[10px]">
                          {doc.collection_id}
                        </Badge>
                        <span className="text-[11px] text-muted-foreground/60">
                          {doc.chunk_count} chunks
                        </span>
                        <span className="text-[11px] text-muted-foreground/60">
                          {doc.page_count || 0} pages
                        </span>
                        <span className="text-[11px] text-muted-foreground/60">
                          {completeness}
                        </span>
                        <span className="text-[11px] text-muted-foreground/60">
                          Updated {formatRelativeTime(doc.latest_updated_at || doc.updated_at)}
                        </span>
                      </div>

                      {doc.degraded_reason ? (
                        <p className="mt-1 text-xs text-amber-500">
                          {doc.degraded_reason}
                        </p>
                      ) : null}
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      <Badge
                        variant="outline"
                        className={`h-6 border text-[10px] ${stateConfig.border} ${stateConfig.bg}`}
                      >
                        <span className={stateConfig.color}>{stateConfig.label}</span>
                      </Badge>
                      {doc.is_stale ? (
                        <Badge variant="destructive" className="h-5 text-[10px]">
                          STALE
                        </Badge>
                      ) : null}
                      <Link href={`/documents/${doc.doc_id}`}>
                        <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg">
                          <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                        </Button>
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      ) : null}

      <Dialog open={batchAction !== null} onOpenChange={(open) => !open && setBatchAction(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {batchAction === "archive"
                ? "Archive selected documents"
                : batchAction === "retract"
                ? "Retract selected documents"
                : "Reindex selected documents"}
            </DialogTitle>
            <DialogDescription>
              Actions are executed one document at a time and will return per-item results.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Textarea
              placeholder="Reason"
              value={batchReason}
              onChange={(event) => setBatchReason(event.target.value)}
              className="min-h-24"
            />
            {batchAction === "reindex" ? (
              <Input
                value={indexProfileId}
                onChange={(event) => setIndexProfileId(event.target.value)}
                placeholder="Index profile id"
              />
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setBatchAction(null)} disabled={batchMutation.isPending}>
              Cancel
            </Button>
            <Button
              onClick={() => batchMutation.mutate()}
              disabled={batchMutation.isPending}
              variant={batchAction === "retract" ? "destructive" : "default"}
            >
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
