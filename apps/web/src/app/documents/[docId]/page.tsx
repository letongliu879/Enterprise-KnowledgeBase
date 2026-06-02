"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Database,
  FileText,
} from "lucide-react";
import { toast } from "sonner";
import { DocumentViewer } from "@/components/document-workbench/document-viewer";
import { ChunkEditorWorkbench } from "@/features/workbench/components/chunk-editor";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { workbenchApi } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";

export default function DocumentDetailPage() {
  const { docId } = useParams<{ docId: string }>();
  const [activeTab, setActiveTab] = useState("source");

  const {
    data: document,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["document", docId],
    queryFn: () => workbenchApi.getDocument(docId),
    enabled: Boolean(docId),
    retry: 0,
  });

  const parseSnapshotId = document?.parse_snapshot_id ?? "";

  const {
    data: chunks,
    isLoading: chunksLoading,
  } = useQuery({
    queryKey: ["document-chunks", parseSnapshotId],
    queryFn: () => workbenchApi.getParseSnapshotChunks(parseSnapshotId, 1, 100),
    enabled: Boolean(parseSnapshotId),
    retry: 0,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-56 rounded-lg" />
        <Skeleton className="h-36 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          {isApiError(error) ? error.message : String(error)}
        </AlertDescription>
      </Alert>
    );
  }

  if (!document) {
    return (
      <EmptyState
        icon={FileText}
        title="文档未找到"
        description="该文档不存在或您没有访问权限。"
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border bg-card/92 p-5 shadow-sm">
        <div className="flex flex-col gap-5">
          <div className="flex items-start gap-3">
            <Button variant="outline" size="icon" className="mt-1 rounded-full" onClick={() => window.location.href = '/documents'}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{document.document_state || "UNKNOWN"}</Badge>
                {document.is_stale && (
                  <Badge variant="destructive">STALE</Badge>
                )}
              </div>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight xl:text-4xl">
                {document.filename || document.doc_id}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                已入库文档。可以直接修改 chunk 内容，修改后会自动同步到检索系统。
              </p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="space-y-1.5 rounded-xl border bg-muted/10 p-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Doc ID</p>
              <p className="break-all text-sm font-mono text-foreground">{document.doc_id}</p>
            </div>
            <div className="space-y-1.5 rounded-xl border bg-muted/10 p-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Collection</p>
              <p className="text-sm font-medium text-foreground">{document.collection_id}</p>
            </div>
            <div className="space-y-1.5 rounded-xl border bg-muted/10 p-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Chunks</p>
              <p className="text-sm font-medium text-foreground">{document.chunk_count}</p>
            </div>
            <div className="space-y-1.5 rounded-xl border bg-muted/10 p-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Index Version</p>
              <p className="text-sm font-medium text-foreground">{document.active_index_version || "-"}</p>
            </div>
          </div>
        </div>
      </section>

      <div className="min-w-0 space-y-4">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList
            variant="line"
            className="w-full justify-start gap-2 overflow-x-auto rounded-none border-0 bg-transparent p-0"
          >
            <TabsTrigger value="source">
              <FileText className="mr-1 h-3.5 w-3.5" />
              原文预览
            </TabsTrigger>
            <TabsTrigger value="chunks">
              <Database className="mr-1 h-3.5 w-3.5" />
              Chunk 管理
            </TabsTrigger>
          </TabsList>

          <TabsContent value="source" className="space-y-4">
            {!parseSnapshotId ? (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>该文档没有关联的解析快照。</AlertDescription>
              </Alert>
            ) : (
              <DocumentViewer
                parseSnapshotId={parseSnapshotId}
                filename={document.filename || undefined}
                chunks={chunks?.items ?? []}
              />
            )}
          </TabsContent>

          <TabsContent value="chunks" className="space-y-4">
            {!parseSnapshotId ? (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>该文档没有关联的解析快照。</AlertDescription>
              </Alert>
            ) : (
              <ChunkEditorWorkbench
                parseSnapshotId={parseSnapshotId}
                mode="post-publish"
                title="Chunk 管理"
                description="已入库文档的 chunk 可以直接编辑，保存后会自动同步到检索系统。"
              />
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
