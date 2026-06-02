// features/workbench/types/document.ts

export interface DocumentProjectionItem {
  doc_id: string;
  tenant_id: string;
  collection_id: string;
  source_file_id: string | null;
  parse_snapshot_id: string | null;
  published_doc_id: string | null;
  upload_id: string | null;
  filename: string | null;
  mime_type: string | null;
  document_state: string | null;
  publish_state: string | null;
  active_index_version: string | null;
  chunk_count: number;
  page_count: number;
  parser_profile_id: string | null;
  parser_profile_name: string | null;
  projection_updated_at: string | null;
  is_stale: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface DocumentListResponse {
  items: DocumentProjectionItem[];
  total: number;
}
