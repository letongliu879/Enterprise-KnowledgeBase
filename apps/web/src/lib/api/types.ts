// Canonical wire types — NEVER use deprecated fields here
// query (not query_text), token_budget (not max_context_tokens),
// evidence_items (not result_chunks), doc_id (not final_doc_id),
// evidence_id (not chunk_id), content (not display_text)

export interface ApiError {
  code: string;
  message: string;
  downstream?: string;
}

// ── Admin ──────────────────────────────────────────────────────────────

export interface AdminCollection {
  collection_id: string;
  tenant_id: string;
  name: string;
  description?: string;
  lifecycle_state: "active" | "archived" | "disabled";
  authority_level?: number;
  access_policy?: Record<string, unknown>;
  default_parser_profile_id?: string;
  default_retrieval_profile_id?: string;
  default_approval_policy_id?: string;
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
}

export interface CollectionListResponse {
  items: AdminCollection[];
  total: number;
}

export interface AdminUser {
  user_id: string;
  email: string;
  display_name?: string;
  roles: string[];
  tenant_id: string;
  allowed_collections: string[];
}

export interface ParserProfileItem {
  parser_profile_id: string;
  name: string;
  parser_id: string;
  state: string;
  is_default: boolean;
}

export interface RetrievalProfileItem {
  retrieval_profile_id: string;
  name: string;
  state: string;
}

// ── Workbench ──────────────────────────────────────────────────────────

export type UploadStatus =
  | "uploading"
  | "uploaded"
  | "duplicate"
  | "parsing"
  | "reviewing"
  | "approved"
  | "rejected"
  | "published"
  | "indexing"
  | "archived"
  | "retracted"
  | "failed";

export interface WorkbenchUploadSession {
  upload_id: string;
  user_id: string;
  tenant_id: string;
  collection_id: string;
  source_file_id?: string;
  intake_job_id?: string;
  parse_snapshot_id?: string;
  ticket_id?: string;
  selected_parser_profile_id?: string;
  parser_override_json?: Record<string, unknown>;
  access_scope_json?: Record<string, unknown> | null;
  status: UploadStatus;
  progress_pct: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkbenchTaskView {
  upload_id: string;
  status: UploadStatus;
  progress_pct: number;
  source_file_state?: string;
  intake_job_state?: string;
  parse_snapshot_state?: string;
  ticket_state?: string;
  published_document_state?: string | null;
  filename: string;
  collection_id: string;
  created_at: string;
  updated_at: string;
}

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

export interface TicketItem {
  ticket_id: string;
  collection_id: string;
  status: string;
  doc_id: string | null;
  source_file_id: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface TicketDetail {
  ticket_id: string;
  collection_id: string;
  status: string;
  doc_id: string | null;
  source_file_id: string | null;
  parse_snapshot_id: string | null;
  filename?: string | null;
  decision: string | null;
  decision_reason: string | null;
  decided_by: string | null;
  tenant_id: string;
  created_at: string;
  updated_at: string | null;
  failure_code?: string | null;
  failure_stage?: string | null;
  next_action?: string | null;
}

export interface TicketDecisionResult {
  ticket_id: string;
  status: string;
  decision: string;
}

export interface AgentReviewView {
  ticket_id: string;
  decision: "PASS" | "FAIL" | "REVIEW" | "DEGRADED";
  quality_findings: Array<{
    category: string;
    severity: "critical" | "major" | "minor" | "info";
    message: string;
    evidence_anchor?: string;
  }>;
  risk_flags: Array<{
    flag_type: string;
    description: string;
    confidence?: number;
  }>;
  evidence_anchors: Array<{
    anchor_id: string;
    doc_id: string;
    evidence_id: string;
    content?: string;
    page_span?: { page_from: number; page_to: number };
  }>;
  model?: string;
  version?: string;
  prompt_hash?: string;
  suggested_fixes: Array<{
    fix_type: string;
    description: string;
    target_evidence_id?: string;
  }>;
  degraded_reason?: string | null;
  failure_reason?: string | null;
  created_at: string;
}

export interface ChunkView {
  evidence_id: string;
  doc_id: string;
  content: string;
  vector_text?: string;
  section_path?: string[];
  page_spans?: Array<{ page_from: number; page_to: number }>;
  chunk_type?: string;
  metadata?: Record<string, unknown>;
}

export interface ChunkRevisionRequest {
  content?: string;
  vector_text?: string;
  section_path?: string[];
  metadata_patch?: Record<string, unknown>;
  edit_reason?: string;
}

// ── Access / Retrieval ─────────────────────────────────────────────────

export interface RetrieveRequest {
  query: string;
  collection_scope: string[];
  retrieval_profile_id: string;
  token_budget?: number;
  filters?: Record<string, unknown>;
  language?: string;
  cross_languages?: string[];
  keyword?: boolean;
  meta_data_filter?: Record<string, unknown>;
  debug?: "none" | "basic" | "full";
}

export interface EvidenceItem {
  collection_id: string;
  doc_id: string;
  evidence_id: string;
  document_index_revision_id: string;
  content: string;
  section_path: string[];
  page_spans: Array<{ page_from: number; page_to: number }>;
  score: number;
  source_stage: string;
  why_selected: string;
}

export interface KnowledgeContext {
  query_id: string;
  tenant_id?: string;
  principal_context?: Record<string, unknown>;
  index_version_used: string[];
  collection_plans_used: Array<Record<string, unknown>>;
  evidence_items: EvidenceItem[];
  grouped_sources: Array<Record<string, unknown>>;
  citations: Array<Record<string, unknown>>;
  token_budget_used: number;
  retrieval_debug?: Record<string, unknown>;
}

// ── Access Scope ───────────────────────────────────────────────────────

export interface AccessScope {
  scope_type: "internal" | "external";
  // internal
  department?: string;
  role?: string;
  user?: string;
  group?: string;
  // external
  agent_type_id?: string;
  api_key?: string;
  customer?: string;
  app?: string;
}
