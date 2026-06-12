import type {
  CollectionListResponse,
  DocumentProjectionItem,
  WorkbenchTaskView,
  WorkbenchUploadSession,
  TicketItem,
  TicketDetail,
  TicketDecisionResult,
  AgentReviewView,
  ChunkView,
  ParseSnapshotView,
  SourceFilePreviewView,
  WorkspaceDetailView,
  DocumentWorkspaceDetailView,
  DocumentLifecycleActionRequest,
  DocumentLifecycleActionResult,
  BatchDocumentActionRequest,
  BatchDocumentActionResult,
  DashboardResponse,
  NotificationListResponse,
  RetrievalProfileDetail,
  ParserProfileDetail,
  AuditLogListResponse,
  ApiKeyItem,
  ApiKeyDetail,
  TicketComment,
  TicketCommentListResponse,
  TrashItem,
  TrashListResponse,
  ApiKeyUsage,
} from "./types";
import { ApiClientError, BackendGapError } from "./errors";
import { useAppStore } from "@/lib/store";

const WORKBENCH_BASE =
  process.env.NEXT_PUBLIC_WORKBENCH_API_BASE_URL ||
  process.env.NEXT_PUBLIC_WORKBENCH_API_URL ||
  "/api/workbench";
const DEFAULT_REQUEST_TIMEOUT_MS = Number(
  process.env.NEXT_PUBLIC_WORKBENCH_REQUEST_TIMEOUT_MS || "15000"
);
const UPLOAD_REQUEST_TIMEOUT_MS = Number(
  process.env.NEXT_PUBLIC_WORKBENCH_UPLOAD_TIMEOUT_MS || "120000"
);
const WORKBENCH_AUTH_COOKIE = "ekb_workbench_token";

function buildTimeoutError(timeoutMs: number) {
  return new ApiClientError(
    "REQUEST_TIMEOUT",
    `Request timed out after ${timeoutMs / 1000}s`,
    408
  );
}

async function fetchWithTimeout(
  input: URL | string,
  init: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw buildTimeoutError(timeoutMs);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function syncWorkbenchAuthCookie(token?: string) {
  if (typeof document === "undefined") return;
  if (!token) {
    document.cookie = `${WORKBENCH_AUTH_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
    return;
  }
  document.cookie = `${WORKBENCH_AUTH_COOKIE}=${encodeURIComponent(token)}; Path=/; Max-Age=28800; SameSite=Lax`;
}

function getToken(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const storeToken = useAppStore.getState().demoToken;
  // Reject non-JWT values (e.g. legacy "123456") and fall back to env
  const token =
    storeToken && storeToken.split(".").length === 3
      ? storeToken
      : process.env.NEXT_PUBLIC_DEMO_TOKEN || undefined;
  syncWorkbenchAuthCookie(token);
  return token;
}

async function request<T>(
  base: string,
  path: string,
  options: RequestInit & {
    query?: Record<string, string | undefined>;
    timeoutMs?: number;
  } = {}
): Promise<T> {
  const { query, timeoutMs, ...requestInit } = options;
  const url = resolveUrl(base, path);
  if (query) {
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
  }

  const headers = new Headers(requestInit.headers);
  headers.set("Content-Type", "application/json");

  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetchWithTimeout(
    url.toString(),
    {
      ...requestInit,
      headers,
    },
    timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS
  );

  if (res.status === 501) {
    throw new BackendGapError(
      `${requestInit.method || "GET"} ${path}`,
      `${base}${path}`,
      "Backend API returns 501 — not implemented"
    );
  }

  if (!res.ok) {
    let body: {
      code?: string;
      message?: string;
      detail?: string | { error_code?: string; message?: string };
    } = {};
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    const nestedDetail =
      body.detail && typeof body.detail === "object" ? body.detail : undefined;
    throw new ApiClientError(
      body.code || nestedDetail?.error_code || `HTTP_${res.status}`,
      body.message ||
        nestedDetail?.message ||
        (typeof body.detail === "string" ? body.detail : undefined) ||
        `HTTP ${res.status}`,
      res.status
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

function resolveUrl(base: string, path: string): URL {
  if (/^https?:\/\//i.test(base)) {
    return new URL(path, base);
  }

  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const basePrefix = normalizedBase.split("/").filter(Boolean).at(-1);
  const adjustedPath =
    basePrefix && normalizedPath.startsWith(`/${basePrefix}/`)
      ? normalizedPath.slice(basePrefix.length + 1)
      : normalizedPath;
  const origin =
    typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1";
  return new URL(`${normalizedBase}${adjustedPath}`, origin);
}

// ── Workbench API ──────────────────────────────────────────────────────

export const workbenchApi = {
  health: () =>
    request<{ service: string; status: string }>(
      WORKBENCH_BASE,
      "/workbench/health"
    ),
  healthAll: () =>
    request<{
      workbench: { status: string; service: string };
      services: Record<string, { status: string; service: string }>;
      all_healthy: boolean;
    }>(WORKBENCH_BASE, "/workbench/health/all"),
  me: () =>
    request<{
      user_id: string;
      email: string;
      display_name?: string;
      roles: string[];
      tenant_id: string;
      allowed_collections: string[];
    }>(WORKBENCH_BASE, "/workbench/auth/me"),
  listCollections: (tenant_id?: string) =>
    request<CollectionListResponse>(WORKBENCH_BASE, "/workbench/collections", {
      query: { tenant_id: tenant_id || "" },
    }),
  createCollection: (payload: {
    collection_id: string;
    tenant_id: string;
    name: string;
    description?: string;
    lifecycle_state: string;
    authority_level?: number;
    access_policy?: Record<string, unknown>;
  }) =>
    request<Record<string, unknown>>(WORKBENCH_BASE, "/workbench/collections", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCollection: (collection_id: string, payload: {
    name?: string;
    description?: string;
    lifecycle_state?: string;
  }) =>
    request<Record<string, unknown>>(WORKBENCH_BASE, `/workbench/collections/${collection_id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteCollection: (collection_id: string) =>
    request<{ status: string }>(WORKBENCH_BASE, `/workbench/collections/${collection_id}`, {
      method: "DELETE",
    }),
  listRetrievalProfiles: (state?: string) =>
    request<{ items: RetrievalProfileDetail[]; total: number }>(
      WORKBENCH_BASE,
      "/workbench/retrieval-profiles",
      { query: { state } }
    ),
  getRetrievalProfileDetail: (id: string) =>
    request<RetrievalProfileDetail>(WORKBENCH_BASE, `/workbench/retrieval-profiles/${id}`),
  createRetrievalProfile: (payload: {
    name: string;
    description?: string;
    config: Record<string, unknown>;
  }) =>
    request<RetrievalProfileDetail>(WORKBENCH_BASE, "/workbench/retrieval-profiles", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateRetrievalProfile: (id: string, payload: {
    name?: string;
    description?: string;
    config?: Record<string, unknown>;
  }) =>
    request<RetrievalProfileDetail>(WORKBENCH_BASE, `/workbench/retrieval-profiles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteRetrievalProfile: (id: string) =>
    request<void>(WORKBENCH_BASE, `/workbench/retrieval-profiles/${id}`, { method: "DELETE" }),
  publishRetrievalProfile: (id: string) =>
    request<RetrievalProfileDetail>(WORKBENCH_BASE, `/workbench/retrieval-profiles/${id}/publish`, { method: "POST" }),
  cloneRetrievalProfile: (id: string) =>
    request<RetrievalProfileDetail>(WORKBENCH_BASE, `/workbench/retrieval-profiles/${id}/clone`, { method: "POST" }),
  listParserProfiles: () =>
    request<{ items: ParserProfileDetail[]; total: number }>(
      WORKBENCH_BASE,
      "/workbench/parser-profiles"
    ),
  getParserProfileDetail: (id: string) =>
    request<ParserProfileDetail>(WORKBENCH_BASE, `/workbench/parser-profiles/${id}`),
  createParserProfile: (payload: {
    name: string;
    description?: string;
    parser_id?: string;
    config?: Record<string, unknown>;
  }) =>
    request<ParserProfileDetail>(WORKBENCH_BASE, "/workbench/parser-profiles", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateParserProfile: (id: string, payload: {
    name?: string;
    description?: string;
    parser_id?: string;
    config?: Record<string, unknown>;
  }) =>
    request<ParserProfileDetail>(WORKBENCH_BASE, `/workbench/parser-profiles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteParserProfile: (id: string) =>
    request<{ parser_profile_id: string; deleted: boolean }>(WORKBENCH_BASE, `/workbench/parser-profiles/${id}`, { method: "DELETE" }),
  publishParserProfile: (id: string) =>
    request<ParserProfileDetail>(WORKBENCH_BASE, `/workbench/parser-profiles/${id}/publish`, { method: "POST" }),
  cloneParserProfile: (id: string) =>
    request<ParserProfileDetail>(WORKBENCH_BASE, `/workbench/parser-profiles/${id}/clone`, { method: "POST" }),
  createUpload: (payload: {
    collection_id: string;
    filename: string;
    mime_type: string;
    size_bytes: number;
    selected_parser_profile_id?: string;
    parser_override_json?: Record<string, unknown>;
    access_scope_json?: Record<string, unknown> | null;
  }) =>
    request<Record<string, unknown>>(WORKBENCH_BASE, "/workbench/uploads", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS,
    }),
  uploadFileContent: async (
    upload_id: string,
    file: File,
    access_scope_json?: Record<string, unknown> | null
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    if (access_scope_json) {
      formData.append("access_scope_json", JSON.stringify(access_scope_json));
    }
    const url = resolveUrl(WORKBENCH_BASE, `/workbench/uploads/${upload_id}/content`);
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const res = await fetchWithTimeout(
      url.toString(),
      {
        method: "POST",
        body: formData,
        headers,
      },
      UPLOAD_REQUEST_TIMEOUT_MS
    );

    if (res.status === 501) {
      throw new BackendGapError(
        `POST /workbench/uploads/${upload_id}/content`,
        url.toString(),
        "Backend API returns 501 — not implemented"
      );
    }
    if (!res.ok) {
      let body: {
        code?: string;
        message?: string;
        detail?: string | { error_code?: string; message?: string };
      } = {};
      try {
        body = await res.json();
      } catch {
        /* ignore */
      }
      const nestedDetail =
        body.detail && typeof body.detail === "object" ? body.detail : undefined;
      throw new ApiClientError(
        body.code || nestedDetail?.error_code || `HTTP_${res.status}`,
        body.message ||
          nestedDetail?.message ||
          (typeof body.detail === "string" ? body.detail : undefined) ||
          `HTTP ${res.status}`,
        res.status
      );
    }
    return res.json() as Promise<WorkbenchUploadSession>;
  },
  listUploads: (opts?: { collection_id?: string; status?: string }) =>
    request<{ items: WorkbenchUploadSession[]; total: number }>(
      WORKBENCH_BASE,
      "/workbench/uploads",
      { query: opts }
    ),
  getUpload: (upload_id: string) =>
    request<WorkbenchUploadSession>(
      WORKBENCH_BASE,
      `/workbench/uploads/${upload_id}`
    ),
  cancelTask: (taskId: string) =>
    request<{ status: string; task_id: string }>(
      WORKBENCH_BASE,
      `/workbench/tasks/${taskId}/cancel`,
      { method: "POST" }
    ),
  listTasks: (opts?: {
    collection_id?: string; status?: string;
    offset?: number; limit?: number;
    sort_by?: string; sort_order?: string;
  }) => {
    const query: Record<string, string | undefined> = {};
    if (opts?.collection_id) query.collection_id = opts.collection_id;
    if (opts?.status) query.status = opts.status;
    if (opts?.offset !== undefined) query.offset = String(opts.offset);
    if (opts?.limit !== undefined) query.limit = String(opts.limit);
    if (opts?.sort_by) query.sort_by = opts.sort_by;
    if (opts?.sort_order) query.sort_order = opts.sort_order;
    return request<{ items: WorkbenchTaskView[]; total: number }>(
      WORKBENCH_BASE,
      "/workbench/tasks",
      { query }
    );
  },
  getTask: (upload_id: string) =>
    request<WorkbenchTaskView>(
      WORKBENCH_BASE,
      `/workbench/tasks/${upload_id}`
    ),
  listTickets: (opts?: {
    collection_id?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }) =>
    request<{ items: TicketItem[]; total: number }>(
      WORKBENCH_BASE,
      "/workbench/tickets",
      {
        query: opts
          ? Object.fromEntries(
              Object.entries(opts).map(([key, value]) => [key, value == null ? undefined : String(value)])
            )
          : undefined,
      }
    ),
  getTicket: (ticket_id: string) =>
    request<TicketDetail>(
      WORKBENCH_BASE,
      `/workbench/tickets/${ticket_id}`
    ),
  getAgentReview: (ticket_id: string) =>
    request<AgentReviewView>(
      WORKBENCH_BASE,
      `/workbench/tickets/${ticket_id}/agent-review`
    ),
  decideTicket: (
    ticket_id: string,
    payload: {
      decision_request_id: string;
      action: "APPROVE" | "REJECT" | "RETURN";
      reason?: string;
      tenant_id: string;
      collection_id: string;
    }
  ) =>
    request<TicketDecisionResult>(
      WORKBENCH_BASE,
      `/workbench/tickets/${ticket_id}/decide`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  listTicketComments: (ticket_id: string) =>
    request<TicketCommentListResponse>(
      WORKBENCH_BASE,
      `/workbench/tickets/${ticket_id}/comments`
    ),
  createTicketComment: (ticket_id: string, payload: { content: string }) =>
    request<TicketComment>(
      WORKBENCH_BASE,
      `/workbench/tickets/${ticket_id}/comments`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  updateTicketComment: (comment_id: string, payload: { content: string }) =>
    request<TicketComment>(
      WORKBENCH_BASE,
      `/workbench/comments/${comment_id}`,
      { method: "PATCH", body: JSON.stringify(payload) }
    ),
  deleteTicketComment: (comment_id: string) =>
    request<void>(
      WORKBENCH_BASE,
      `/workbench/comments/${comment_id}`,
      { method: "DELETE" }
    ),
  transferTicket: (ticket_id: string, payload: { assignee_user_id: string; reason?: string }) =>
    request<TicketDetail>(
      WORKBENCH_BASE,
      `/workbench/tickets/${ticket_id}/transfer`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  shareDocument: (doc_id: string, payload: { expires_in_hours?: number; password?: string }) =>
    request<{ share_url: string; expires_at: string }>(
      WORKBENCH_BASE,
      `/workbench/documents/${doc_id}/share`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  listTrashItems: () =>
    request<TrashListResponse>(WORKBENCH_BASE, "/workbench/trash"),
  restoreDocument: (doc_id: string) =>
    request<{ doc_id: string; restored: boolean }>(
      WORKBENCH_BASE,
      `/workbench/trash/${doc_id}/restore`,
      { method: "POST" }
    ),
  permanentlyDeleteDocument: (doc_id: string) =>
    request<void>(
      WORKBENCH_BASE,
      `/workbench/trash/${doc_id}`,
      { method: "DELETE" }
    ),
  getChunk: (evidence_id: string) =>
    request<Record<string, unknown>>(
      WORKBENCH_BASE,
      `/workbench/chunks/${evidence_id}`
    ),
  patchChunk: <T = Record<string, unknown>>(evidence_id: string, payload: T) =>
    request<T>(
      WORKBENCH_BASE,
      `/workbench/chunks/${evidence_id}`,
      { method: "PATCH", body: JSON.stringify(payload) }
    ),
  getParseSnapshot: (id: string) =>
    request<ParseSnapshotView>(
      WORKBENCH_BASE,
      `/workbench/parse-snapshots/${id}`
    ),
  getParseSnapshotChunks: (id: string, page?: number, page_size?: number) =>
    request<{ items: ChunkView[]; total: number }>(
      WORKBENCH_BASE,
      `/workbench/parse-snapshots/${id}/chunks`,
      { query: { page: String(page || 1), page_size: String(page_size || 50) } }
    ),
  listChunkEdits: (parse_snapshot_id: string) =>
    request<{ items: Array<Record<string, unknown>>; total: number }>(
      WORKBENCH_BASE,
      `/workbench/chunk-edits`,
      { query: { parse_snapshot_id } }
    ),
  listDocuments: (opts?: {
    collection_id?: string;
    document_state?: string;
    status?: string;
    offset?: number;
    limit?: number;
    order_by?: string;
    order_dir?: string;
  }) =>
    request<{ items: DocumentProjectionItem[]; total: number }>(
      WORKBENCH_BASE,
      "/workbench/documents",
      {
        query: opts
          ? Object.fromEntries(
              Object.entries(opts).map(([key, value]) => [key, value == null ? undefined : String(value)])
            )
          : undefined,
      }
    ),
  getDocument: (doc_id: string) =>
    request<DocumentProjectionItem>(
      WORKBENCH_BASE,
      `/workbench/documents/${doc_id}`
    ),
  getDocumentWorkspace: (doc_id: string) =>
    request<DocumentWorkspaceDetailView>(
      WORKBENCH_BASE,
      `/workbench/documents/${doc_id}/workspace`
    ),
  archiveDocument: (doc_id: string, payload: DocumentLifecycleActionRequest) =>
    request<DocumentLifecycleActionResult>(
      WORKBENCH_BASE,
      `/workbench/documents/${doc_id}/archive`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  retractDocument: (doc_id: string, payload: DocumentLifecycleActionRequest) =>
    request<DocumentLifecycleActionResult>(
      WORKBENCH_BASE,
      `/workbench/documents/${doc_id}/retract`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  reindexDocument: (doc_id: string, payload: DocumentLifecycleActionRequest) =>
    request<DocumentLifecycleActionResult>(
      WORKBENCH_BASE,
      `/workbench/documents/${doc_id}/reindex`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  batchArchiveDocuments: (payload: BatchDocumentActionRequest) =>
    request<BatchDocumentActionResult>(
      WORKBENCH_BASE,
      "/workbench/documents/batch/archive",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  batchRetractDocuments: (payload: BatchDocumentActionRequest) =>
    request<BatchDocumentActionResult>(
      WORKBENCH_BASE,
      "/workbench/documents/batch/retract",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  batchReindexDocuments: (payload: BatchDocumentActionRequest) =>
    request<BatchDocumentActionResult>(
      WORKBENCH_BASE,
      "/workbench/documents/batch/reindex",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  getSourceFilePreview: (source_file_id: string) =>
    request<SourceFilePreviewView>(
      WORKBENCH_BASE,
      `/workbench/source-files/${source_file_id}/preview`
    ),
  getSourceFilePreviewContentUrl: (source_file_id: string) => {
    const token = getToken();
    syncWorkbenchAuthCookie(token);
    return resolveUrl(
      WORKBENCH_BASE,
      `/workbench/source-files/${source_file_id}/preview/content`
    ).toString();
  },
  getParseSnapshotSourceBlob: async (parse_snapshot_id: string) => {
    const url = resolveUrl(
      WORKBENCH_BASE,
      `/workbench/parse-snapshots/${parse_snapshot_id}/source`
    );
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const res = await fetchWithTimeout(
      url.toString(),
      { headers },
      DEFAULT_REQUEST_TIMEOUT_MS
    );

    if (!res.ok) {
      let body: { code?: string; message?: string; detail?: string } = {};
      try {
        body = await res.json();
      } catch {
        /* ignore */
      }
      throw new ApiClientError(
        body.code || `HTTP_${res.status}`,
        body.message || body.detail || `HTTP ${res.status}`,
        res.status
      );
    }

    const blob = await res.blob();
    const contentType = res.headers.get("content-type") || "application/octet-stream";
    return { blob, contentType };
  },
  getSourceFilePreviewBlob: async (source_file_id: string) => {
    const url = resolveUrl(
      WORKBENCH_BASE,
      `/workbench/source-files/${source_file_id}/preview/content`
    );
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const res = await fetchWithTimeout(
      url.toString(),
      { headers },
      DEFAULT_REQUEST_TIMEOUT_MS
    );

    if (!res.ok) {
      let body: { code?: string; message?: string; detail?: string } = {};
      try {
        body = await res.json();
      } catch {
        /* ignore */
      }
      throw new ApiClientError(
        body.code || `HTTP_${res.status}`,
        body.message || body.detail || `HTTP ${res.status}`,
        res.status
      );
    }

    const blob = await res.blob();
    const contentType = res.headers.get("content-type") || "application/octet-stream";
    return { blob, contentType };
  },
  getWorkspaceDetail: (ticket_id: string) =>
    request<WorkspaceDetailView>(
      WORKBENCH_BASE,
      `/workbench/tickets/${ticket_id}/workspace`
    ),
  retrieve: (payload: {
    query: string;
    collection_id: string;
    token_budget?: number;
    max_results?: number;
    budget_policy?: string;
    application_profile_id?: string;
    retrieval_profile_id?: string;
    debug?: "none" | "basic" | "full";
  }) =>
    request<{
      query_run_id: string;
      knowledge_context: Record<string, unknown>;
      latency_ms: number;
      trace_id: string;
      evidence_items: Array<Record<string, unknown>>;
      token_budget_used: number;
    }>(WORKBENCH_BASE, "/workbench/retrieve", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listQueryRuns: (opts?: { limit?: number; offset?: number }) =>
    request<{
      items: Array<{
        query_run_id: string;
        query: string;
        collection_id: string;
        retrieval_profile_id: string;
        created_at: string;
        latency_ms?: number;
      }>;
      total: number;
    }>(WORKBENCH_BASE, "/workbench/query-runs", {
      query: opts
        ? Object.fromEntries(
            Object.entries(opts).map(([key, value]) => [
              key,
              value == null ? undefined : String(value),
            ])
          )
        : undefined,
    }),
  getDashboard: () =>
    request<DashboardResponse>(WORKBENCH_BASE, "/workbench/dashboard"),
  getNotifications: () =>
    request<NotificationListResponse>(WORKBENCH_BASE, "/workbench/notifications"),
  markNotificationRead: (id: string) =>
    request<{ notification_id: string; is_read: boolean }>(
      WORKBENCH_BASE,
      `/workbench/notifications/${id}/read`,
      { method: "PATCH" }
    ),
  readAllNotifications: () =>
    request<{ count: number }>(
      WORKBENCH_BASE,
      "/workbench/notifications/read-all",
      { method: "POST" }
    ),
  getUnreadCount: () =>
    request<{ count: number }>(WORKBENCH_BASE, "/workbench/notifications/unread-count"),
  listAuditLogs: (opts?: {
    operator_id?: string;
    operation_type?: string;
    collection_id?: string;
    target_id?: string;
    from_date?: string;
    to_date?: string;
    page?: number;
    page_size?: number;
  }) =>
    request<AuditLogListResponse>(WORKBENCH_BASE, "/workbench/audit-logs", {
      query: opts
        ? Object.fromEntries(
            Object.entries(opts).map(([key, value]) => [key, value == null ? undefined : String(value)])
          )
        : undefined,
    }),
  exportAuditLogs: (opts?: { format?: "csv" | "excel" }) =>
    request<{ download_url: string }>(WORKBENCH_BASE, "/workbench/audit-logs/export", {
      method: "POST",
      body: JSON.stringify(opts || {}),
    }),
  listApiKeys: () =>
    request<{ items: ApiKeyItem[]; total: number }>(WORKBENCH_BASE, "/workbench/api-keys"),
  getApiKeyDetail: (id: string) =>
    request<ApiKeyDetail>(WORKBENCH_BASE, `/workbench/api-keys/${id}`),
  createApiKey: (payload: {
    name: string;
    permissions?: string[];
    collection_ids?: string[];
    expires_at?: string | null;
  }) =>
    request<ApiKeyDetail>(WORKBENCH_BASE, "/workbench/api-keys", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateApiKey: (id: string, payload: {
    name?: string;
    permissions?: string[];
    collection_ids?: string[];
    expires_at?: string | null;
  }) =>
    request<ApiKeyDetail>(WORKBENCH_BASE, `/workbench/api-keys/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteApiKey: (id: string) =>
    request<{ api_key_id: string; deleted: boolean }>(WORKBENCH_BASE, `/workbench/api-keys/${id}`, { method: "DELETE" }),
  getApiKeyUsage: (id: string) =>
    request<ApiKeyUsage>(WORKBENCH_BASE, `/workbench/api-keys/${id}/usage`),
};

export { WORKBENCH_BASE };
