"use client";

import { useState, useEffect } from "react";
import { Braces, FileText, Info, Layers3, PencilLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ChunkView, ChunkEditData } from "../../types/chunk";

interface ChunkEditModalProps {
  open: boolean;
  mode: "pre-publish" | "post-publish";
  chunk: ChunkView | null;
  onSaveDraft?: (data: ChunkEditData) => void;
  onSubmit?: (data: ChunkEditData) => void;
  onSave?: (data: ChunkEditData) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export function ChunkEditModal({
  open,
  mode,
  chunk,
  onSaveDraft,
  onSubmit,
  onSave,
  onCancel,
  isSubmitting = false,
}: ChunkEditModalProps) {
  const [content, setContent] = useState(chunk?.content || "");
  const [sectionPath, setSectionPath] = useState(
    JSON.stringify(chunk?.section_path || [], null, 2)
  );
  const [metadata, setMetadata] = useState(
    JSON.stringify(chunk?.metadata || {}, null, 2)
  );
  const [editReason, setEditReason] = useState("");

  // Reset form when chunk changes
  useEffect(() => {
    if (chunk) {
      setContent(chunk.content || "");
      setSectionPath(JSON.stringify(chunk.section_path || [], null, 2));
      setMetadata(JSON.stringify(chunk.metadata || {}, null, 2));
      setEditReason("");
    }
  }, [chunk]);

  if (!chunk) return null;

  const titleColor =
    mode === "pre-publish" ? "text-orange-600" : "text-blue-600";
  const titleText =
    mode === "pre-publish" ? "Edit Chunk (Pre-publish)" : "Edit Chunk (Published)";

  const pageSummary =
    chunk.page_spans && chunk.page_spans.length > 0
      ? `P${chunk.page_spans[0].page_from}-${chunk.page_spans[0].page_to}`
      : null;
  const sectionSummary =
    chunk.section_path && chunk.section_path.length > 0
      ? chunk.section_path.join(" / ")
      : null;

  const buildData = (): ChunkEditData => {
    let parsedSectionPath: string[] | undefined;
    let parsedMetadata: Record<string, unknown> | undefined;

    try {
      parsedSectionPath = JSON.parse(sectionPath);
    } catch {
      /* ignore invalid JSON */
    }

    try {
      parsedMetadata = JSON.parse(metadata);
    } catch {
      /* ignore invalid JSON */
    }

    return {
      content,
      section_path: parsedSectionPath,
      metadata: parsedMetadata,
      edit_reason: editReason || undefined,
    };
  };

  const handleSaveDraft = () => {
    if (onSaveDraft) {
      onSaveDraft(buildData());
    }
  };

  const handleSubmit = () => {
    if (onSubmit) {
      onSubmit(buildData());
    }
  };

  const handleSave = () => {
    if (onSave) {
      onSave(buildData());
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent className="max-h-[90vh] max-w-[calc(100%-2rem)] overflow-y-auto p-0 sm:max-w-5xl">
        <DialogHeader>
          <div className="border-b px-6 py-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-3">
                <DialogTitle className={titleColor}>{titleText}</DialogTitle>
                <DialogDescription>
                  {mode === "pre-publish"
                    ? "Save as draft first, then submit to indexing."
                    : "Changes will be applied directly to the indexed chunk."}
                </DialogDescription>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className="font-mono text-xs">
                    {chunk.evidence_id}
                  </Badge>
                  {pageSummary ? (
                    <Badge variant="secondary" className="text-xs">
                      {pageSummary}
                    </Badge>
                  ) : null}
                  {chunk.chunk_type ? (
                    <Badge variant="outline" className="text-xs uppercase">
                      {chunk.chunk_type}
                    </Badge>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </DialogHeader>

        <div className="grid gap-0 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
          <div className="space-y-5 px-6 py-5">
            <div className="space-y-2">
              <Label htmlFor="content" className="gap-2">
                <PencilLine className="h-4 w-4 text-muted-foreground" />
                Content *
              </Label>
              <Textarea
                id="content"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="min-h-[420px] resize-y bg-background text-sm leading-7"
                placeholder="Enter chunk content..."
              />
            </div>

            <div className="rounded-xl border bg-muted/10 p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Info className="h-4 w-4 text-muted-foreground" />
                Editing Notes
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Keep the chunk self-contained and retrieval-friendly. Preserve structure and
                page meaning; avoid stuffing unrelated context into one chunk.
              </p>
            </div>
          </div>

          <div className="space-y-5 border-t bg-muted/5 px-6 py-5 lg:border-t-0 lg:border-l">
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <FileText className="h-4 w-4 text-muted-foreground" />
                Context
              </div>
              <div className="space-y-3 rounded-xl border bg-background/80 p-4">
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                    Evidence ID
                  </p>
                  <p className="break-all font-mono text-xs text-foreground/80">
                    {chunk.evidence_id}
                  </p>
                </div>
                {sectionSummary ? (
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                      Section Path
                    </p>
                    <p className="text-sm leading-6 text-foreground/90">{sectionSummary}</p>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-reason" className="gap-2">
                <PencilLine className="h-4 w-4 text-muted-foreground" />
                Edit Reason {mode === "pre-publish" && "*"}
              </Label>
              <Input
                id="edit-reason"
                value={editReason}
                onChange={(e) => setEditReason(e.target.value)}
                placeholder="Why are you editing this chunk?"
                className="bg-background"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="section-path" className="gap-2">
                <Layers3 className="h-4 w-4 text-muted-foreground" />
                Section Path (JSON)
              </Label>
              <Textarea
                id="section-path"
                value={sectionPath}
                onChange={(e) => setSectionPath(e.target.value)}
                disabled={mode === "post-publish"}
                className="min-h-[120px] resize-y bg-background font-mono text-xs leading-6"
                placeholder='["Chapter 1", "Section 1.1"]'
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="metadata" className="gap-2">
                <Braces className="h-4 w-4 text-muted-foreground" />
                Metadata (JSON)
              </Label>
              <Textarea
                id="metadata"
                value={metadata}
                onChange={(e) => setMetadata(e.target.value)}
                className="min-h-[220px] resize-y bg-background font-mono text-xs leading-6"
                placeholder='{"keywords": ["sales", "Q3"]}'
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t bg-muted/5 px-6 py-4">
          <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>

          {mode === "pre-publish" && (
            <>
              <Button
                variant="secondary"
                onClick={handleSaveDraft}
                disabled={isSubmitting || !content.trim()}
              >
                Save Draft
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={isSubmitting || !content.trim() || !editReason.trim()}
              >
                Submit
              </Button>
            </>
          )}

          {mode === "post-publish" && (
            <Button
              onClick={handleSave}
              disabled={isSubmitting || !content.trim()}
            >
              Save
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
