"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  FileText,
  Search,
  ChevronRight,
  Database,
  Filter,
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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">文档库</h1>
        <p className="text-sm text-muted-foreground mt-1">
          已入库的文档和 chunk 管理。
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索文档..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-56 h-8"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="知识库集合..."
            value={collectionFilter}
            onChange={(e) => setCollectionFilter(e.target.value)}
            className="w-40 h-8"
          />
        </div>
        <Select
          value={stateFilter}
          onValueChange={(v) => setStateFilter(v ?? "ALL")}
        >
          <SelectTrigger className="w-36 h-8">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent>
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
            onClick={() => {
              setCollectionFilter("");
              setStateFilter("ALL");
              setSearchQuery("");
            }}
          >
            清除
          </Button>
        )}
      </div>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
      )}

      {error && (
        isBackendGap(error) ? (
          <BackendGap feature="Document Library" endpoint={error.endpoint} />
        ) : (
          <div className="text-red-500 text-sm">
            {isApiError(error) ? error.message : 
              error instanceof Error ? error.message : 
              typeof error === 'string' ? error : 
              JSON.stringify(error)}
          </div>
        )
      )}

      {!isLoading && !error && filteredDocuments.length === 0 ? (
        <EmptyState
          icon={Database}
          title="暂无文档"
          description="没有已入库的文档。上传文件并通过审核后即可查看。"
        />
      ) : (
        <div className="space-y-2">
          {filteredDocuments.map((doc) => (
            <Link key={doc.doc_id} href={`/documents/${doc.doc_id}`}>
              <Card className="hover:border-primary/50 transition-colors cursor-pointer">
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="shrink-0">
                    <FileText className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">
                        {doc.filename || doc.doc_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      <Badge variant="outline" className="text-xs">
                        {doc.collection_id}
                      </Badge>
                      <span>{doc.chunk_count} chunks</span>
                      <span>{doc.page_count || 0} pages</span>
                      {doc.parser_profile_name && (
                        <span>{doc.parser_profile_name}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge
                      variant={
                        doc.document_state === "ACTIVE"
                          ? "default"
                          : doc.document_state === "ARCHIVED"
                          ? "secondary"
                          : "outline"
                      }
                    >
                      {doc.document_state || "UNKNOWN"}
                    </Badge>
                    {doc.is_stale && (
                      <Badge variant="destructive" className="text-xs">
                        STALE
                      </Badge>
                    )}
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
