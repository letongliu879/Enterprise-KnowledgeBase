import type {
  CollectionListResponse,
  WorkbenchTaskView,
  WorkbenchUploadSession,
  TicketItem,
  TicketDetail,
  TicketDecisionResult,
  AgentReviewView,
  ChunkView,
} from "./types";
import { ApiClientError, BackendGapError } from "./errors";
import { useAppStore } from "@/lib/store";

const ADMIN_BASE =
  process.env.NEXT_PUBLIC_ADMIN_API_BASE_URL ||
  "/api/admin";
const WORKBENCH_BASE =
  process.env.NEXT_PUBLIC_WORKBENCH_API_BASE_URL ||
  "/api/workbench";
const ACCESS_BASE =
  process.env.NEXT_PUBLIC_ACCESS_API_BASE_URL ||
  "/api/access";
const RETRIEVAL_BASE =
  process.env.NEXT_PUBLIC_RETRIEVAL_API_BASE_URL ||
  "/api/retrieval";
const REQUEST_TIMEOUT_MS = 15000;

function getToken(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const storeToken = useAppStore.getState().demoToken;
  if (storeToken) return storeToken;
  return process.env.NEXT_PUBLIC_DEMO_TOKEN || undefined;
}

function getApiKey(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const storeKey = useAppStore.getState().demoApiKey;
  if (storeKey) return storeKey;
  return process.env.NEXT_PUBLIC_DEMO_API_KEY || undefined;
}

async function request<T>(
  base: string,
  path: string,
  options: RequestInit & { query?: Record<string, string | undefined> } = {}
): Promise<T> {
  const url = resolveUrl(base, path);
  if (options.query) {
    Object.entries(options.query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
  }

  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const res = await fetch(url.toString(), {
    ...options,
    headers,
    signal: controller.signal,
  }).catch((error: unknown) => {
    clearTimeout(timeout);
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiClientError(
        "REQUEST_TIMEOUT",
        `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s`,
        408
      );
    }
    throw error;
  });
  clearTimeout(timeout);

  if (res.status === 501) {
    throw new BackendGapError(
      `${options.method || "GET"} ${path}`,
      `${base}${path}`,
      "Backend API returns 501 — not implemented"
    );
  }

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

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

async function requestAccess<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = resolveUrl(ACCESS_BASE, path);
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  const apiKey = getApiKey();
  if (apiKey) headers.set("X-API-Key", apiKey);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const res = await fetch(url.toString(), {
    ...options,
    headers,
    signal: controller.signal,
  }).catch((error: unknown) => {
    clearTimeout(timeout);
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiClientError(
        "REQUEST_TIMEOUT",
        `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s`,
        408
      );
    }
    throw error;
  });
  clearTimeout(timeout);

  if (!res.ok) {
    let body: { code?: string; message?: string } = {};
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    throw new ApiClientError(
      body.code || `HTTP_${res.status}`,
      body.message || `HTTP ${res.status}`,
      res.status
    );
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

// ── Admin API ──────────────────────────────────────────────────────────

export const adminApi = {
  health: () =>
    request<{ service: string; status: string }>(ADMIN_BASE, "/health"),
  me: () =>
    request<{
      user_id: string;
      email: string;
      display_name?: string;
      roles: string[];
      tenant_id: string;
      allowed_tenants?: string[];
      allowed_collections?: string[];
    }>(ADMIN_BASE, "/admin/auth/me"),
  listCollections: (tenant_id?: string) =>
    request<CollectionListResponse>(ADMIN_BASE, "/admin/collections", {
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
    request<Record<string, unknown>>(ADMIN_BASE, "/admin/collections", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listRetrievalProfiles: (state?: string) =>
    request<{ items: Array<Record<string, unknown>>; total: number }>(
      ADMIN_BASE,
      "/admin/retrieval-profiles",
      { query: { state } }
    ),
};

// ── Workbench API ──────────────────────────────────────────────────────

export const workbenchApi = {
  health: () =>
    request<{ service: string; status: string }>(
      WORKBENCH_BASE,
      "/workbench/health"
    ),
  me: () =>
    request<{
      user_id: string;
      email: string;
      display_name?: string;
      roles: string[];
      tenant_id: string;
      allowed_collections: string[];
    }>(WORKBENCH_BASE, "/workbench/auth/me"),
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

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    const res = await fetch(url.toString(), {
      method: "POST",
      body: formData,
      headers,
      signal: controller.signal,
    }).catch((error: unknown) => {
      clearTimeout(timeout);
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiClientError(
          "REQUEST_TIMEOUT",
          `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s`,
          408
        );
      }
      throw error;
    });
    clearTimeout(timeout);

    if (res.status === 501) {
      throw new BackendGapError(
        `POST /workbench/uploads/${upload_id}/content`,
        url.toString(),
        "Backend API returns 501 — not implemented"
      );
    }
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
  listTasks: (opts?: { collection_id?: string; status?: string }) =>
    request<{ items: WorkbenchTaskView[]; total: number }>(
      WORKBENCH_BASE,
      "/workbench/tasks",
      { query: opts }
    ),
  getTask: (upload_id: string) =>
    request<WorkbenchTaskView>(
      WORKBENCH_BASE,
      `/workbench/tasks/${upload_id}`
    ),
  listTickets: (opts?: { collection_id?: string; status?: string }) =>
    request<{ items: TicketItem[]; total: number }>(
      WORKBENCH_BASE,
      "/workbench/tickets",
      { query: opts }
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
  getChunk: (evidence_id: string) =>
    request<Record<string, unknown>>(
      WORKBENCH_BASE,
      `/workbench/chunks/${evidence_id}`
    ),
  patchChunk: (evidence_id: string, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(
      WORKBENCH_BASE,
      `/workbench/chunks/${evidence_id}`,
      { method: "PATCH", body: JSON.stringify(payload) }
    ),
  getParseSnapshot: (id: string) =>
    request<Record<string, unknown>>(
      WORKBENCH_BASE,
      `/workbench/parse-snapshots/${id}`
    ),
  getParseSnapshotChunks: (id: string, page?: number, page_size?: number) =>
    request<{ items: ChunkView[]; total: number }>(
      WORKBENCH_BASE,
      `/workbench/parse-snapshots/${id}/chunks`,
      { query: { page: String(page || 1), page_size: String(page_size || 50) } }
    ),
};

// ── Access API (retrieval) ─────────────────────────────────────────────

export const accessApi = {
  health: () =>
    request<{ service: string; status: string; retrieval_status: string }>(
      ACCESS_BASE,
      "/health"
    ),
  retrieve: (payload: {
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
  }) =>
    requestAccess<Record<string, unknown>>("/v1/retrieve", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// ── Retrieval internal (for workbench debug only) ──────────────────────

export const retrievalApi = {
  health: () =>
    request<{ service: string; status: string }>(RETRIEVAL_BASE, "/health"),
};

export { ADMIN_BASE, WORKBENCH_BASE, ACCESS_BASE, RETRIEVAL_BASE };
