"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
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
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className={titleColor}>{titleText}</DialogTitle>
          <DialogDescription>
            {mode === "pre-publish"
              ? "Save as draft first, then submit to indexing."
              : "Changes will be applied directly to the indexed chunk."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Evidence ID</Label>
            <p className="text-sm font-mono text-muted-foreground">{chunk.evidence_id}</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="content">Content *</Label>
            <textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="Enter chunk content..."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="section-path">Section Path (JSON)</Label>
            <textarea
              id="section-path"
              value={sectionPath}
              onChange={(e) => setSectionPath(e.target.value)}
              disabled={mode === "post-publish"}
              className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder='["Chapter 1", "Section 1.1"]'
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="metadata">Metadata (JSON)</Label>
            <textarea
              id="metadata"
              value={metadata}
              onChange={(e) => setMetadata(e.target.value)}
              className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder='{"keywords": ["sales", "Q3"]}'
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-reason">
              Edit Reason {mode === "pre-publish" && "*"}
            </Label>
            <input
              id="edit-reason"
              value={editReason}
              onChange={(e) => setEditReason(e.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              placeholder="Why are you editing this chunk?"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2">
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
