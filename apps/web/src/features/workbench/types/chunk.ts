// features/workbench/types/chunk.ts

import type { ChunkView as ApiChunkView, PageSpan } from "@/lib/api/types";

export type { PageSpan };

export interface ChunkView extends ApiChunkView {
  status?: "active" | "draft" | "superseded";
}

export interface ChunkEditData {
  content: string;
  section_path?: string[];
  metadata?: Record<string, unknown>;
  edit_reason?: string;
}

export interface ChunkEditItem {
  chunk_edit_id: string;
  tenant_id: string;
  collection_id: string;
  parse_snapshot_id?: string;
  base_evidence_id: string;
  content?: string;
  section_path?: string[];
  metadata_patch?: Record<string, unknown>;
  status: "draft" | "submitted" | "applied" | "rejected";
  edit_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface ChunkListResponse {
  items: ChunkView[];
  total: number;
}
