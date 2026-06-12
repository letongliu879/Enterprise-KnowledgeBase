import { http, HttpResponse } from "msw";
import type {
  AdminCollection,
  WorkbenchUploadSession,
  WorkbenchTaskView,
  TicketItem,
  TicketDetail,
  TicketDecisionResult,
  TicketComment,
  AgentReviewView,
  ChunkView,
  ParseSnapshotView,
  SourceFilePreviewView,
  WorkspaceDetailView,
  DocumentProjectionItem,
  DocumentLifecycleActionResult,
  BatchDocumentActionResult,
  CollectionListResponse,
  TrashItem,
} from "../lib/api/types";

// ── Helpers ────────────────────────────────────────────────────────────

const LOREM_600 =
  "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. " +
  "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem. Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur? Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur? At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident, similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus id quod maxime placeat facere possimus, omnis voluptas assumenda est, omnis dolor repellendus. Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non recusandae. Itaque earum rerum hic tenetur a sapiente delectus, ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis doloribus asperiores repellat. ";

const UNICODE_STR =
  "测试中文内容 🚀 日本語テキスト 🇯🇵 한국어 텍스트 🇰🇷 العربية 🌍 Ελληνικά 🏛️ עברית ✡️ русский текст 🐻 emojis: 🎉🔥💯🚀⭐🌈🍎🌍🎨🎵";

function deepNested(depth = 5): Record<string, unknown> {
  if (depth <= 0) return { leaf: "value" };
  return { level: depth, child: deepNested(depth - 1), extra: { a: { b: { c: { d: { e: "deep" } } } } } };
}

// ── Health ─────────────────────────────────────────────────────────────

export function buildHealthResponse(
  overrides?: Partial<{ service: string; status: string }>
) {
  return { service: "workbench", status: "ok", ...overrides };
}

export function buildHealthEmptyResponse() {
  return { service: "", status: "" };
}

export function buildHealthBoundaryResponse() {
  return { service: LOREM_600.slice(0, 520), status: UNICODE_STR };
}

export function buildHealthAllResponse(
  overrides?: Partial<{
    workbench: { status: string; service: string };
    services: Record<string, { status: string; service: string }>;
    all_healthy: boolean;
  }>
) {
  return {
    workbench: { status: "ok", service: "workbench" },
    services: {
      access: { status: "ok", service: "access" },
      retrieval: { status: "ok", service: "retrieval" },
      ingestion: { status: "ok", service: "ingestion" },
    },
    all_healthy: true,
    ...overrides,
  };
}

export function buildHealthAllEmptyResponse() {
  return {
    workbench: { status: "ok", service: "workbench" },
    services: {},
    all_healthy: true,
  };
}

export function buildHealthAllBoundaryResponse() {
  return {
    workbench: { status: UNICODE_STR, service: LOREM_600.slice(0, 520) },
    services: {
      [LOREM_600.slice(0, 300)]: { status: LOREM_600.slice(0, 300), service: UNICODE_STR },
    },
    all_healthy: false,
  };
}

// ── Me ─────────────────────────────────────────────────────────────────

export function buildMeResponse(
  overrides?: Partial<{
    user_id: string;
    email: string;
    display_name?: string;
    roles: string[];
    tenant_id: string;
    allowed_collections: string[];
  }>
) {
  return {
    user_id: "user-001",
    email: "admin@example.com",
    display_name: "Administrator",
    roles: ["knowledge_admin", "platform_admin"],
    tenant_id: "tenant-001",
    allowed_collections: ["coll-001", "coll-002"],
    ...overrides,
  };
}

export function buildMeEmptyResponse() {
  return {
    user_id: "user-001",
    email: "admin@example.com",
    roles: [],
    tenant_id: "tenant-001",
    allowed_collections: [],
  };
}

export function buildMeBoundaryResponse() {
  return {
    user_id: "user-001",
    email: "admin+🚀@example.com",
    display_name: LOREM_600.slice(0, 520),
    roles: ["knowledge_admin", UNICODE_STR],
    tenant_id: "tenant-001",
    allowed_collections: [LOREM_600.slice(0, 300)],
  };
}

// ── Collections ────────────────────────────────────────────────────────

export function buildCollection(overrides?: Partial<AdminCollection>): AdminCollection {
  return {
    collection_id: "coll-001",
    tenant_id: "tenant-001",
    name: "Default Collection",
    description: "Primary knowledge base collection",
    lifecycle_state: "active",
    authority_level: 1,
    access_policy: { public: false },
    default_parser_profile_id: "parser-default",
    default_retrieval_profile_id: "retrieval-default",
    default_approval_policy_id: "approval-default",
    created_by: "user-001",
    created_at: "2024-01-01T00:00:00Z",
    updated_by: "user-001",
    updated_at: "2024-06-01T00:00:00Z",
    ...overrides,
  };
}

export function buildCollectionEmptyResponse(): CollectionListResponse {
  return { items: [], total: 0 };
}

export function buildCollectionBoundaryResponse(): CollectionListResponse {
  return {
    items: [
      buildCollection({
        name: LOREM_600.slice(0, 520),
        description: UNICODE_STR,
        access_policy: deepNested(6),
      }),
    ],
    total: 1,
  };
}

export function buildCollectionListResponse(overrides?: Partial<CollectionListResponse>): CollectionListResponse {
  return {
    items: [buildCollection(), buildCollection({ collection_id: "coll-002", name: "Secondary" })],
    total: 2,
    ...overrides,
  };
}

export function buildCreateCollectionResponse(overrides?: Partial<Record<string, unknown>>) {
  return { collection_id: "coll-new", tenant_id: "tenant-001", name: "New Collection", ...overrides };
}

export function buildCreateCollectionEmptyResponse() {
  return {};
}

export function buildCreateCollectionBoundaryResponse() {
  return { collection_id: LOREM_600.slice(0, 520), metadata: deepNested(6) };
}

// ── Retrieval Profiles ─────────────────────────────────────────────────

export function buildRetrievalProfilesResponse(
  overrides?: Partial<{ items: Array<Record<string, unknown>>; total: number }>
) {
  return {
    items: [
      { retrieval_profile_id: "rp-001", name: "Standard", state: "published", top_k: 10 },
      { retrieval_profile_id: "rp-002", name: "Aggressive", state: "published", top_k: 50 },
    ],
    total: 2,
    ...overrides,
  };
}

export function buildRetrievalProfilesEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildRetrievalProfilesBoundaryResponse() {
  return {
    items: [
      {
        retrieval_profile_id: "rp-001",
        name: LOREM_600.slice(0, 520),
        state: UNICODE_STR,
        config: deepNested(6),
      },
    ],
    total: 1,
  };
}

// ── Uploads ────────────────────────────────────────────────────────────

export function buildUploadSession(overrides?: Partial<WorkbenchUploadSession>): WorkbenchUploadSession {
  return {
    upload_id: "upload-001",
    user_id: "user-001",
    tenant_id: "tenant-001",
    collection_id: "coll-001",
    source_file_id: "sf-001",
    intake_job_id: "job-001",
    parse_snapshot_id: "ps-001",
    ticket_id: "ticket-001",
    selected_parser_profile_id: "parser-default",
    parser_override_json: { ocr: true },
    access_scope_json: { scope_type: "internal", department: "engineering" },
    status: "published",
    progress_pct: 100,
    filename: "document.pdf",
    mime_type: "application/pdf",
    size_bytes: 1024000,
    error_message: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T01:00:00Z",
    ...overrides,
  };
}

export function buildCreateUploadResponse(overrides?: Partial<Record<string, unknown>>) {
  return { upload_id: "upload-new", status: "ready", ...overrides };
}

export function buildCreateUploadEmptyResponse() {
  return {};
}

export function buildCreateUploadBoundaryResponse() {
  return { upload_id: LOREM_600.slice(0, 520), metadata: deepNested(6), filename: UNICODE_STR };
}

export function buildUploadFileContentResponse(overrides?: Partial<WorkbenchUploadSession>): WorkbenchUploadSession {
  return buildUploadSession({ status: "uploaded", progress_pct: 100, ...overrides });
}

export function buildUploadFileContentEmptyResponse(): WorkbenchUploadSession {
  return buildUploadSession({
    parse_snapshot_id: undefined,
    ticket_id: undefined,
    intake_job_id: undefined,
    source_file_id: undefined,
    parser_override_json: undefined,
    access_scope_json: null,
  });
}

export function buildUploadFileContentBoundaryResponse(): WorkbenchUploadSession {
  return buildUploadSession({
    filename: LOREM_600.slice(0, 520),
    mime_type: UNICODE_STR,
    parser_override_json: deepNested(6),
  });
}

export function buildListUploadsResponse(
  overrides?: Partial<{ items: WorkbenchUploadSession[]; total: number }>
) {
  return {
    items: [buildUploadSession(), buildUploadSession({ upload_id: "upload-002", filename: "report.docx" })],
    total: 2,
    ...overrides,
  };
}

export function buildListUploadsEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildListUploadsBoundaryResponse() {
  return {
    items: [
      buildUploadSession({
        filename: LOREM_600.slice(0, 520),
        mime_type: UNICODE_STR,
        parser_override_json: deepNested(6),
      }),
    ],
    total: 1,
  };
}

export function buildGetUploadResponse(overrides?: Partial<WorkbenchUploadSession>): WorkbenchUploadSession {
  return buildUploadSession(overrides);
}

export function buildGetUploadEmptyResponse(): WorkbenchUploadSession {
  return buildUploadSession({
    source_file_id: undefined,
    intake_job_id: undefined,
    parse_snapshot_id: undefined,
    ticket_id: undefined,
    parser_override_json: undefined,
    access_scope_json: null,
    error_message: null,
  });
}

export function buildGetUploadBoundaryResponse(): WorkbenchUploadSession {
  return buildUploadSession({
    filename: LOREM_600.slice(0, 520),
    mime_type: UNICODE_STR,
    parser_override_json: deepNested(6),
  });
}

// ── Tasks ──────────────────────────────────────────────────────────────

export function buildTaskView(overrides?: Partial<WorkbenchTaskView>): WorkbenchTaskView {
  return {
    upload_id: "upload-001",
    status: "published",
    progress_pct: 100,
    source_file_state: "ready",
    intake_job_state: "completed",
    parse_snapshot_state: "completed",
    ticket_state: "approved",
    published_document_state: "active",
    filename: "document.pdf",
    collection_id: "coll-001",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T01:00:00Z",
    ...overrides,
  };
}

export function buildListTasksResponse(
  overrides?: Partial<{ items: WorkbenchTaskView[]; total: number }>
) {
  return {
    items: [buildTaskView(), buildTaskView({ upload_id: "upload-002", filename: "report.docx" })],
    total: 2,
    ...overrides,
  };
}

export function buildListTasksEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildListTasksBoundaryResponse() {
  return {
    items: [
      buildTaskView({
        filename: LOREM_600.slice(0, 520),
        source_file_state: UNICODE_STR,
      }),
    ],
    total: 1,
  };
}

export function buildGetTaskResponse(overrides?: Partial<WorkbenchTaskView>): WorkbenchTaskView {
  return buildTaskView(overrides);
}

export function buildGetTaskEmptyResponse(): WorkbenchTaskView {
  return buildTaskView({
    source_file_state: undefined,
    intake_job_state: undefined,
    parse_snapshot_state: undefined,
    ticket_state: undefined,
    published_document_state: null,
  });
}

export function buildGetTaskBoundaryResponse(): WorkbenchTaskView {
  return buildTaskView({
    filename: LOREM_600.slice(0, 520),
    source_file_state: UNICODE_STR,
  });
}

// ── Tickets ────────────────────────────────────────────────────────────

export function buildTicketItem(overrides?: Partial<TicketItem>): TicketItem {
  return {
    ticket_id: "ticket-001",
    collection_id: "coll-001",
    status: "pending_review",
    title: "Review document.pdf",
    filename: "document.pdf",
    priority: "high",
    assignee_user_id: "user-001",
    doc_id: "doc-001",
    source_file_id: "sf-001",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T01:00:00Z",
    ...overrides,
  };
}

export function buildListTicketsResponse(
  overrides?: Partial<{ items: TicketItem[]; total: number }>
) {
  return {
    items: [buildTicketItem(), buildTicketItem({ ticket_id: "ticket-002", filename: "report.docx" })],
    total: 2,
    ...overrides,
  };
}

export function buildListTicketsEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildListTicketsBoundaryResponse() {
  return {
    items: [
      buildTicketItem({
        title: LOREM_600.slice(0, 520),
        filename: UNICODE_STR,
      }),
    ],
    total: 1,
  };
}

export function buildTicketDetail(overrides?: Partial<TicketDetail>): TicketDetail {
  return {
    ticket_id: "ticket-001",
    collection_id: "coll-001",
    status: "pending_review",
    doc_id: "doc-001",
    source_file_id: "sf-001",
    parse_snapshot_id: "ps-001",
    filename: "document.pdf",
    decision: null,
    decision_reason: null,
    decided_by: null,
    tenant_id: "tenant-001",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T01:00:00Z",
    failure_code: null,
    failure_stage: null,
    next_action: null,
    ...overrides,
  };
}

export function buildGetTicketResponse(overrides?: Partial<TicketDetail>): TicketDetail {
  return buildTicketDetail(overrides);
}

export function buildGetTicketEmptyResponse(): TicketDetail {
  return buildTicketDetail({
    doc_id: null,
    source_file_id: null,
    parse_snapshot_id: null,
    filename: null,
    decision: null,
    decision_reason: null,
    decided_by: null,
    updated_at: null,
    failure_code: null,
    failure_stage: null,
    next_action: null,
  });
}

export function buildGetTicketBoundaryResponse(): TicketDetail {
  return buildTicketDetail({
    filename: LOREM_600.slice(0, 520),
    decision_reason: UNICODE_STR,
  });
}

export function buildAgentReviewResponse(overrides?: Partial<AgentReviewView>): AgentReviewView {
  return {
    ticket_id: "ticket-001",
    decision: null,
    source_file_id: "sf-001",
    parse_snapshot_id: "ps-001",
    findings: [
      {
        finding_id: "finding-001",
        severity: "critical",
        category: "sensitive_data",
        problem_summary: "Contains PII in section 3",
        source_quote: "Name: John Doe, SSN: 123-45-6789",
        evidence_id: "ev-001",
        doc_id: "doc-001",
        source_file_id: "sf-001",
        parse_snapshot_id: "ps-001",
        page_from: 1,
        page_to: 1,
        state: "open",
        confidence: 0.95,
      },
      {
        finding_id: "finding-002",
        severity: "high",
        category: "formatting",
        problem_summary: "Malformed table detected",
        source_quote: "Table 1 has inconsistent columns",
        evidence_id: "ev-002",
        doc_id: "doc-001",
        source_file_id: "sf-001",
        parse_snapshot_id: "ps-001",
        page_from: 2,
        page_to: 2,
        state: "open",
        confidence: 0.87,
      },
    ],
    matched_count: 2,
    unmatched_count: 0,
    source: "projection",
    ...overrides,
  };
}

export function buildAgentReviewEmptyResponse(): AgentReviewView {
  return {
    ticket_id: "ticket-001",
    decision: null,
    source_file_id: null,
    parse_snapshot_id: null,
    findings: [],
    matched_count: 0,
    unmatched_count: 0,
    source: "projection",
  };
}

export function buildAgentReviewBoundaryResponse(): AgentReviewView {
  return {
    ticket_id: "ticket-001",
    decision: null,
    source_file_id: "sf-001",
    parse_snapshot_id: "ps-001",
    findings: [
      {
        finding_id: "finding-001",
        severity: "critical",
        category: UNICODE_STR,
        problem_summary: LOREM_600.slice(0, 520),
        source_quote: UNICODE_STR,
        evidence_id: "ev-001",
        doc_id: "doc-001",
        source_file_id: "sf-001",
        parse_snapshot_id: "ps-001",
        page_from: 1,
        page_to: 999,
        state: "open",
        confidence: 0.9999,
      },
    ],
    matched_count: 1,
    unmatched_count: 0,
    source: "projection",
  };
}

export function buildDecideTicketResponse(overrides?: Partial<TicketDecisionResult>): TicketDecisionResult {
  return {
    ticket_id: "ticket-001",
    status: "approved",
    decision: "APPROVE",
    ...overrides,
  };
}

export function buildDecideTicketEmptyResponse(): TicketDecisionResult {
  return { ticket_id: "ticket-001", status: "", decision: "" };
}

export function buildDecideTicketBoundaryResponse(): TicketDecisionResult {
  return {
    ticket_id: LOREM_600.slice(0, 520),
    status: UNICODE_STR,
    decision: UNICODE_STR,
  };
}

// ── Ticket Comments ────────────────────────────────────────────────────

function buildTicketComment(overrides?: Partial<TicketComment>): TicketComment {
  return {
    comment_id: "comment-001",
    ticket_id: "ticket-001",
    author_id: "user-001",
    author_name: "Administrator",
    author_email: "admin@example.com",
    content: "这条工单需要重点关注 PII 信息。",
    mentions: null,
    created_at: "2024-06-10T12:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

export function buildTicketCommentsResponse(
  overrides?: Partial<{ items: TicketComment[]; total: number }>
) {
  return {
    items: [
      buildTicketComment(),
      buildTicketComment({
        comment_id: "comment-002",
        author_id: "user-002",
        author_name: "Reviewer",
        author_email: "reviewer@example.com",
        content: "@user-001 已确认，建议在第 3 页补充说明。",
        mentions: ["user-001"],
        created_at: "2024-06-10T13:00:00Z",
      }),
    ],
    total: 2,
    ...overrides,
  };
}

export function buildTicketCommentsEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildTicketCommentsBoundaryResponse() {
  return {
    items: [
      buildTicketComment({
        comment_id: LOREM_600.slice(0, 520),
        author_name: LOREM_600.slice(0, 520),
        content: UNICODE_STR,
      }),
    ],
    total: 1,
  };
}

export function buildCreateTicketCommentResponse(overrides?: Partial<TicketComment>): TicketComment {
  return {
    comment_id: "comment-new",
    ticket_id: "ticket-001",
    author_id: "user-001",
    author_name: "Administrator",
    author_email: "admin@example.com",
    content: "New comment",
    mentions: null,
    created_at: "2024-06-10T14:00:00Z",
    updated_at: "2024-06-10T14:00:00Z",
    ...overrides,
  };
}

// ── Trash ──────────────────────────────────────────────────────────────

export function buildTrashItem(overrides?: Partial<TrashItem>): TrashItem {
  return {
    doc_id: "doc-002",
    tenant_id: "tenant-001",
    collection_id: "coll-001",
    filename: "trashed-report.docx",
    source_file_id: "sf-002",
    deleted_by: "user-001",
    deleted_at: "2024-06-09T12:00:00Z",
    auto_purge_at: "2024-07-09T12:00:00Z",
    ...overrides,
  };
}

export function buildTrashListResponse(
  overrides?: Partial<{ items: TrashItem[]; total: number }>
) {
  return {
    items: [
      buildTrashItem(),
      buildTrashItem({
        doc_id: "doc-003",
        filename: "old-presentation.pptx",
        source_file_id: "sf-003",
        deleted_at: "2024-06-08T12:00:00Z",
      }),
    ],
    total: 2,
    ...overrides,
  };
}

export function buildTrashListEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildTrashListBoundaryResponse() {
  return {
    items: [
      buildTrashItem({
        doc_id: LOREM_600.slice(0, 520),
        filename: UNICODE_STR,
        collection_id: LOREM_600.slice(0, 300),
      }),
    ],
    total: 1,
  };
}

// ── Chunks ─────────────────────────────────────────────────────────────

export function buildChunkResponse(overrides?: Partial<Record<string, unknown>>) {
  return {
    evidence_id: "ev-001",
    doc_id: "doc-001",
    content: "This is the chunk content extracted from the document.",
    vector_text: "vector representation text",
    section_path: ["Section 1", "Subsection 1.1"],
    page_spans: [{ page_from: 1, page_to: 1 }],
    chunk_type: "text",
    metadata: { language: "en", confidence: 0.95 },
    ...overrides,
  };
}

export function buildChunkEmptyResponse() {
  return {
    evidence_id: "ev-001",
    doc_id: "doc-001",
    content: "",
    metadata: {},
  };
}

export function buildChunkBoundaryResponse() {
  return {
    evidence_id: "ev-001",
    doc_id: "doc-001",
    content: LOREM_600.slice(0, 520),
    vector_text: UNICODE_STR,
    section_path: [UNICODE_STR, LOREM_600.slice(0, 100)],
    page_spans: [{ page_from: 1, page_to: 9999 }],
    chunk_type: UNICODE_STR,
    metadata: deepNested(6),
  };
}

export function buildPatchChunkResponse(overrides?: Partial<Record<string, unknown>>) {
  return buildChunkResponse(overrides);
}

export function buildPatchChunkEmptyResponse() {
  return buildChunkEmptyResponse();
}

export function buildPatchChunkBoundaryResponse() {
  return buildChunkBoundaryResponse();
}

// ── Parse Snapshots ────────────────────────────────────────────────────

export function buildParseSnapshot(overrides?: Partial<ParseSnapshotView>): ParseSnapshotView {
  return {
    parse_snapshot_id: "ps-001",
    source_file_id: "sf-001",
    tenant_id: "tenant-001",
    collection_id: "coll-001",
    source_binary_ref: "ref-001",
    source_filename: "document.pdf",
    source_suffix: "pdf",
    parser_id: "deepdoc",
    parser_backend: "python",
    parser_profile_id: "parser-default",
    effective_policy: "standard",
    decision_reason: "Parsed successfully",
    preview_text: "Document preview text...",
    document_metadata: { title: "Document", author: "Author" },
    outline: [{ level: 1, title: "Introduction" }, { level: 2, title: "Background" }],
    chunk_preview: [{ evidence_id: "ev-001", preview: "Chunk preview..." }],
    warnings: [],
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

export function buildGetParseSnapshotResponse(overrides?: Partial<ParseSnapshotView>): ParseSnapshotView {
  return buildParseSnapshot(overrides);
}

export function buildGetParseSnapshotEmptyResponse(): ParseSnapshotView {
  return buildParseSnapshot({
    tenant_id: undefined,
    collection_id: undefined,
    source_binary_ref: undefined,
    source_filename: undefined,
    source_suffix: undefined,
    parser_id: undefined,
    parser_backend: undefined,
    parser_profile_id: undefined,
    effective_policy: undefined,
    decision_reason: undefined,
    preview_text: undefined,
    document_metadata: undefined,
    outline: [],
    chunk_preview: [],
    warnings: [],
    created_at: null,
  });
}

export function buildGetParseSnapshotBoundaryResponse(): ParseSnapshotView {
  return buildParseSnapshot({
    source_filename: LOREM_600.slice(0, 520),
    preview_text: UNICODE_STR,
    document_metadata: deepNested(6),
    outline: [{ level: 1, title: UNICODE_STR, nested: { a: { b: { c: { d: { e: "deep" } } } } } }],
    warnings: [LOREM_600.slice(0, 300), UNICODE_STR],
  });
}

export function buildParseSnapshotChunksResponse(
  overrides?: Partial<{ items: ChunkView[]; total: number }>
) {
  return {
    items: [
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: "First chunk content",
        vector_text: "vector text 1",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        chunk_type: "text",
        metadata: { key: "value" },
      },
      {
        evidence_id: "ev-002",
        doc_id: "doc-001",
        content: "Second chunk content",
        vector_text: "vector text 2",
        section_path: ["Section 2"],
        page_spans: [{ page_from: 2, page_to: 2 }],
        chunk_type: "text",
        metadata: { key: "value2" },
      },
    ],
    total: 2,
    ...overrides,
  };
}

export function buildParseSnapshotChunksEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildParseSnapshotChunksBoundaryResponse() {
  return {
    items: [
      {
        evidence_id: "ev-001",
        doc_id: "doc-001",
        content: LOREM_600.slice(0, 520),
        vector_text: UNICODE_STR,
        section_path: [UNICODE_STR, LOREM_600.slice(0, 100)],
        page_spans: [{ page_from: 1, page_to: 9999 }],
        chunk_type: UNICODE_STR,
        metadata: deepNested(6),
      },
    ],
    total: 1,
  };
}

export function buildListChunkEditsResponse(
  overrides?: Partial<{ items: Array<Record<string, unknown>>; total: number }>
) {
  return {
    items: [
      {
        chunk_edit_id: "ce-001",
        base_evidence_id: "ev-001",
        operation: "update_content",
        edit_reason: "Fixed typo",
        edited_by: "user-001",
        status: "applied",
        created_at: "2024-01-01T00:00:00Z",
      },
    ],
    total: 1,
    ...overrides,
  };
}

export function buildListChunkEditsEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildListChunkEditsBoundaryResponse() {
  return {
    items: [
      {
        chunk_edit_id: "ce-001",
        base_evidence_id: "ev-001",
        operation: UNICODE_STR,
        edit_reason: LOREM_600.slice(0, 520),
        edited_by: "user-001",
        status: UNICODE_STR,
        metadata: deepNested(6),
        created_at: "2024-01-01T00:00:00Z",
      },
    ],
    total: 1,
  };
}

// ── Documents ──────────────────────────────────────────────────────────

export function buildDocumentProjection(overrides?: Partial<DocumentProjectionItem>): DocumentProjectionItem {
  return {
    doc_id: "doc-001",
    tenant_id: "tenant-001",
    collection_id: "coll-001",
    source_file_id: "sf-001",
    parse_snapshot_id: "ps-001",
    published_doc_id: "pub-001",
    upload_id: "upload-001",
    filename: "document.pdf",
    mime_type: "application/pdf",
    document_state: "active",
    publish_state: "published",
    active_index_version: "v1",
    chunk_count: 42,
    page_count: 10,
    parser_profile_id: "parser-default",
    parser_profile_name: "Standard Parser",
    projection_updated_at: "2024-01-01T01:00:00Z",
    is_stale: false,
    degraded_reason: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T01:00:00Z",
    ticket_id: "ticket-001",
    ticket_status: "approved",
    task_status: "completed",
    has_source_file: true,
    has_parse_snapshot: true,
    has_active_index: true,
    latest_updated_at: "2024-01-01T01:00:00Z",
    ...overrides,
  };
}

export function buildListDocumentsResponse(
  overrides?: Partial<{ items: DocumentProjectionItem[]; total: number }>
) {
  return {
    items: [buildDocumentProjection(), buildDocumentProjection({ doc_id: "doc-002", filename: "report.docx" })],
    total: 2,
    ...overrides,
  };
}

export function buildListDocumentsEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildListDocumentsBoundaryResponse() {
  return {
    items: [
      buildDocumentProjection({
        filename: LOREM_600.slice(0, 520),
        mime_type: UNICODE_STR,
        degraded_reason: LOREM_600.slice(0, 300),
      }),
    ],
    total: 1,
  };
}

export function buildGetDocumentResponse(overrides?: Partial<DocumentProjectionItem>): DocumentProjectionItem {
  return buildDocumentProjection(overrides);
}

export function buildGetDocumentEmptyResponse(): DocumentProjectionItem {
  return buildDocumentProjection({
    source_file_id: null,
    parse_snapshot_id: null,
    published_doc_id: null,
    upload_id: null,
    filename: null,
    mime_type: null,
    document_state: null,
    publish_state: null,
    active_index_version: null,
    parser_profile_id: null,
    parser_profile_name: null,
    projection_updated_at: null,
    degraded_reason: null,
    created_at: null,
    updated_at: null,
    ticket_id: null,
    ticket_status: null,
    task_status: null,
    latest_updated_at: null,
  });
}

export function buildGetDocumentBoundaryResponse(): DocumentProjectionItem {
  return buildDocumentProjection({
    filename: LOREM_600.slice(0, 520),
    mime_type: UNICODE_STR,
    degraded_reason: UNICODE_STR,
  });
}

export function buildDocumentWorkspaceResponse(overrides?: Partial<WorkspaceDetailView>): WorkspaceDetailView {
  return {
    ticket_id: "ticket-001",
    ticket: {
      ticket_id: "ticket-001",
      collection_id: "coll-001",
      status: "pending_review",
      tenant_id: "tenant-001",
      doc_id: "doc-001",
      source_file_id: "sf-001",
      parse_snapshot_id: "ps-001",
      upload_id: "upload-001",
      title: "Review document.pdf",
      filename: "document.pdf",
      priority: "high",
      assignee_user_id: "user-001",
      decision: null,
      decision_reason: null,
      decided_by: null,
      agent_decision: null,
      agent_risk_level: "medium",
      agent_finding_count: 2,
      agent_blocking_finding_count: 1,
      failure_code: null,
      failure_stage: null,
      next_action: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T01:00:00Z",
      projection_updated_at: "2024-01-01T01:00:00Z",
      is_stale: false,
      source: "projection",
    },
    document: {
      doc_id: "doc-001",
      tenant_id: "tenant-001",
      collection_id: "coll-001",
      source_file_id: "sf-001",
      parse_snapshot_id: "ps-001",
      published_doc_id: "pub-001",
      upload_id: "upload-001",
      filename: "document.pdf",
      mime_type: "application/pdf",
      document_state: "active",
      publish_state: "published",
      active_index_version: "v1",
      chunk_count: 42,
      page_count: 10,
      parser_profile_id: "parser-default",
      parser_profile_name: "Standard Parser",
      projection_updated_at: "2024-01-01T01:00:00Z",
      is_stale: false,
      degraded_reason: null,
      linkage_source: "document_projection",
    },
    task: {
      upload_id: "upload-001",
      collection_id: "coll-001",
      status: "published",
      filename: "document.pdf",
      source_file_id: "sf-001",
      intake_job_id: "job-001",
      parse_snapshot_id: "ps-001",
      ticket_id: "ticket-001",
      published_doc_id: "pub-001",
      doc_id: "doc-001",
      progress_pct: 100,
      source_file_state: "ready",
      intake_job_state: "completed",
      parse_snapshot_state: "completed",
      ticket_state: "approved",
      published_document_state: "active",
      index_build_state: "completed",
      active_index_version: "v1",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T01:00:00Z",
      projection_updated_at: "2024-01-01T01:00:00Z",
      is_stale: false,
    },
    source_file: {
      source_file_id: "sf-001",
      upload_id: "upload-001",
      tenant_id: "tenant-001",
      collection_id: "coll-001",
      filename: "document.pdf",
      mime_type: "application/pdf",
      size_bytes: 1024000,
      state: "ready",
      intake_job_id: "job-001",
      scan_verdict: "clean",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T01:00:00Z",
    },
    parse_snapshot: {
      parse_snapshot_id: "ps-001",
      source_file_id: "sf-001",
      tenant_id: "tenant-001",
      collection_id: "coll-001",
      source_filename: "document.pdf",
      source_suffix: "pdf",
      parser_id: "deepdoc",
      parser_backend: "python",
      parser_profile_id: "parser-default",
      effective_policy: "standard",
      decision_reason: "Parsed successfully",
      preview_text: "Preview...",
      warnings: [],
      created_at: "2024-01-01T00:00:00Z",
    },
    chunks: {
      items: [
        {
          evidence_id: "ev-001",
          doc_id: "doc-001",
          content: "Chunk content 1",
          vector_text: "vector 1",
          section_path: ["Section 1"],
          page_spans: [{ page_from: 1, page_to: 1 }],
          chunk_type: "text",
          metadata: {},
        },
      ],
      total: 1,
    },
    chunk_edits: {
      items: [],
      total: 0,
    },
    agent_review: {
      ticket_id: "ticket-001",
      decision: null,
      source_file_id: "sf-001",
      parse_snapshot_id: "ps-001",
      findings: [],
      matched_count: 0,
      unmatched_count: 0,
      source: "projection",
    },
    capabilities: {
      can_view_source: true,
      can_view_parsed_text: true,
      can_search_in_document: true,
      can_edit_drafts: true,
      can_jump_to_chunk: true,
      can_decide_ticket: true,
      can_approve: true,
      can_reject: true,
      can_upload: true,
      can_archive: true,
      can_retract: true,
      can_reindex: true,
    },
    projection_freshness: {
      ticket_projection_updated_at: "2024-01-01T01:00:00Z",
      ticket_is_stale: false,
      document_projection_updated_at: "2024-01-01T01:00:00Z",
      document_is_stale: false,
    },
    degraded_parts: [],
    trace_id: "trace-001",
    ...overrides,
  };
}

export function buildDocumentWorkspaceEmptyResponse(): WorkspaceDetailView {
  return buildDocumentWorkspaceResponse({
    ticket: null,
    task: null,
    source_file: null,
    parse_snapshot: null,
    chunks: { items: [], total: 0 },
    chunk_edits: { items: [], total: 0 },
    agent_review: {
      ticket_id: "ticket-001",
      decision: null,
      source_file_id: null,
      parse_snapshot_id: null,
      findings: [],
      matched_count: 0,
      unmatched_count: 0,
      source: "missing",
    },
    degraded_parts: [],
  });
}

export function buildDocumentWorkspaceBoundaryResponse(): WorkspaceDetailView {
  return buildDocumentWorkspaceResponse({
    ticket: {
      ...buildDocumentWorkspaceResponse().ticket!,
      title: LOREM_600.slice(0, 520),
      filename: UNICODE_STR,
    },
    document: {
      ...buildDocumentWorkspaceResponse().document,
      filename: LOREM_600.slice(0, 520),
      mime_type: UNICODE_STR,
    },
    chunks: {
      items: [
        {
          evidence_id: "ev-001",
          doc_id: "doc-001",
          content: LOREM_600.slice(0, 520),
          vector_text: UNICODE_STR,
          section_path: [UNICODE_STR],
          page_spans: [{ page_from: 1, page_to: 9999 }],
          chunk_type: UNICODE_STR,
          metadata: deepNested(6),
        },
      ],
      total: 1,
    },
    degraded_parts: [LOREM_600.slice(0, 300), UNICODE_STR],
  });
}

export function buildArchiveDocumentResponse(overrides?: Partial<DocumentLifecycleActionResult>): DocumentLifecycleActionResult {
  return {
    success: true,
    final_doc_id: "doc-001",
    previous_state: "active",
    new_state: "archived",
    job_id: "job-archive-001",
    ...overrides,
  };
}

export function buildArchiveDocumentEmptyResponse(): DocumentLifecycleActionResult {
  return { success: true, final_doc_id: "doc-001" };
}

export function buildArchiveDocumentBoundaryResponse(): DocumentLifecycleActionResult {
  return {
    success: true,
    final_doc_id: LOREM_600.slice(0, 520),
    previous_state: UNICODE_STR,
    new_state: UNICODE_STR,
    job_id: LOREM_600.slice(0, 300),
  };
}

export function buildRetractDocumentResponse(overrides?: Partial<DocumentLifecycleActionResult>): DocumentLifecycleActionResult {
  return {
    success: true,
    final_doc_id: "doc-001",
    previous_state: "active",
    new_state: "retracted",
    job_id: "job-retract-001",
    ...overrides,
  };
}

export function buildRetractDocumentEmptyResponse(): DocumentLifecycleActionResult {
  return { success: true, final_doc_id: "doc-001" };
}

export function buildRetractDocumentBoundaryResponse(): DocumentLifecycleActionResult {
  return {
    success: true,
    final_doc_id: LOREM_600.slice(0, 520),
    previous_state: UNICODE_STR,
    new_state: UNICODE_STR,
    job_id: LOREM_600.slice(0, 300),
  };
}

export function buildReindexDocumentResponse(overrides?: Partial<DocumentLifecycleActionResult>): DocumentLifecycleActionResult {
  return {
    success: true,
    final_doc_id: "doc-001",
    previous_state: "active",
    new_state: "active",
    job_id: "job-reindex-001",
    ...overrides,
  };
}

export function buildReindexDocumentEmptyResponse(): DocumentLifecycleActionResult {
  return { success: true, final_doc_id: "doc-001" };
}

export function buildReindexDocumentBoundaryResponse(): DocumentLifecycleActionResult {
  return {
    success: true,
    final_doc_id: LOREM_600.slice(0, 520),
    previous_state: UNICODE_STR,
    new_state: UNICODE_STR,
    job_id: LOREM_600.slice(0, 300),
  };
}

export function buildBatchArchiveResponse(overrides?: Partial<BatchDocumentActionResult>): BatchDocumentActionResult {
  return {
    total: 2,
    succeeded: 2,
    failed: 0,
    items: [
      { doc_id: "doc-001", success: true, previous_state: "active", new_state: "archived", job_id: "job-001" },
      { doc_id: "doc-002", success: true, previous_state: "active", new_state: "archived", job_id: "job-002" },
    ],
    ...overrides,
  };
}

export function buildBatchArchiveEmptyResponse(): BatchDocumentActionResult {
  return { total: 0, succeeded: 0, failed: 0, items: [] };
}

export function buildBatchArchiveBoundaryResponse(): BatchDocumentActionResult {
  return {
    total: 1,
    succeeded: 0,
    failed: 1,
    items: [
      {
        doc_id: LOREM_600.slice(0, 520),
        success: false,
        previous_state: UNICODE_STR,
        new_state: UNICODE_STR,
        job_id: LOREM_600.slice(0, 300),
        error_code: UNICODE_STR,
        error_message: LOREM_600.slice(0, 520),
      },
    ],
  };
}

export function buildBatchRetractResponse(overrides?: Partial<BatchDocumentActionResult>): BatchDocumentActionResult {
  return {
    total: 2,
    succeeded: 2,
    failed: 0,
    items: [
      { doc_id: "doc-001", success: true, previous_state: "active", new_state: "retracted", job_id: "job-001" },
      { doc_id: "doc-002", success: true, previous_state: "active", new_state: "retracted", job_id: "job-002" },
    ],
    ...overrides,
  };
}

export function buildBatchRetractEmptyResponse(): BatchDocumentActionResult {
  return { total: 0, succeeded: 0, failed: 0, items: [] };
}

export function buildBatchRetractBoundaryResponse(): BatchDocumentActionResult {
  return {
    total: 1,
    succeeded: 0,
    failed: 1,
    items: [
      {
        doc_id: LOREM_600.slice(0, 520),
        success: false,
        previous_state: UNICODE_STR,
        new_state: UNICODE_STR,
        job_id: LOREM_600.slice(0, 300),
        error_code: UNICODE_STR,
        error_message: LOREM_600.slice(0, 520),
      },
    ],
  };
}

export function buildBatchReindexResponse(overrides?: Partial<BatchDocumentActionResult>): BatchDocumentActionResult {
  return {
    total: 2,
    succeeded: 2,
    failed: 0,
    items: [
      { doc_id: "doc-001", success: true, previous_state: "active", new_state: "active", job_id: "job-001" },
      { doc_id: "doc-002", success: true, previous_state: "active", new_state: "active", job_id: "job-002" },
    ],
    ...overrides,
  };
}

export function buildBatchReindexEmptyResponse(): BatchDocumentActionResult {
  return { total: 0, succeeded: 0, failed: 0, items: [] };
}

export function buildBatchReindexBoundaryResponse(): BatchDocumentActionResult {
  return {
    total: 1,
    succeeded: 0,
    failed: 1,
    items: [
      {
        doc_id: LOREM_600.slice(0, 520),
        success: false,
        previous_state: UNICODE_STR,
        new_state: UNICODE_STR,
        job_id: LOREM_600.slice(0, 300),
        error_code: UNICODE_STR,
        error_message: LOREM_600.slice(0, 520),
      },
    ],
  };
}

// ── Source Files ───────────────────────────────────────────────────────

export function buildSourceFilePreviewResponse(overrides?: Partial<SourceFilePreviewView>): SourceFilePreviewView {
  return {
    source_file_id: "sf-001",
    collection_id: "coll-001",
    filename: "document.pdf",
    mime_type: "application/pdf",
    page_count: 10,
    preview_available: true,
    preview_status: "ready",
    preview_kind: "pdf",
    preview_mime_type: "application/pdf",
    preview_url: "/api/preview/sf-001",
    thumbnail_url: "/api/thumbnail/sf-001",
    ...overrides,
  };
}

export function buildSourceFilePreviewEmptyResponse(): SourceFilePreviewView {
  return {
    source_file_id: "sf-001",
    collection_id: "coll-001",
    filename: "document.pdf",
    mime_type: "application/pdf",
    page_count: null,
    preview_available: false,
    preview_status: null,
    preview_kind: null,
    preview_mime_type: null,
    preview_url: null,
    thumbnail_url: null,
  };
}

export function buildSourceFilePreviewBoundaryResponse(): SourceFilePreviewView {
  return {
    source_file_id: "sf-001",
    collection_id: "coll-001",
    filename: LOREM_600.slice(0, 520),
    mime_type: UNICODE_STR,
    page_count: 99999,
    preview_available: true,
    preview_status: UNICODE_STR,
    preview_kind: UNICODE_STR,
    preview_mime_type: UNICODE_STR,
    preview_url: LOREM_600.slice(0, 300),
    thumbnail_url: LOREM_600.slice(0, 300),
  };
}

export function buildSourceFilePreviewBlobResponse() {
  return new Uint8Array([37, 80, 68, 70, 45, 49, 46, 52]).buffer;
}

export function buildParseSnapshotSourceBlobResponse() {
  return new Uint8Array([37, 80, 68, 70, 45, 49, 46, 52]).buffer;
}

// ── Workspace Detail ───────────────────────────────────────────────────

export function buildWorkspaceDetailResponse(overrides?: Partial<WorkspaceDetailView>): WorkspaceDetailView {
  return buildDocumentWorkspaceResponse(overrides);
}

export function buildWorkspaceDetailEmptyResponse(): WorkspaceDetailView {
  return buildDocumentWorkspaceEmptyResponse();
}

export function buildWorkspaceDetailBoundaryResponse(): WorkspaceDetailView {
  return buildDocumentWorkspaceBoundaryResponse();
}

// ── Dashboard ──────────────────────────────────────────────────────────

export function buildDashboardResponse(
  overrides?: Partial<{
    stats: {
      today_uploads: number;
      pending_review_count: number;
      total_documents: number;
      stale_ratio: number;
    };
    recent_tickets: TicketItem[];
  }>
) {
  return {
    stats: {
      today_uploads: 12,
      pending_review_count: 3,
      total_documents: 147,
      stale_ratio: 0.08,
    },
    recent_tickets: [
      buildTicketItem({ ticket_id: "ticket-001", title: "Review document.pdf", filename: "document.pdf" }),
      buildTicketItem({ ticket_id: "ticket-002", title: "Review report.docx", filename: "report.docx" }),
      buildTicketItem({ ticket_id: "ticket-003", title: "Review slides.pptx", filename: "slides.pptx" }),
    ],
    ...overrides,
  };
}

export function buildDashboardEmptyResponse() {
  return {
    stats: {
      today_uploads: 0,
      pending_review_count: 0,
      total_documents: 0,
      stale_ratio: 0,
    },
    recent_tickets: [],
  };
}

export function buildDashboardBoundaryResponse() {
  return {
    stats: {
      today_uploads: 999999999,
      pending_review_count: 999999999,
      total_documents: 999999999,
      stale_ratio: 0.999999,
    },
    recent_tickets: [
      buildTicketItem({
        ticket_id: "ticket-001",
        title: LOREM_600.slice(0, 520),
        filename: UNICODE_STR,
      }),
    ],
  };
}

// ── Retrieve ───────────────────────────────────────────────────────────

export function buildRetrieveResponse(
  overrides?: Partial<{
    query_run_id: string;
    knowledge_context: Record<string, unknown>;
    latency_ms: number;
    trace_id: string;
    evidence_items: Array<Record<string, unknown>>;
    token_budget_used: number;
  }>
) {
  return {
    query_run_id: "qr-001",
    knowledge_context: {
      query_id: "q-001",
      tenant_id: "tenant-001",
      index_version_used: ["v1"],
      collection_plans_used: [{ collection_id: "coll-001", plan: "standard" }],
      evidence_items: [],
      grouped_sources: [],
      citations: [],
      token_budget_used: 500,
    },
    latency_ms: 245,
    trace_id: "trace-001",
    evidence_items: [
      {
        collection_id: "coll-001",
        doc_id: "doc-001",
        evidence_id: "ev-001",
        document_index_revision_id: "rev-001",
        content: "Retrieved evidence content from document.",
        section_path: ["Section 1"],
        page_spans: [{ page_from: 1, page_to: 1 }],
        score: 0.95,
        source_stage: "index",
        why_selected: "High semantic similarity",
      },
    ],
    token_budget_used: 500,
    ...overrides,
  };
}

export function buildRetrieveEmptyResponse() {
  return {
    query_run_id: "qr-001",
    knowledge_context: {},
    latency_ms: 0,
    trace_id: "trace-001",
    evidence_items: [],
    token_budget_used: 0,
  };
}

export function buildRetrieveBoundaryResponse() {
  return {
    query_run_id: LOREM_600.slice(0, 520),
    knowledge_context: deepNested(6),
    latency_ms: 999999,
    trace_id: UNICODE_STR,
    evidence_items: [
      {
        collection_id: "coll-001",
        doc_id: "doc-001",
        evidence_id: "ev-001",
        document_index_revision_id: "rev-001",
        content: LOREM_600.slice(0, 520),
        section_path: [UNICODE_STR, LOREM_600.slice(0, 100)],
        page_spans: [{ page_from: 1, page_to: 9999 }],
        score: 0.9999,
        source_stage: UNICODE_STR,
        why_selected: LOREM_600.slice(0, 520),
        metadata: deepNested(6),
      },
    ],
    token_budget_used: 999999,
  };
}

// ── Query Runs ─────────────────────────────────────────────────────────

export function buildQueryRunsResponse(
  overrides?: Partial<{
    items: Array<{
      query_run_id: string;
      query: string;
      collection_id: string;
      retrieval_profile_id: string;
      created_at: string;
      latency_ms?: number;
    }>;
    total: number;
  }>
) {
  return {
    items: [
      {
        query_run_id: "qr-001",
        query: "产品功能介绍",
        collection_id: "coll-001",
        retrieval_profile_id: "rp-001",
        created_at: "2024-06-10T12:00:00Z",
        latency_ms: 245,
      },
      {
        query_run_id: "qr-002",
        query: "安全合规要求",
        collection_id: "coll-001",
        retrieval_profile_id: "rp-002",
        created_at: "2024-06-10T11:00:00Z",
        latency_ms: 189,
      },
      {
        query_run_id: "qr-003",
        query: "API 使用文档",
        collection_id: "coll-002",
        retrieval_profile_id: "rp-001",
        created_at: "2024-06-10T10:00:00Z",
        latency_ms: 312,
      },
    ],
    total: 3,
    ...overrides,
  };
}

export function buildQueryRunsEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildQueryRunsBoundaryResponse() {
  return {
    items: [
      {
        query_run_id: LOREM_600.slice(0, 520),
        query: UNICODE_STR,
        collection_id: LOREM_600.slice(0, 300),
        retrieval_profile_id: LOREM_600.slice(0, 300),
        created_at: "2099-12-31T23:59:59Z",
        latency_ms: 999999,
      },
    ],
    total: 999999,
  };
}

// ── Notifications ──────────────────────────────────────────────────────

function buildNotificationItem(
  overrides?: Partial<{
    notification_id: string;
    type: "ticket_status_change" | "chunk_edit_conflict" | "quota_warning" | "system_maintenance";
    title: string;
    message: string;
    link?: string;
    is_read: boolean;
    created_at: string;
  }>
) {
  return {
    notification_id: "notif-001",
    type: "ticket_status_change" as const,
    title: "Ticket status changed",
    message: "Your ticket ticket-001 has been approved.",
    link: "/workbench/tickets/ticket-001",
    is_read: false,
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

export function buildNotificationsResponse(
  overrides?: Partial<{ items: Array<Record<string, unknown>>; total: number; unread_count: number }>
) {
  return {
    items: [
      buildNotificationItem(),
      buildNotificationItem({
        notification_id: "notif-002",
        type: "chunk_edit_conflict",
        title: "Chunk edit conflict detected",
        message: "A conflict was found in chunk ev-001.",
        link: "/workbench/documents/doc-001",
        is_read: true,
        created_at: "2024-01-02T00:00:00Z",
      }),
      buildNotificationItem({
        notification_id: "notif-003",
        type: "quota_warning",
        title: "Storage quota warning",
        message: "You have used 90% of your storage quota.",
        is_read: false,
        created_at: "2024-01-03T00:00:00Z",
      }),
      buildNotificationItem({
        notification_id: "notif-004",
        type: "system_maintenance",
        title: "Scheduled maintenance",
        message: "System maintenance is scheduled for tonight.",
        is_read: true,
        created_at: "2024-01-04T00:00:00Z",
      }),
    ],
    total: 4,
    unread_count: 2,
    ...overrides,
  };
}

export function buildNotificationsEmptyResponse() {
  return { items: [], total: 0, unread_count: 0 };
}

export function buildNotificationsBoundaryResponse() {
  return {
    items: [
      buildNotificationItem({
        notification_id: LOREM_600.slice(0, 520),
        type: "system_maintenance",
        title: LOREM_600.slice(0, 520),
        message: UNICODE_STR,
        link: LOREM_600.slice(0, 300),
        is_read: false,
        created_at: "2099-12-31T23:59:59Z",
      }),
    ],
    total: 999999,
    unread_count: 999999,
  };
}

export function buildMarkNotificationReadResponse(
  overrides?: Partial<{ notification_id: string; is_read: boolean; read_at: string }>
) {
  return {
    notification_id: "notif-001",
    is_read: true,
    read_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

export function buildMarkNotificationReadEmptyResponse() {
  return { notification_id: "notif-001", is_read: true };
}

export function buildMarkNotificationReadBoundaryResponse() {
  return {
    notification_id: LOREM_600.slice(0, 520),
    is_read: true,
    read_at: "2099-12-31T23:59:59Z",
  };
}

export function buildReadAllNotificationsResponse(
  overrides?: Partial<{ updated_count: number; updated_ids: string[] }>
) {
  return {
    updated_count: 4,
    updated_ids: ["notif-001", "notif-002", "notif-003", "notif-004"],
    ...overrides,
  };
}

export function buildReadAllNotificationsEmptyResponse() {
  return { updated_count: 0, updated_ids: [] };
}

export function buildReadAllNotificationsBoundaryResponse() {
  return {
    updated_count: 999999,
    updated_ids: [LOREM_600.slice(0, 520), UNICODE_STR],
  };
}

export function buildUnreadCountResponse(overrides?: Partial<{ count: number }>) {
  return { count: 2, ...overrides };
}

export function buildUnreadCountEmptyResponse() {
  return { count: 0 };
}

export function buildUnreadCountBoundaryResponse() {
  return { count: 999999 };
}

// ── Retrieval Profile Detail ───────────────────────────────────────────

export function buildRetrievalProfileDetailResponse(
  overrides?: Partial<{
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
  }>
) {
  return {
    retrieval_profile_id: "rp-001",
    name: "Standard",
    state: "published" as const,
    description: "Standard retrieval configuration",
    config: {
      rerank_model: "default",
      top_k: 10,
      similarity_threshold: 0.75,
      token_budget_limit: 4096,
      metadata_filters: { language: "en" },
    },
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    ...overrides,
  };
}

export function buildRetrievalProfileDetailEmptyResponse() {
  return {
    retrieval_profile_id: "rp-001",
    name: "",
    state: "draft" as const,
    config: {},
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };
}

export function buildRetrievalProfileDetailBoundaryResponse() {
  return {
    retrieval_profile_id: LOREM_600.slice(0, 520),
    name: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    description: UNICODE_STR,
    config: deepNested(6),
    created_at: "2099-12-31T23:59:59Z",
    updated_at: "2099-12-31T23:59:59Z",
  };
}

export function buildCreateRetrievalProfileResponse(
  overrides?: Partial<{
    retrieval_profile_id: string;
    name: string;
    state: "draft" | "published";
    created_at: string;
  }>
) {
  return {
    retrieval_profile_id: "rp-new",
    name: "New Retrieval Profile",
    state: "draft" as const,
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

export function buildCreateRetrievalProfileEmptyResponse() {
  return {
    retrieval_profile_id: "rp-new",
    name: "",
    state: "draft" as const,
    created_at: "2024-01-01T00:00:00Z",
  };
}

export function buildCreateRetrievalProfileBoundaryResponse() {
  return {
    retrieval_profile_id: LOREM_600.slice(0, 520),
    name: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    created_at: "2099-12-31T23:59:59Z",
    metadata: deepNested(6),
  };
}

export function buildUpdateRetrievalProfileResponse(
  overrides?: Partial<{
    retrieval_profile_id: string;
    name: string;
    state: "draft" | "published";
    updated_at: string;
  }>
) {
  return {
    retrieval_profile_id: "rp-001",
    name: "Updated Standard",
    state: "published" as const,
    updated_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

export function buildUpdateRetrievalProfileEmptyResponse() {
  return {
    retrieval_profile_id: "rp-001",
    name: "",
    state: "draft" as const,
    updated_at: "2024-01-01T00:00:00Z",
  };
}

export function buildUpdateRetrievalProfileBoundaryResponse() {
  return {
    retrieval_profile_id: LOREM_600.slice(0, 520),
    name: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    updated_at: "2099-12-31T23:59:59Z",
    metadata: deepNested(6),
  };
}

export function buildDeleteRetrievalProfileResponse(
  overrides?: Partial<{
    retrieval_profile_id: string;
    deleted: boolean;
  }>
) {
  return {
    retrieval_profile_id: "rp-001",
    deleted: true,
    ...overrides,
  };
}

export function buildDeleteRetrievalProfileEmptyResponse() {
  return {
    retrieval_profile_id: "rp-001",
    deleted: true,
  };
}

export function buildDeleteRetrievalProfileBoundaryResponse() {
  return {
    retrieval_profile_id: LOREM_600.slice(0, 520),
    deleted: false,
    reason: UNICODE_STR,
  };
}

export function buildPublishRetrievalProfileResponse(
  overrides?: Partial<{
    retrieval_profile_id: string;
    state: "draft" | "published";
    published_at: string;
  }>
) {
  return {
    retrieval_profile_id: "rp-001",
    state: "published" as const,
    published_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

export function buildPublishRetrievalProfileEmptyResponse() {
  return {
    retrieval_profile_id: "rp-001",
    state: "published" as const,
  };
}

export function buildPublishRetrievalProfileBoundaryResponse() {
  return {
    retrieval_profile_id: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    published_at: "2099-12-31T23:59:59Z",
    metadata: deepNested(6),
  };
}

export function buildCloneRetrievalProfileResponse(
  overrides?: Partial<{
    source_retrieval_profile_id: string;
    retrieval_profile_id: string;
    name: string;
    state: "draft" | "published";
    created_at: string;
  }>
) {
  return {
    source_retrieval_profile_id: "rp-001",
    retrieval_profile_id: "rp-clone-001",
    name: "Standard (Copy)",
    state: "draft" as const,
    created_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

export function buildCloneRetrievalProfileEmptyResponse() {
  return {
    source_retrieval_profile_id: "rp-001",
    retrieval_profile_id: "rp-clone-001",
    name: "",
    state: "draft" as const,
    created_at: "2024-06-10T12:00:00Z",
  };
}

export function buildCloneRetrievalProfileBoundaryResponse() {
  return {
    source_retrieval_profile_id: LOREM_600.slice(0, 520),
    retrieval_profile_id: LOREM_600.slice(0, 520),
    name: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    created_at: "2099-12-31T23:59:59Z",
    metadata: deepNested(6),
  };
}

// ── Parser Profiles ────────────────────────────────────────────────────

export function buildParserProfilesResponse(
  overrides?: Partial<{ items: Array<Record<string, unknown>>; total: number }>
) {
  return {
    items: [
      { parser_profile_id: "pp-001", name: "Standard", state: "published", parser_id: "deepdoc", is_default: true },
      { parser_profile_id: "pp-002", name: "Aggressive", state: "published", parser_id: "deepdoc", is_default: false },
    ],
    total: 2,
    ...overrides,
  };
}

export function buildParserProfilesEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildParserProfilesBoundaryResponse() {
  return {
    items: [
      {
        parser_profile_id: "pp-001",
        name: LOREM_600.slice(0, 520),
        state: UNICODE_STR,
        parser_id: LOREM_600.slice(0, 520),
        is_default: false,
      },
    ],
    total: 1,
  };
}

export function buildParserProfileDetailResponse(
  overrides?: Partial<{
    parser_profile_id: string;
    name: string;
    state: "draft" | "published";
    description?: string;
    parser_id?: string;
    config?: Record<string, unknown>;
    created_at: string;
    updated_at: string;
  }>
) {
  return {
    parser_profile_id: "pp-001",
    name: "Standard",
    state: "published" as const,
    description: "Standard parser configuration",
    parser_id: "deepdoc",
    config: { ocr: true, table_detection: false, language: "en" },
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    ...overrides,
  };
}

export function buildParserProfileDetailEmptyResponse() {
  return {
    parser_profile_id: "pp-001",
    name: "",
    state: "draft" as const,
    config: {},
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };
}

export function buildParserProfileDetailBoundaryResponse() {
  return {
    parser_profile_id: LOREM_600.slice(0, 520),
    name: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    description: UNICODE_STR,
    parser_id: LOREM_600.slice(0, 520),
    config: deepNested(6),
    created_at: "2099-12-31T23:59:59Z",
    updated_at: "2099-12-31T23:59:59Z",
  };
}

export function buildCreateParserProfileResponse(
  overrides?: Partial<{
    parser_profile_id: string;
    name: string;
    state: "draft" | "published";
    created_at: string;
  }>
) {
  return {
    parser_profile_id: "pp-new",
    name: "New Parser Profile",
    state: "draft" as const,
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

export function buildCreateParserProfileEmptyResponse() {
  return {
    parser_profile_id: "pp-new",
    name: "",
    state: "draft" as const,
    created_at: "2024-01-01T00:00:00Z",
  };
}

export function buildCreateParserProfileBoundaryResponse() {
  return {
    parser_profile_id: LOREM_600.slice(0, 520),
    name: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    created_at: "2099-12-31T23:59:59Z",
    metadata: deepNested(6),
  };
}

export function buildUpdateParserProfileResponse(
  overrides?: Partial<{
    parser_profile_id: string;
    name: string;
    state: "draft" | "published";
    updated_at: string;
  }>
) {
  return {
    parser_profile_id: "pp-001",
    name: "Updated Standard",
    state: "published" as const,
    updated_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

export function buildUpdateParserProfileEmptyResponse() {
  return {
    parser_profile_id: "pp-001",
    name: "",
    state: "draft" as const,
    updated_at: "2024-01-01T00:00:00Z",
  };
}

export function buildUpdateParserProfileBoundaryResponse() {
  return {
    parser_profile_id: LOREM_600.slice(0, 520),
    name: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    updated_at: "2099-12-31T23:59:59Z",
    metadata: deepNested(6),
  };
}

export function buildDeleteParserProfileResponse(
  overrides?: Partial<{
    parser_profile_id: string;
    deleted: boolean;
  }>
) {
  return {
    parser_profile_id: "pp-001",
    deleted: true,
    ...overrides,
  };
}

export function buildDeleteParserProfileEmptyResponse() {
  return {
    parser_profile_id: "pp-001",
    deleted: true,
  };
}

export function buildDeleteParserProfileBoundaryResponse() {
  return {
    parser_profile_id: LOREM_600.slice(0, 520),
    deleted: false,
    reason: UNICODE_STR,
  };
}

export function buildPublishParserProfileResponse(
  overrides?: Partial<{
    parser_profile_id: string;
    state: "draft" | "published";
    published_at: string;
  }>
) {
  return {
    parser_profile_id: "pp-001",
    state: "published" as const,
    published_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

export function buildPublishParserProfileEmptyResponse() {
  return {
    parser_profile_id: "pp-001",
    state: "published" as const,
  };
}

export function buildPublishParserProfileBoundaryResponse() {
  return {
    parser_profile_id: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    published_at: "2099-12-31T23:59:59Z",
    metadata: deepNested(6),
  };
}

export function buildCloneParserProfileResponse(
  overrides?: Partial<{
    source_parser_profile_id: string;
    parser_profile_id: string;
    name: string;
    state: "draft" | "published";
    created_at: string;
  }>
) {
  return {
    source_parser_profile_id: "pp-001",
    parser_profile_id: "pp-clone-001",
    name: "Standard (Copy)",
    state: "draft" as const,
    created_at: "2024-06-10T12:00:00Z",
    ...overrides,
  };
}

export function buildCloneParserProfileEmptyResponse() {
  return {
    source_parser_profile_id: "pp-001",
    parser_profile_id: "pp-clone-001",
    name: "",
    state: "draft" as const,
    created_at: "2024-06-10T12:00:00Z",
  };
}

export function buildCloneParserProfileBoundaryResponse() {
  return {
    source_parser_profile_id: LOREM_600.slice(0, 520),
    parser_profile_id: LOREM_600.slice(0, 520),
    name: LOREM_600.slice(0, 520),
    state: UNICODE_STR,
    created_at: "2099-12-31T23:59:59Z",
    metadata: deepNested(6),
  };
}

// ── Audit Logs ─────────────────────────────────────────────────────────

function buildAuditLogItem(
  overrides?: Partial<{
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
  }>
) {
  return {
    log_id: "log-001",
    operator_id: "user-001",
    operator_email: "admin@example.com",
    operation_type: "upload" as const,
    target_type: "document" as const,
    target_id: "doc-001",
    collection_id: "coll-001",
    timestamp: "2024-06-10T12:00:00Z",
    ip_address: "192.168.1.1",
    details: { filename: "document.pdf", mime_type: "application/pdf" },
    before_snapshot: undefined,
    after_snapshot: { doc_id: "doc-001", state: "active" },
    ...overrides,
  };
}

export function buildAuditLogsResponse(
  overrides?: Partial<{ items: Array<Record<string, unknown>>; total: number; page: number; page_size: number }>
) {
  return {
    items: [
      buildAuditLogItem(),
      buildAuditLogItem({
        log_id: "log-002",
        operation_type: "approve",
        target_type: "ticket",
        target_id: "ticket-001",
        operator_id: "user-002",
        operator_email: "reviewer@example.com",
        timestamp: "2024-06-10T13:00:00Z",
        ip_address: "192.168.1.2",
        details: { decision: "APPROVE", reason: "Looks good" },
        before_snapshot: { status: "pending_review" },
        after_snapshot: { status: "approved" },
      }),
      buildAuditLogItem({
        log_id: "log-003",
        operation_type: "edit_chunk",
        target_type: "chunk",
        target_id: "ev-001",
        operator_id: "user-001",
        operator_email: "admin@example.com",
        timestamp: "2024-06-10T14:00:00Z",
        ip_address: "192.168.1.1",
        details: { edit_reason: "Fixed typo" },
        before_snapshot: { content: "Old content" },
        after_snapshot: { content: "Updated content" },
      }),
    ],
    total: 3,
    page: 1,
    page_size: 20,
    ...overrides,
  };
}

export function buildAuditLogsEmptyResponse() {
  return { items: [], total: 0, page: 1, page_size: 20 };
}

export function buildAuditLogsBoundaryResponse() {
  return {
    items: [
      buildAuditLogItem({
        log_id: LOREM_600.slice(0, 520),
        operator_email: LOREM_600.slice(0, 520),
        operation_type: UNICODE_STR as unknown as "upload",
        target_type: UNICODE_STR as unknown as "document",
        target_id: LOREM_600.slice(0, 520),
        collection_id: LOREM_600.slice(0, 520),
        timestamp: "2099-12-31T23:59:59Z",
        ip_address: UNICODE_STR,
        details: deepNested(6),
        before_snapshot: deepNested(6),
        after_snapshot: deepNested(6),
      }),
    ],
    total: 999999,
    page: 999999,
    page_size: 999999,
  };
}

export function buildExportAuditLogsResponse(overrides?: Partial<{ download_url: string }>) {
  return {
    download_url: "/api/workbench/audit-logs/export/download?file=audit-logs-2024-06-10.csv",
    ...overrides,
  };
}

export function buildExportAuditLogsEmptyResponse() {
  return { download_url: "" };
}

export function buildExportAuditLogsBoundaryResponse() {
  return { download_url: LOREM_600.slice(0, 520) };
}

// ── API Keys ───────────────────────────────────────────────────────────

export function buildApiKeysResponse() {
  return {
    items: [
      {
        api_key_id: "ak-001",
        name: "Production API Key",
        key_prefix: "ak_prod...",
        state: "active",
        permissions: ["read", "search"],
        collection_ids: ["coll-001"],
        expires_at: "2025-12-31T23:59:59Z",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-06-01T00:00:00Z",
        last_used_at: "2024-06-10T12:00:00Z",
      },
      {
        api_key_id: "ak-002",
        name: "Development API Key",
        key_prefix: "ak_dev...",
        state: "active",
        permissions: ["read", "search", "upload"],
        collection_ids: ["coll-001", "coll-002"],
        expires_at: null,
        created_at: "2024-03-01T00:00:00Z",
        updated_at: "2024-03-01T00:00:00Z",
        last_used_at: null,
      },
    ],
    total: 2,
  };
}

export function buildApiKeysEmptyResponse() {
  return { items: [], total: 0 };
}

export function buildApiKeysBoundaryResponse() {
  return {
    items: [
      {
        api_key_id: "ak-" + "x".repeat(120),
        name: LOREM_600.slice(0, 200),
        key_prefix: LOREM_600.slice(0, 50),
        state: UNICODE_STR,
        permissions: [UNICODE_STR, LOREM_600.slice(0, 100)],
        collection_ids: ["coll-001", "coll-002", "coll-003", "coll-004", "coll-005"],
        expires_at: "2099-12-31T23:59:59Z",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-06-01T00:00:00Z",
        last_used_at: "2024-06-10T12:00:00Z",
      },
    ],
    total: 1,
  };
}

export function buildApiKeyDetailResponse() {
  return {
    api_key_id: "ak-001",
    name: "Production API Key",
    key_prefix: "ak_prod...",
    state: "active",
    permissions: ["read", "search"],
    collection_ids: ["coll-001"],
    expires_at: "2025-12-31T23:59:59Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    last_used_at: "2024-06-10T12:00:00Z",
  };
}

export function buildApiKeyDetailEmptyResponse() {
  return {
    api_key_id: "ak-001",
    name: "",
    key_prefix: "",
    state: "active",
    permissions: [],
    collection_ids: [],
    expires_at: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    last_used_at: null,
  };
}

export function buildApiKeyDetailBoundaryResponse() {
  return {
    api_key_id: "ak-" + "x".repeat(120),
    name: LOREM_600.slice(0, 200),
    key_prefix: LOREM_600.slice(0, 50),
    state: UNICODE_STR,
    permissions: [UNICODE_STR, LOREM_600.slice(0, 100)],
    collection_ids: ["coll-001", "coll-002", "coll-003", "coll-004", "coll-005"],
    expires_at: "2099-12-31T23:59:59Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    last_used_at: "2024-06-10T12:00:00Z",
  };
}

export function buildCreateApiKeyResponse() {
  return {
    api_key_id: "ak-new-001",
    name: "New API Key",
    key_prefix: "ak_new...",
    full_key: "ak_new_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    state: "active",
    permissions: ["read"],
    collection_ids: ["coll-001"],
    expires_at: null,
    created_at: "2024-06-10T12:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    last_used_at: null,
  };
}

export function buildCreateApiKeyEmptyResponse() {
  return {
    api_key_id: "ak-new-001",
    name: "",
    key_prefix: "",
    full_key: "",
    state: "active",
    permissions: [],
    collection_ids: [],
    expires_at: null,
    created_at: "2024-06-10T12:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    last_used_at: null,
  };
}

export function buildCreateApiKeyBoundaryResponse() {
  return {
    api_key_id: "ak-" + "x".repeat(120),
    name: LOREM_600.slice(0, 200),
    key_prefix: LOREM_600.slice(0, 50),
    full_key: LOREM_600.slice(0, 300),
    state: UNICODE_STR,
    permissions: [UNICODE_STR],
    collection_ids: ["coll-001"],
    expires_at: "2099-12-31T23:59:59Z",
    created_at: "2024-06-10T12:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    last_used_at: null,
  };
}

export function buildUpdateApiKeyResponse() {
  return {
    api_key_id: "ak-001",
    name: "Updated API Key",
    key_prefix: "ak_prod...",
    state: "active",
    permissions: ["read", "search", "upload"],
    collection_ids: ["coll-001", "coll-002"],
    expires_at: "2025-12-31T23:59:59Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    last_used_at: "2024-06-10T12:00:00Z",
  };
}

export function buildUpdateApiKeyEmptyResponse() {
  return {
    api_key_id: "ak-001",
    name: "",
    key_prefix: "",
    state: "active",
    permissions: [],
    collection_ids: [],
    expires_at: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    last_used_at: null,
  };
}

export function buildUpdateApiKeyBoundaryResponse() {
  return {
    api_key_id: "ak-" + "x".repeat(120),
    name: LOREM_600.slice(0, 200),
    key_prefix: LOREM_600.slice(0, 50),
    state: UNICODE_STR,
    permissions: [UNICODE_STR, LOREM_600.slice(0, 100)],
    collection_ids: ["coll-001", "coll-002", "coll-003", "coll-004", "coll-005"],
    expires_at: "2099-12-31T23:59:59Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-06-10T12:00:00Z",
    last_used_at: "2024-06-10T12:00:00Z",
  };
}

export function buildDeleteApiKeyResponse() {
  return { api_key_id: "ak-001", deleted: true };
}

export function buildDeleteApiKeyEmptyResponse() {
  return { api_key_id: "", deleted: false };
}

export function buildDeleteApiKeyBoundaryResponse() {
  return { api_key_id: "ak-" + "x".repeat(120), deleted: true };
}

export function buildApiKeyUsageResponse() {
  return {
    api_key_id: "ak-001",
    total_requests: 15420,
    total_tokens: 3847500,
    qps_peak: 45.2,
    last_used_at: "2024-06-10T12:00:00Z",
    daily_stats: [
      { date: "2024-06-08", requests: 5200, tokens: 1250000 },
      { date: "2024-06-09", requests: 4800, tokens: 1100000 },
      { date: "2024-06-10", requests: 5420, tokens: 1497500 },
    ],
  };
}

export function buildApiKeyUsageEmptyResponse() {
  return {
    api_key_id: "ak-001",
    total_requests: 0,
    total_tokens: 0,
    qps_peak: 0,
    last_used_at: null,
    daily_stats: [],
  };
}

export function buildApiKeyUsageBoundaryResponse() {
  return {
    api_key_id: "ak-" + "x".repeat(120),
    total_requests: 999999999,
    total_tokens: 999999999999,
    qps_peak: 99999.99,
    last_used_at: "2099-12-31T23:59:59Z",
    daily_stats: Array.from({ length: 365 }, (_, i) => ({
      date: `2024-01-${String(i + 1).padStart(2, "0")}`,
      requests: 999999,
      tokens: 99999999,
    })),
  };
}

// ── Handlers ───────────────────────────────────────────────────────────

export const handlers = [
  // health
  http.get("*/api/workbench/health", () => HttpResponse.json(buildHealthResponse())),

  // healthAll
  http.get("*/api/workbench/health/all", () => HttpResponse.json(buildHealthAllResponse())),

  // dashboard
  http.get("*/api/workbench/dashboard", () => HttpResponse.json(buildDashboardResponse())),

  // me
  http.get("*/api/workbench/auth/me", () => HttpResponse.json(buildMeResponse())),

  // listCollections
  http.get("*/api/workbench/collections", () => HttpResponse.json(buildCollectionListResponse())),

  // createCollection
  http.post("*/api/workbench/collections", () => HttpResponse.json(buildCreateCollectionResponse())),

  // listRetrievalProfiles
  http.get("*/api/workbench/retrieval-profiles", () => HttpResponse.json(buildRetrievalProfilesResponse())),

  // createUpload
  http.post("*/api/workbench/uploads", () => HttpResponse.json(buildCreateUploadResponse())),

  // uploadFileContent
  http.post("*/api/workbench/uploads/:upload_id/content", () =>
    HttpResponse.json(buildUploadFileContentResponse())
  ),

  // listUploads
  http.get("*/api/workbench/uploads", () => HttpResponse.json(buildListUploadsResponse())),

  // getUpload
  http.get("*/api/workbench/uploads/:upload_id", () => HttpResponse.json(buildGetUploadResponse())),

  // listTasks
  http.get("*/api/workbench/tasks", () => HttpResponse.json(buildListTasksResponse())),

  // getTask
  http.get("*/api/workbench/tasks/:upload_id", () => HttpResponse.json(buildGetTaskResponse())),

  // listTickets
  http.get("*/api/workbench/tickets", () => HttpResponse.json(buildListTicketsResponse())),

  // getTicket
  http.get("*/api/workbench/tickets/:ticket_id", () => HttpResponse.json(buildGetTicketResponse())),

  // getAgentReview
  http.get("*/api/workbench/tickets/:ticket_id/agent-review", () =>
    HttpResponse.json(buildAgentReviewResponse())
  ),

  // decideTicket
  http.post("*/api/workbench/tickets/:ticket_id/decide", () =>
    HttpResponse.json(buildDecideTicketResponse())
  ),

  // listTicketComments
  http.get("*/api/workbench/tickets/:ticket_id/comments", () =>
    HttpResponse.json(buildTicketCommentsResponse())
  ),

  // createTicketComment
  http.post("*/api/workbench/tickets/:ticket_id/comments", async ({ request }) => {
    const body = (await request.json()) as { content?: string };
    return HttpResponse.json(
      buildCreateTicketCommentResponse({ content: body?.content || "New comment" })
    );
  }),

  // updateTicketComment
  http.patch("*/api/workbench/comments/:comment_id", async ({ request }) => {
    const body = (await request.json()) as { content?: string };
    return HttpResponse.json(
      buildCreateTicketCommentResponse({
        comment_id: "comment-updated",
        content: body?.content || "Updated comment",
        updated_at: "2024-06-10T15:00:00Z",
      })
    );
  }),

  // deleteTicketComment
  http.delete("*/api/workbench/comments/:comment_id", () => new HttpResponse(null, { status: 204 })),

  // listTrashItems
  http.get("*/api/workbench/trash", () => HttpResponse.json(buildTrashListResponse())),

  // restoreDocument
  http.post("*/api/workbench/trash/:doc_id/restore", () => HttpResponse.json({ doc_id: "doc-002", restored: true })),

  // permanentlyDeleteDocument
  http.delete("*/api/workbench/trash/:doc_id", () => new HttpResponse(null, { status: 204 })),

  // getChunk
  http.get("*/api/workbench/chunks/:evidence_id", () => HttpResponse.json(buildChunkResponse())),

  // patchChunk
  http.patch("*/api/workbench/chunks/:evidence_id", () => HttpResponse.json(buildPatchChunkResponse())),

  // getParseSnapshot
  http.get("*/api/workbench/parse-snapshots/:id", () => HttpResponse.json(buildGetParseSnapshotResponse())),

  // getParseSnapshotChunks
  http.get("*/api/workbench/parse-snapshots/:id/chunks", () =>
    HttpResponse.json(buildParseSnapshotChunksResponse())
  ),

  // listChunkEdits
  http.get("*/api/workbench/chunk-edits", () => HttpResponse.json(buildListChunkEditsResponse())),

  // listDocuments
  http.get("*/api/workbench/documents", () => HttpResponse.json(buildListDocumentsResponse())),

  // getDocument
  http.get("*/api/workbench/documents/:doc_id", () => HttpResponse.json(buildGetDocumentResponse())),

  // getDocumentWorkspace
  http.get("*/api/workbench/documents/:doc_id/workspace", () =>
    HttpResponse.json(buildDocumentWorkspaceResponse())
  ),

  // archiveDocument
  http.post("*/api/workbench/documents/:doc_id/archive", () =>
    HttpResponse.json(buildArchiveDocumentResponse())
  ),

  // retractDocument
  http.post("*/api/workbench/documents/:doc_id/retract", () =>
    HttpResponse.json(buildRetractDocumentResponse())
  ),

  // reindexDocument
  http.post("*/api/workbench/documents/:doc_id/reindex", () =>
    HttpResponse.json(buildReindexDocumentResponse())
  ),

  // batchArchiveDocuments
  http.post("*/api/workbench/documents/batch/archive", () =>
    HttpResponse.json(buildBatchArchiveResponse())
  ),

  // batchRetractDocuments
  http.post("*/api/workbench/documents/batch/retract", () =>
    HttpResponse.json(buildBatchRetractResponse())
  ),

  // batchReindexDocuments
  http.post("*/api/workbench/documents/batch/reindex", () =>
    HttpResponse.json(buildBatchReindexResponse())
  ),

  // getSourceFilePreview
  http.get("*/api/workbench/source-files/:source_file_id/preview", () =>
    HttpResponse.json(buildSourceFilePreviewResponse())
  ),

  // getSourceFilePreviewBlob
  http.get("*/api/workbench/source-files/:source_file_id/preview/content", () =>
    HttpResponse.arrayBuffer(buildSourceFilePreviewBlobResponse(), {
      headers: { "Content-Type": "application/pdf" },
    })
  ),

  // getParseSnapshotSourceBlob
  http.get("*/api/workbench/parse-snapshots/:parse_snapshot_id/source", () =>
    HttpResponse.arrayBuffer(buildParseSnapshotSourceBlobResponse(), {
      headers: { "Content-Type": "application/pdf" },
    })
  ),

  // getWorkspaceDetail
  http.get("*/api/workbench/tickets/:ticket_id/workspace", () =>
    HttpResponse.json(buildWorkspaceDetailResponse())
  ),

  // retrieve
  http.post("*/api/workbench/retrieve", () => HttpResponse.json(buildRetrieveResponse())),

  // listQueryRuns
  http.get("*/api/workbench/query-runs", () => HttpResponse.json(buildQueryRunsResponse())),

  // listNotifications
  http.get("*/api/workbench/notifications", () => HttpResponse.json(buildNotificationsResponse())),

  // markNotificationRead
  http.patch("*/api/workbench/notifications/:id/read", () => HttpResponse.json(buildMarkNotificationReadResponse())),

  // readAllNotifications
  http.post("*/api/workbench/notifications/read-all", () => HttpResponse.json(buildReadAllNotificationsResponse())),

  // getUnreadCount
  http.get("*/api/workbench/notifications/unread-count", () => HttpResponse.json(buildUnreadCountResponse())),

  // getRetrievalProfileDetail
  http.get("*/api/workbench/retrieval-profiles/:id", () =>
    HttpResponse.json(buildRetrievalProfileDetailResponse())
  ),

  // createRetrievalProfile
  http.post("*/api/workbench/retrieval-profiles", () =>
    HttpResponse.json(buildCreateRetrievalProfileResponse())
  ),

  // updateRetrievalProfile
  http.patch("*/api/workbench/retrieval-profiles/:id", () =>
    HttpResponse.json(buildUpdateRetrievalProfileResponse())
  ),

  // deleteRetrievalProfile
  http.delete("*/api/workbench/retrieval-profiles/:id", () =>
    HttpResponse.json(buildDeleteRetrievalProfileResponse())
  ),

  // publishRetrievalProfile
  http.post("*/api/workbench/retrieval-profiles/:id/publish", () =>
    HttpResponse.json(buildPublishRetrievalProfileResponse())
  ),

  // cloneRetrievalProfile
  http.post("*/api/workbench/retrieval-profiles/:id/clone", () =>
    HttpResponse.json(buildCloneRetrievalProfileResponse())
  ),

  // listParserProfiles
  http.get("*/api/workbench/parser-profiles", () => HttpResponse.json(buildParserProfilesResponse())),

  // getParserProfileDetail
  http.get("*/api/workbench/parser-profiles/:id", () => HttpResponse.json(buildParserProfileDetailResponse())),

  // createParserProfile
  http.post("*/api/workbench/parser-profiles", () => HttpResponse.json(buildCreateParserProfileResponse())),

  // updateParserProfile
  http.patch("*/api/workbench/parser-profiles/:id", () => HttpResponse.json(buildUpdateParserProfileResponse())),

  // deleteParserProfile
  http.delete("*/api/workbench/parser-profiles/:id", () => HttpResponse.json(buildDeleteParserProfileResponse())),

  // publishParserProfile
  http.post("*/api/workbench/parser-profiles/:id/publish", () =>
    HttpResponse.json(buildPublishParserProfileResponse())
  ),

  // cloneParserProfile
  http.post("*/api/workbench/parser-profiles/:id/clone", () =>
    HttpResponse.json(buildCloneParserProfileResponse())
  ),

  // listAuditLogs
  http.get("*/api/workbench/audit-logs", () => HttpResponse.json(buildAuditLogsResponse())),

  // exportAuditLogs
  http.post("*/api/workbench/audit-logs/export", () => HttpResponse.json(buildExportAuditLogsResponse())),

  // listApiKeys
  http.get("*/api/workbench/api-keys", () => HttpResponse.json(buildApiKeysResponse())),

  // createApiKey
  http.post("*/api/workbench/api-keys", () => HttpResponse.json(buildCreateApiKeyResponse())),

  // getApiKeyDetail
  http.get("*/api/workbench/api-keys/:id", () => HttpResponse.json(buildApiKeyDetailResponse())),

  // updateApiKey
  http.patch("*/api/workbench/api-keys/:id", () => HttpResponse.json(buildUpdateApiKeyResponse())),

  // deleteApiKey
  http.delete("*/api/workbench/api-keys/:id", () => HttpResponse.json(buildDeleteApiKeyResponse())),

  // getApiKeyUsage
  http.get("*/api/workbench/api-keys/:id/usage", () => HttpResponse.json(buildApiKeyUsageResponse())),
];
