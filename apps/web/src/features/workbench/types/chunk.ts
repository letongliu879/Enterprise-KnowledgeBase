// features/workbench/types/chunk.ts

export interface PageSpan {
  page_from: number;
  page_to: number;
}

export interface ChunkView {
  evidence_id: string;
  doc_id: string;
  content: string;
  vector_text?: string;
  section_path?: string[];
  page_spans?: PageSpan[];
  chunk_type?: string;
  metadata?: Record<string, unknown>;
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
