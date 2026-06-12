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

export interface ParserProfileDetail {
  parser_profile_id: string;
  name: string;
  state: "draft" | "published";
  description?: string;
  parser_id?: string;
  config?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyItem {
  api_key_id: string;
  name: string;
  key_prefix: string;
  state: "active" | "revoked";
  permissions: string[];
  collection_ids: string[];
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
}

export interface ApiKeyDetail extends ApiKeyItem {
  full_key?: string;
}

export interface ApiKeyUsage {
  api_key_id: string;
  total_requests: number;
  total_tokens: number;
  qps_peak: number;
  last_used_at: string | null;
  daily_stats: Array<{
    date: string;
    requests: number;
    tokens: number;
  }>;
}

export interface TrashItem {
  doc_id: string;
  tenant_id: string;
  collection_id: string;
  filename: string | null;
  source_file_id: string | null;
  deleted_by: string;
  deleted_at: string;
  auto_purge_at: string;
}

export interface TrashListResponse {
  items: TrashItem[];
  total: number;
}

export interface RetrievalProfileDetail {
  retrieval_profile_id: string;
  name: string;
  state: "draft" | "published";
  description?: string;
  config: {
    rerank_model?: string;
    top_k?: number;
    similarity_threshold?: number;
    token_budget_limit?: number;
    metadata_filters?: Record<string, unknown>;
  };
  created_at: string;
  updated_at: string;
}

// ── Workbench ──────────────────────────────────────────────────────────

export type UploadStatus =
  | "uploading"
  | "ready"
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
  | "cancelled"
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
  degraded_reason?: string | null;
  created_at: string | null;
  updated_at: string | null;
  ticket_id?: string | null;
  ticket_status?: string | null;
  task_status?: string | null;
  has_source_file?: boolean;
  has_parse_snapshot?: boolean;
  has_active_index?: boolean;
  latest_updated_at?: string | null;
}

export interface TicketItem {
  ticket_id: string;
  collection_id: string;
  status: string;
  title?: string | null;
  filename?: string | null;
  priority?: string | null;
  assignee_user_id?: string | null;
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

export interface TicketComment {
  comment_id: string;
  ticket_id: string;
  author_id: string;
  author_name?: string | null;
  author_email?: string | null;
  content: string;
  mentions?: string[] | null;
  created_at: string;
  updated_at: string | null;
}

export interface TicketCommentListResponse {
  items: TicketComment[];
  total: number;
}

export interface AgentReviewView {
  ticket_id: string;
  decision?: string | null;
  source_file_id?: string | null;
  parse_snapshot_id?: string | null;
  findings: Array<{
    finding_id: string;
    severity: "critical" | "high" | "medium" | "low" | "info";
    category: string;
    problem_summary: string;
    source_quote?: string;
    evidence_id?: string;
    doc_id?: string;
    source_file_id?: string;
    parse_snapshot_id?: string;
    page_from?: number;
    page_to?: number;
    state: "open" | "resolved";
    confidence?: number;
  }>;
  matched_count?: number;
  unmatched_count?: number;
  source?: "projection" | "approval";
}

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
}

export interface ChunkRevisionRequest {
  content?: string;
  vector_text?: string;
  section_path?: string[];
  metadata_patch?: Record<string, unknown>;
  edit_reason?: string;
}

export interface ParseSnapshotView {
  parse_snapshot_id: string;
  source_file_id: string;
  tenant_id?: string;
  collection_id?: string;
  source_binary_ref?: string;
  source_filename?: string;
  source_suffix?: string;
  parser_id?: string;
  parser_backend?: string;
  parser_profile_id?: string;
  effective_policy?: string;
  decision_reason?: string;
  preview_text?: string;
  document_metadata?: Record<string, unknown>;
  outline?: unknown[];
  chunk_preview?: unknown[];
  warnings?: string[];
  created_at?: string | null;
}

export interface SourceFilePreviewView {
  source_file_id: string;
  collection_id: string;
  filename: string;
  mime_type: string;
  page_count?: number | null;
  preview_available: boolean;
  preview_status?: string | null;
  preview_kind?: "pdf" | "image" | "html" | "text" | "unsupported" | string | null;
  preview_mime_type?: string | null;
  preview_url?: string | null;
  thumbnail_url?: string | null;
}

export interface WorkspaceTicketView {
  ticket_id: string;
  collection_id: string;
  status: string;
  tenant_id: string;
  doc_id?: string | null;
  source_file_id?: string | null;
  parse_snapshot_id?: string | null;
  upload_id?: string | null;
  title?: string | null;
  filename?: string | null;
  priority?: string | null;
  assignee_user_id?: string | null;
  decision?: string | null;
  decision_reason?: string | null;
  decided_by?: string | null;
  agent_decision?: string | null;
  agent_risk_level?: string | null;
  agent_finding_count: number;
  agent_blocking_finding_count: number;
  failure_code?: string | null;
  failure_stage?: string | null;
  next_action?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  projection_updated_at?: string | null;
  is_stale: boolean;
  source: "approval" | "projection" | "merged";
}

export interface WorkspaceDocumentView {
  doc_id?: string | null;
  tenant_id?: string | null;
  collection_id?: string | null;
  source_file_id?: string | null;
  parse_snapshot_id?: string | null;
  published_doc_id?: string | null;
  upload_id?: string | null;
  filename?: string | null;
  mime_type?: string | null;
  document_state?: string | null;
  publish_state?: string | null;
  active_index_version?: string | null;
  chunk_count: number;
  page_count: number;
  parser_profile_id?: string | null;
  parser_profile_name?: string | null;
  projection_updated_at?: string | null;
  is_stale: boolean;
  degraded_reason?: string | null;
  linkage_source:
    | "document_projection"
    | "ticket_projection"
    | "task_projection"
    | "missing";
}

export interface WorkspaceTaskView {
  upload_id: string;
  collection_id: string;
  status: string;
  filename?: string | null;
  source_file_id?: string | null;
  intake_job_id?: string | null;
  parse_snapshot_id?: string | null;
  ticket_id?: string | null;
  published_doc_id?: string | null;
  doc_id?: string | null;
  progress_pct: number;
  source_file_state?: string | null;
  intake_job_state?: string | null;
  parse_snapshot_state?: string | null;
  ticket_state?: string | null;
  published_document_state?: string | null;
  index_build_state?: string | null;
  active_index_version?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  projection_updated_at?: string | null;
  is_stale: boolean;
}

export interface WorkspaceSourceFileView {
  source_file_id: string;
  upload_id?: string | null;
  tenant_id?: string | null;
  collection_id?: string | null;
  filename?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  state?: string | null;
  intake_job_id?: string | null;
  scan_verdict?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WorkspaceParseSnapshotView {
  parse_snapshot_id: string;
  source_file_id?: string | null;
  tenant_id?: string | null;
  collection_id?: string | null;
  source_filename?: string | null;
  source_suffix?: string | null;
  parser_id?: string | null;
  parser_backend?: string | null;
  parser_profile_id?: string | null;
  effective_policy?: string | null;
  decision_reason?: string | null;
  preview_text?: string | null;
  warnings: string[];
  created_at?: string | null;
}

export interface WorkspaceChunkEditView {
  chunk_edit_id: string;
  tenant_id: string;
  collection_id: string;
  source_file_id?: string | null;
  parse_snapshot_id?: string | null;
  base_evidence_id: string;
  edit_scope: string;
  operation: string;
  content?: string | null;
  vector_text?: string | null;
  section_path?: string[] | null;
  metadata_patch?: Record<string, unknown> | null;
  citation_payload?: Record<string, unknown> | null;
  source_block_ids?: string[] | null;
  edit_reason?: string | null;
  edited_by: string;
  status: string;
  downstream_revision_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WorkspaceAgentReviewView {
  ticket_id: string;
  decision?: string | null;
  source_file_id?: string | null;
  parse_snapshot_id?: string | null;
  findings: Array<{
    finding_id: string;
    severity: "critical" | "high" | "medium" | "low" | "info";
    category: string;
    problem_summary: string;
    source_quote?: string | null;
    evidence_id?: string | null;
    doc_id?: string | null;
    source_file_id?: string | null;
    parse_snapshot_id?: string | null;
    page_from?: number | null;
    page_to?: number | null;
    state: "open" | "resolved";
    confidence?: number | null;
    chunk_quote?: string | null;
    why_wrong?: string | null;
    suggested_fix?: string | null;
    suggested_operation?: string | null;
  }>;
  matched_count: number;
  unmatched_count: number;
  source: "projection" | "approval" | "missing";
}

export interface WorkspaceCapabilitiesView {
  can_view_source: boolean;
  can_view_parsed_text: boolean;
  can_search_in_document: boolean;
  can_edit_drafts: boolean;
  can_jump_to_chunk: boolean;
  can_decide_ticket: boolean;
  can_approve: boolean;
  can_reject: boolean;
  can_upload: boolean;
  can_archive: boolean;
  can_retract: boolean;
  can_reindex: boolean;
}

export interface WorkspaceProjectionFreshnessView {
  ticket_projection_updated_at?: string | null;
  ticket_is_stale: boolean;
  document_projection_updated_at?: string | null;
  document_is_stale: boolean;
}

export interface WorkspaceDetailView {
  ticket_id: string;
  ticket?: WorkspaceTicketView | null;
  document: WorkspaceDocumentView;
  task?: WorkspaceTaskView | null;
  source_file?: WorkspaceSourceFileView | null;
  parse_snapshot?: WorkspaceParseSnapshotView | null;
  chunks: {
    items: ChunkView[];
    total: number;
  };
  chunk_edits: {
    items: WorkspaceChunkEditView[];
    total: number;
  };
  agent_review: WorkspaceAgentReviewView;
  capabilities: WorkspaceCapabilitiesView;
  projection_freshness: WorkspaceProjectionFreshnessView;
  degraded_parts: string[];
  trace_id: string;
}

export interface DocumentLifecycleActionRequest {
  reason: string;
  index_profile_id?: string;
}

export interface DocumentLifecycleActionResult {
  success: boolean;
  final_doc_id: string;
  previous_state?: string | null;
  new_state?: string | null;
  job_id?: string | null;
}

export interface BatchDocumentActionRequest {
  doc_ids: string[];
  reason: string;
  index_profile_id?: string;
}

export interface BatchDocumentActionItemResult {
  doc_id: string;
  success: boolean;
  previous_state?: string | null;
  new_state?: string | null;
  job_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface BatchDocumentActionResult {
  total: number;
  succeeded: number;
  failed: number;
  items: BatchDocumentActionItemResult[];
}

export type DocumentWorkspaceDetailView = WorkspaceDetailView;

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

// ── Dashboard ──────────────────────────────────────────────────────────

export interface DashboardStats {
  today_uploads: number;
  pending_review_count: number;
  total_documents: number;
  stale_ratio: number;
}

export interface DashboardResponse {
  stats: DashboardStats;
  recent_tickets: TicketItem[];
}

// ── Notifications ──────────────────────────────────────────────────────

export interface NotificationItem {
  notification_id: string;
  type: string;
  title: string;
  message: string;
  link?: string | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread_count: number;
}

export interface UnreadCountResponse {
  count: number;
}

// ── Audit Log ──────────────────────────────────────────────────────────

export interface AuditLogItem {
  log_id: string;
  operator_id: string;
  operator_email: string;
  operation_type: "upload" | "approve" | "reject" | "return" | "edit_chunk" | "archive" | "retract" | "reindex" | "delete";
  target_type: "document" | "collection" | "ticket" | "chunk";
  target_id: string;
  collection_id?: string;
  timestamp: string;
  ip_address: string;
  details?: Record<string, unknown>;
  before_snapshot?: Record<string, unknown>;
  after_snapshot?: Record<string, unknown>;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
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
