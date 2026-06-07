"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  FileText,
  Search,
  ChevronRight,
  Database,
  Filter,
  FileSpreadsheet,
  Presentation,
  Archive,
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
import { isBackendGap, isApiError } from "@/lib/api/errors";
import { staggerContainer, staggerItem } from "@/lib/animations";

function getDocIcon(filename?: string | null) {
  if (!filename) return { icon: FileText, color: "text-muted-foreground", bg: "bg-white/[0.03]" };
  const ext = filename.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "pdf":
      return { icon: FileText, color: "text-red-400", bg: "bg-red-500/10" };
    case "docx":
    case "doc":
      return { icon: FileText, color: "text-blue-400", bg: "bg-blue-500/10" };
    case "pptx":
    case "ppt":
      return {
        icon: Presentation,
        color: "text-orange-400",
        bg: "bg-orange-500/10",
      };
    case "xlsx":
    case "xls":
    case "csv":
      return {
        icon: FileSpreadsheet,
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
      };
    default:
      return {
        icon: FileText,
        color: "text-muted-foreground",
        bg: "bg-white/[0.03]",
      };
  }
}

function getStateConfig(state?: string | null) {
  switch (state) {
    case "ACTIVE":
      return {
        variant: "success" as const,
        label: "已激活",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
        border: "border-emerald-500/20",
      };
    case "PENDING":
      return {
        variant: "warning" as const,
        label: "待处理",
        color: "text-amber-400",
        bg: "bg-amber-500/10",
        border: "border-amber-500/20",
      };
    case "ARCHIVED":
      return {
        variant: "secondary" as const,
        label: "已归档",
        color: "text-slate-400",
        bg: "bg-slate-500/10",
        border: "border-slate-500/20",
      };
    default:
      return {
        variant: "outline" as const,
        label: state || "未知",
        color: "text-muted-foreground",
        bg: "bg-white/[0.03]",
        border: "border-white/10",
      };
  }
}

export default function DocumentsPage() {
  const [collectionFilter, setCollectionFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["documents", collectionFilter, stateFilter],
    queryFn: () =>
      workbenchApi.listDocuments({
        collection_id: collectionFilter || undefined,
        document_state: stateFilter === "ALL" ? undefined : stateFilter,
      }),
  });

  const documents = data?.items ?? [];

  const filteredDocuments = documents.filter((doc) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      String(doc.filename || "").toLowerCase().includes(query) ||
      String(doc.doc_id || "").toLowerCase().includes(query)
    );
  });

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div variants={staggerItem}>
        <h1 className="text-2xl font-semibold tracking-tight">文档库</h1>
        <p className="text-sm text-muted-foreground mt-1">
          已入库的文档和 chunk 管理。
        </p>
      </motion.div>

      {/* Filters — Pill Style */}
      <motion.div
        variants={staggerItem}
        className="flex flex-wrap items-center gap-2"
      >
        <div className="flex items-center gap-2 glass rounded-full px-1 py-1">
          <Search className="h-3.5 w-3.5 text-muted-foreground ml-2" />
          <Input
            placeholder="搜索文档..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-48 h-7 bg-transparent border-0 focus-visible:ring-0 focus-visible:shadow-none px-0 text-sm"
          />
        </div>

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
          value={stateFilter}
          onValueChange={(v) => setStateFilter(v ?? "ALL")}
        >
          <SelectTrigger className="w-32 h-8 glass rounded-full border-white/10 text-xs">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent className="glass-strong rounded-xl border-white/10">
            <SelectItem value="ALL">全部</SelectItem>
            <SelectItem value="ACTIVE">已激活</SelectItem>
            <SelectItem value="PENDING">待处理</SelectItem>
            <SelectItem value="ARCHIVED">已归档</SelectItem>
          </SelectContent>
        </Select>

        {(collectionFilter || stateFilter !== "ALL" || searchQuery) && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 rounded-full hover:bg-white/[0.06]"
            onClick={() => {
              setCollectionFilter("");
              setStateFilter("ALL");
              setSearchQuery("");
            }}
          >
            清除筛选
          </Button>
        )}

        {filteredDocuments.length > 0 && (
          <span className="text-xs text-muted-foreground/50 ml-auto">
            共 {filteredDocuments.length} 条结果
          </span>
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
          <BackendGap feature="Document Library" endpoint={error.endpoint} />
        ) : (
          <div className="text-red-400 text-sm glass rounded-xl p-4 border-red-500/20">
            {isApiError(error)
              ? error.message
              : error instanceof Error
              ? error.message
              : typeof error === "string"
              ? error
              : JSON.stringify(error)}
          </div>
        ))}

      {/* Empty */}
      {!isLoading &&
        !error &&
        filteredDocuments.length === 0 && (
          <EmptyState
            icon={Database}
            title="暂无文档"
            description="没有已入库的文档。上传文件并通过审核后即可查看。"
          />
        )}

      {/* Document List */}
      {!isLoading && !error && filteredDocuments.length > 0 && (
        <div className="space-y-2">
          {filteredDocuments.map((doc, index) => {
            const iconConfig = getDocIcon(doc.filename);
            const stateConfig = getStateConfig(doc.document_state);
            const Icon = iconConfig.icon;

            return (
              <motion.div
                key={doc.doc_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04 }}
              >
                <Link href={`/documents/${doc.doc_id}`}>
                  <Card
                    interactive
                    className="relative overflow-hidden"
                  >
                    <CardContent className="p-4 flex items-center gap-4">
                      {/* Status color bar */}
                      <div
                        className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${stateConfig.bg.replace("bg-", "bg-")}`}
                        style={{
                          backgroundColor:
                            doc.document_state === "ACTIVE"
                              ? "rgba(16, 185, 129, 0.5)"
                              : doc.document_state === "PENDING"
                              ? "rgba(245, 158, 11, 0.5)"
                              : "rgba(148, 163, 184, 0.3)",
                        }}
                      />

                      {/* Icon */}
                      <div
                        className={`flex items-center justify-center w-11 h-11 rounded-xl shrink-0 ${iconConfig.bg}`}
                      >
                        <Icon className={`h-5 w-5 ${iconConfig.color}`} />
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">
                            {doc.filename || doc.doc_id}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 mt-1.5">
                          <Badge
                            variant="outline"
                            className="text-[10px] h-5 border-white/10"
                          >
                            {doc.collection_id}
                          </Badge>
                          <span className="text-[11px] text-muted-foreground/60">
                            {doc.chunk_count} chunks
                          </span>
                          <span className="text-[11px] text-muted-foreground/60">
                            {doc.page_count || 0} pages
                          </span>
                          {doc.parser_profile_name && (
                            <span className="text-[11px] text-muted-foreground/60">
                              {doc.parser_profile_name}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Status */}
                      <div className="flex items-center gap-2 shrink-0">
                        <Badge
                          variant="outline"
                          className={`text-[10px] h-6 border ${stateConfig.border} ${stateConfig.bg}`}
                        >
                          <span className={stateConfig.color}>
                            {stateConfig.label}
                          </span>
                        </Badge>
                        {doc.is_stale && (
                          <Badge
                            variant="destructive"
                            className="text-[10px] h-5"
                          >
                            STALE
                          </Badge>
                        )}
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
