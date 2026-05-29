# Frontend Workbench

**Status:** MVP Complete (2026-05-29)  
**Location:** `apps/web/`  
**Framework:** Next.js 16 App Router

---

## 1. Overview

The Knowledge Workbench frontend is a governed document intake and retrieval verification UI. It is **not a chatbot** — it does not generate answers. It provides:

- Batch file upload with collection and access-scope gating
- Agent review queue for intercepted documents
- Review detail with chunk preview and human decision workflow
- Retrieval verification using canonical wire fields
- Collection management and backend health monitoring

---

## 2. Architecture

### 2.1 Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 |
| Components | shadcn/ui |
| Server State | TanStack Query v5 |
| Client State | Zustand + persist |
| Animation | Framer Motion |
| E2E Testing | Playwright |

### 2.2 Directory Structure

```
apps/web/
  src/app/
    upload/page.tsx        Batch upload with drag-and-drop
    review/page.tsx        Agent review queue list
    review/[taskId]/       Review detail + decision actions
    retrieval/page.tsx     Retrieval verify (canonical fields)
    collections/page.tsx   Collection list + create dialog
    settings/page.tsx      Auth tokens + access scope editor
  src/components/
    layout/app-shell.tsx   Sidebar, top bar, health dots
    ui/                    shadcn/ui components
    backend-gap.tsx        Explicit missing-endpoint UI
    empty-state.tsx        Empty list placeholder
  src/lib/
    api/client.ts          Typed fetch wrappers for 4 services
    api/types.ts           Canonical TypeScript interfaces
    api/errors.ts          BackendGapError, ApiClientError
    store.ts               Zustand store (collection, scope, tokens)
  e2e/
    workbench.spec.ts      Playwright real-click tests
```

---

## 3. Backend Integration

### 3.1 Services

| Service | Env Var | Auth | Purpose |
|---|---|---|---|
| admin | `NEXT_PUBLIC_ADMIN_API_URL` | Bearer JWT | Collections, health |
| workbench-api | `NEXT_PUBLIC_WORKBENCH_API_URL` | Bearer JWT | Upload, tasks, tickets, snapshots |
| access | `NEXT_PUBLIC_ACCESS_API_URL` | X-API-Key | Retrieval delegation |
| retrieval | `NEXT_PUBLIC_RETRIEVAL_API_URL` | None (caller-gated) | Direct retrieval |

### 3.2 API Client Design

`src/lib/api/client.ts` provides typed wrappers around `fetch`:

- Injects `Authorization: Bearer <token>` for admin/workbench
- Injects `X-API-Key: <key>` for access
- Throws `BackendGapError` on HTTP 501
- Throws `ApiClientError` on other HTTP errors
- Returns typed responses via `src/lib/api/types.ts`

### 3.3 Backend Gap Pattern

When an endpoint is not yet implemented (HTTP 501), the UI shows an explicit `<BackendGap>` card instead of crashing or silently failing. This makes incomplete backend work visible to operators.

---

## 4. Pages

### 4.1 Upload (`/upload`)

- Drag-and-drop file zone (PDF, DOCX, PPTX, XLSX, CSV)
- Collection + access scope required before upload
- Upload metadata and multipart content carry `access_scope_json`; workbench-api maps internal/external scope to document-service `visibility` without requiring a DB schema change
- File status tracking: queued → uploading → parsing → auto-published / needs-review / failed
- Recent tasks list polled from workbench API

### 4.2 Review Queue (`/review`)

- Filterable list of approval tickets (collection, status)
- Status badges: PENDING, APPROVED, REJECTED, RETURNED
- Click through to review detail

### 4.3 Review Detail (`/review/[taskId]`)

- Document metadata card
- Agent intercept reason (quality findings, risk flags, suggested fixes)
- Chunk preview tab (evidence_id, chunk_type, content)
- Parse metadata tab (raw JSON snapshot)
- Decision actions: APPROVE, REJECT, RETURN with optional reason

### 4.4 Retrieval Verify (`/retrieval`)

- Canonical fields only: `query`, `token_budget`
- Evidence item cards with rank, score, doc_id, evidence_id, content
- Expand/collapse for long content
- Copy-to-clipboard for chunk content
- Explicit label: "This is a context workbench — not an answer generator"

### 4.5 Collections (`/collections`)

- Grid of collection cards with lifecycle state badges
- Create collection dialog (id, name, description)
- "Select for Upload" button links to Zustand store

### 4.6 Settings (`/settings`)

- Tabs: Auth / Access Scope
- Auth: paste JWT token and API key (persisted to localStorage)
- Access Scope: internal (department/role/user/group) or external (agent/api_key/customer/app)

---

## 5. State Management

### 5.1 Server State (TanStack Query)

- Collections list
- Tickets list
- Ticket detail
- Agent review artifact
- Parse snapshot + chunks
- Upload tasks
- Backend health (polled every 30s)

### 5.2 Client State (Zustand)

```ts
interface AppStore {
  currentCollectionId: string | null;
  accessScope: AccessScope | null;
  demoToken: string | null;
  demoApiKey: string | null;
}
```

Persisted to `localStorage` so settings survive refresh.

---

## 6. Auth Model

**Demo/operator mode** — no OAuth flow. Users paste credentials in Settings:

- JWT token → `Authorization: Bearer` for admin/workbench
- API key → `X-API-Key` for access

Production deployments should replace this with a real identity provider (Keycloak, Auth0, etc.) and JWKS endpoint.

---

## 7. Testing Strategy

### 7.1 E2E Tests (Playwright)

`e2e/workbench.spec.ts` exercises the real UI against the real dev server:

- Navigation: sidebar links, redirects
- Collections: page load, collection selector dropdown
- Settings: access scope configuration
- Upload: missing-scope warning, drag-and-drop zone
- Review: queue page load with filter inputs
- Retrieval: canonical fields visible, retrieve button
- Screenshots: all 5 pages captured for visual regression

Tests are designed to pass even when backends are offline. They verify skeleton loaders, empty states, and static text — not data-dependent assertions.

### 7.2 Running Tests

```bash
cd apps/web
npm run build          # TypeScript + build check
npx playwright test    # E2E tests
npx playwright show-report
```

---

## 8. Canonical Wire Compliance

Retrieval page uses canonical fields exclusively:

| Canonical | Deprecated |
|---|---|
| `query` | `query_text` |
| `token_budget` | `max_context_tokens` |
| `evidence_items` | `result_chunks` |
| `doc_id` | `final_doc_id` |
| `evidence_id` | `chunk_id` |
| `content` | `display_text` |

No deprecated fields appear in the UI or API client types.

---

## 9. Build Verification

```bash
cd apps/web
npm run build
```

Expected output:
- TypeScript check: pass
- Static prerender: 8 routes (6 static, 1 dynamic `/review/[taskId]`)
- No eslint or type errors
