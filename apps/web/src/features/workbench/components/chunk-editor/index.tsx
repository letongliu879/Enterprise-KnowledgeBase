"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Edit3,
  FileText,
  Layers,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { workbenchApi } from "@/lib/api/client";
import { isApiError, getErrorMessage } from "@/lib/api/errors";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ChunkEditModal } from "./chunk-edit-modal";
import type { ChunkView, ChunkEditData } from "../../types/chunk";

interface ChunkEditorWorkbenchProps {
  parseSnapshotId: string;
  mode: "pre-publish" | "post-publish";
  title?: string;
  description?: string;
  focusEvidenceId?: string | null;
}

export function ChunkEditorWorkbench({
  parseSnapshotId,
  mode,
  title = "Chunk editor",
  description = "Edit parsed chunks.",
  focusEvidenceId,
}: ChunkEditorWorkbenchProps) {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [editingChunk, setEditingChunk] = useState<ChunkView | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const activeQuery = searchQuery.trim() || focusEvidenceId || "";

  const {
    data: chunksData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["parse-snapshot-chunks", parseSnapshotId],
    queryFn: () => workbenchApi.getParseSnapshotChunks(parseSnapshotId, 1, 100),
    enabled: Boolean(parseSnapshotId),
    retry: 0,
  });

  const filteredChunks =
    chunksData?.items.filter((chunk) => {
      if (!activeQuery) return true;
      const query = activeQuery.toLowerCase();
      return (
        String(chunk.content || "").toLowerCase().includes(query) ||
        String(chunk.evidence_id || "").toLowerCase().includes(query)
      );
    }) ?? [];

  const patchChunk = useMutation({
    mutationFn: ({
      evidenceId,
      data,
    }: {
      evidenceId: string;
      data: ChunkEditData;
    }) => workbenchApi.patchChunk(evidenceId, data),
    onSuccess: () => {
      toast.success("Chunk updated");
      queryClient.invalidateQueries({
        queryKey: ["parse-snapshot-chunks", parseSnapshotId],
      });
      setIsModalOpen(false);
      setEditingChunk(null);
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "Failed to update chunk");
    },
  });

  const handleEdit = (chunk: ChunkView) => {
    setEditingChunk(chunk);
    setIsModalOpen(true);
  };

  const handleSave = (data: ChunkEditData) => {
    if (!editingChunk) return;
    patchChunk.mutate({ evidenceId: editingChunk.evidence_id, data });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full rounded-lg" />
        <Skeleton className="h-32 w-full rounded-lg" />
        <Skeleton className="h-32 w-full rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          {isApiError(error) ? error.message : getErrorMessage(error)}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="rounded-2xl border-dashed bg-card/85">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Layers className="h-4 w-4" />
            {title}
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
      </Card>

      <div className="flex items-center gap-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search chunks..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-sm"
        />
        <Badge variant="outline">
          {filteredChunks.length} / {chunksData?.items.length ?? 0}
        </Badge>
      </div>

      {filteredChunks.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No chunks found"
          description={
            searchQuery
              ? "No chunks match your search query."
              : "This parse snapshot does not contain any chunks yet."
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredChunks.map((chunk) => (
            <ChunkCard
              key={chunk.evidence_id}
              chunk={chunk}
              onEdit={() => handleEdit(chunk)}
              highlighted={focusEvidenceId === chunk.evidence_id}
            />
          ))}
        </div>
      )}

      <ChunkEditModal
        open={isModalOpen}
        mode={mode}
        chunk={editingChunk}
        onSave={mode === "post-publish" ? handleSave : undefined}
        onCancel={() => {
          setIsModalOpen(false);
          setEditingChunk(null);
        }}
        isSubmitting={patchChunk.isPending}
      />
    </div>
  );
}

function ChunkCard({
  chunk,
  onEdit,
  highlighted = false,
}: {
  chunk: ChunkView;
  onEdit: () => void;
  highlighted?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const content = chunk.content || "";
  const previewText =
    content.length > 300 && !expanded
      ? content.slice(0, 300) + "..."
      : content;

  useEffect(() => {
    if (highlighted) {
      cardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlighted]);

  return (
    <Card
      ref={cardRef}
      className={`rounded-2xl ${highlighted ? "ring-2 ring-sky-500 ring-offset-2" : ""}`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="font-mono text-xs">
                {chunk.evidence_id.slice(0, 20)}...
              </Badge>
              {chunk.section_path && chunk.section_path.length > 0 && (
                <Badge variant="secondary" className="text-xs">
                  {chunk.section_path.join(" / ")}
                </Badge>
              )}
              {chunk.page_spans && chunk.page_spans.length > 0 && (
                <Badge variant="outline" className="text-xs">
                  P{chunk.page_spans[0].page_from}-
                  {chunk.page_spans[0].page_to}
                </Badge>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={onEdit}>
              <Edit3 className="h-3.5 w-3.5" />
            </Button>
            {content.length > 300 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <ChevronUp className="h-3.5 w-3.5" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5" />
                )}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="max-h-[400px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/10 p-4 text-sm leading-6">
          {previewText || "No content"}
        </div>
      </CardContent>
    </Card>
  );
}
