import { test, expect, type Page } from "@playwright/test";

async function mockWorkbenchShell(page: Page) {
  await page.route("**/api/workbench/health/all", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workbench: { status: "ok", service: "workbench" },
        services: {
          admin: { status: "ok", service: "admin" },
          access: { status: "ok", service: "access" },
          retrieval: { status: "ok", service: "retrieval" },
          ingestion: { status: "ok", service: "ingestion" },
        },
        all_healthy: true,
      }),
    });
  });

  await page.route("**/api/workbench/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user_id: "user-001",
        email: "admin@example.com",
        roles: ["knowledge_admin", "reviewer", "chunk_editor"],
        tenant_id: "tenant_acme",
        allowed_collections: ["col_default", "col_finance"],
      }),
    });
  });

  await page.route("**/api/workbench/collections*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            collection_id: "col_default",
            tenant_id: "tenant_acme",
            name: "Default Collection",
            description: "Default",
            lifecycle_state: "active",
            created_by: "user-001",
            created_at: "2026-06-09T09:00:00Z",
            updated_by: "user-001",
            updated_at: "2026-06-09T09:00:00Z",
          },
          {
            collection_id: "col_finance",
            tenant_id: "tenant_acme",
            name: "Finance Collection",
            description: "Finance",
            lifecycle_state: "active",
            created_by: "user-001",
            created_at: "2026-06-09T09:00:00Z",
            updated_by: "user-001",
            updated_at: "2026-06-09T09:00:00Z",
          },
        ],
        total: 2,
      }),
    });
  });
}

test.describe("Document Management", () => {
  test("document list supports selection and batch reindex", async ({ page }) => {
    await mockWorkbenchShell(page);

    await page.route("**/api/workbench/documents*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              doc_id: "doc_001",
              tenant_id: "tenant_acme",
              collection_id: "col_default",
              source_file_id: "sf_001",
              parse_snapshot_id: "ps_001",
              published_doc_id: "pub_001",
              upload_id: "upload_001",
              filename: "finance-report.docx",
              mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              document_state: "ACTIVE",
              publish_state: "published",
              active_index_version: "idx_v1",
              chunk_count: 12,
              page_count: 8,
              parser_profile_id: "parser_default",
              parser_profile_name: "Default Parser",
              projection_updated_at: "2026-06-09T10:15:01Z",
              is_stale: false,
              degraded_reason: null,
              created_at: "2026-06-09T10:00:00Z",
              updated_at: "2026-06-09T10:15:01Z",
              ticket_id: "ticket_001",
              ticket_status: "pending",
              task_status: "reviewing",
              has_source_file: true,
              has_parse_snapshot: true,
              has_active_index: true,
              latest_updated_at: "2026-06-09T10:15:01Z",
            },
            {
              doc_id: "doc_002",
              tenant_id: "tenant_acme",
              collection_id: "col_finance",
              source_file_id: null,
              parse_snapshot_id: null,
              published_doc_id: null,
              upload_id: "upload_002",
              filename: "budget.csv",
              mime_type: "text/csv",
              document_state: "PENDING",
              publish_state: null,
              active_index_version: null,
              chunk_count: 0,
              page_count: 0,
              parser_profile_id: null,
              parser_profile_name: null,
              projection_updated_at: "2026-06-09T11:00:00Z",
              is_stale: true,
              degraded_reason: "parse snapshot missing",
              created_at: "2026-06-09T10:30:00Z",
              updated_at: "2026-06-09T11:00:00Z",
              ticket_id: null,
              ticket_status: null,
              task_status: "uploading",
              has_source_file: false,
              has_parse_snapshot: false,
              has_active_index: false,
              latest_updated_at: "2026-06-09T11:00:00Z",
            },
          ],
          total: 2,
        }),
      });
    });

    await page.route("**/api/workbench/documents/batch/reindex", async (route) => {
      const body = route.request().postDataJSON();
      expect(body).toEqual({
        doc_ids: ["doc_001", "doc_002"],
        reason: "refresh after parser upgrade",
        index_profile_id: "ragflow",
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total: 2,
          succeeded: 1,
          failed: 1,
          items: [
            {
              doc_id: "doc_001",
              success: true,
              previous_state: "PUBLISHED",
              new_state: "REINDEXING",
              job_id: "idx_job_001",
              error_code: null,
              error_message: null,
            },
            {
              doc_id: "doc_002",
              success: false,
              previous_state: null,
              new_state: null,
              job_id: null,
              error_code: "CONFLICT",
              error_message: "Document does not have a parse snapshot and cannot be reindexed",
            },
          ],
        }),
      });
    });

    await page.goto("/documents");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "Document Library" })).toBeVisible();
    await expect(page.getByRole("link", { name: "finance-report.docx" })).toBeVisible();
    await expect(page.getByRole("link", { name: "budget.csv" })).toBeVisible();

    const checkboxes = page.locator('input[type="checkbox"]');
    await checkboxes.nth(1).check();
    await checkboxes.nth(2).check();

    await expect(page.locator("text=2 selected")).toBeVisible();
    await page.getByRole("button", { name: "Reindex" }).click();
    await page.getByRole("dialog").getByPlaceholder("Reason").fill("refresh after parser upgrade");
    await page.getByRole("button", { name: "Confirm" }).click();

    await expect(page.locator("text=Succeeded 1")).toBeVisible();
    await expect(page.locator("text=Failed 1")).toBeVisible();
    await expect(page.locator("text=doc_001")).toBeVisible();
    await expect(page.locator("text=doc_002")).toBeVisible();
  });

  test("document detail shows workspace, review cockpit, and lifecycle actions", async ({ page }) => {
    await mockWorkbenchShell(page);

    await page.route("**/api/workbench/documents/doc_001/workspace*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ticket_id: "ticket_001",
          ticket: {
            ticket_id: "ticket_001",
            collection_id: "col_default",
            status: "pending",
            tenant_id: "tenant_acme",
            doc_id: "doc_001",
            source_file_id: "sf_001",
            parse_snapshot_id: "ps_001",
            upload_id: "upload_001",
            title: null,
            filename: "finance-report.docx",
            priority: null,
            assignee_user_id: null,
            decision: null,
            decision_reason: null,
            decided_by: null,
            agent_decision: "REVIEW",
            agent_risk_level: "high",
            agent_finding_count: 1,
            agent_blocking_finding_count: 1,
            failure_code: null,
            failure_stage: null,
            next_action: null,
            created_at: "2026-06-09T10:00:00Z",
            updated_at: "2026-06-09T10:15:00Z",
            projection_updated_at: "2026-06-09T10:15:02Z",
            is_stale: false,
            source: "merged",
          },
          document: {
            doc_id: "doc_001",
            tenant_id: "tenant_acme",
            collection_id: "col_default",
            source_file_id: "sf_001",
            parse_snapshot_id: "ps_001",
            published_doc_id: "pub_001",
            upload_id: "upload_001",
            filename: "finance-report.docx",
            mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            document_state: "ACTIVE",
            publish_state: "published",
            active_index_version: "idx_v1",
            chunk_count: 12,
            page_count: 8,
            parser_profile_id: "parser_default",
            parser_profile_name: "Default Parser",
            projection_updated_at: "2026-06-09T10:15:01Z",
            is_stale: false,
            degraded_reason: null,
            linkage_source: "document_projection",
          },
          task: {
            upload_id: "upload_001",
            collection_id: "col_default",
            status: "reviewing",
            filename: "finance-report.docx",
            source_file_id: "sf_001",
            intake_job_id: "job_001",
            parse_snapshot_id: "ps_001",
            ticket_id: "ticket_001",
            published_doc_id: "pub_001",
            doc_id: "doc_001",
            progress_pct: 75,
            source_file_state: "ready",
            intake_job_state: "review_running",
            parse_snapshot_state: null,
            ticket_state: "pending",
            published_document_state: null,
            index_build_state: null,
            active_index_version: "idx_v1",
            created_at: "2026-06-09T10:00:00Z",
            updated_at: "2026-06-09T10:15:00Z",
            projection_updated_at: "2026-06-09T10:15:01Z",
            is_stale: false,
          },
          source_file: {
            source_file_id: "sf_001",
            upload_id: "upload_001",
            tenant_id: "tenant_acme",
            collection_id: "col_default",
            filename: "finance-report.docx",
            mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes: 1024,
            state: "ready",
            intake_job_id: "job_001",
            scan_verdict: "clean",
            created_at: "2026-06-09T09:58:00Z",
            updated_at: "2026-06-09T10:00:00Z",
          },
          parse_snapshot: {
            parse_snapshot_id: "ps_001",
            source_file_id: "sf_001",
            tenant_id: "tenant_acme",
            collection_id: "col_default",
            source_filename: "finance-report.docx",
            source_suffix: "docx",
            parser_id: "docling",
            parser_backend: "ragflow_app",
            parser_profile_id: "parser_default",
            effective_policy: "default-docx-policy",
            decision_reason: null,
            preview_text: "Normalized preview text",
            warnings: [],
            created_at: "2026-06-09T10:05:00Z",
          },
          chunks: {
            items: [
              {
                evidence_id: "ev_001",
                doc_id: "doc_001",
                content: "Normalized preview text",
                vector_text: null,
                section_path: ["Section 1"],
                page_spans: [{ page_from: 1, page_to: 1 }],
                chunk_type: "paragraph",
                metadata: null,
              },
            ],
            total: 1,
          },
          chunk_edits: { items: [], total: 0 },
          agent_review: {
            ticket_id: "ticket_001",
            decision: "REVIEW",
            source_file_id: "sf_001",
            parse_snapshot_id: "ps_001",
            findings: [
              {
                finding_id: "finding_001",
                severity: "high",
                category: "factual_error",
                problem_summary: "Summary omits a constraint",
                source_quote: "quoted text",
                evidence_id: "ev_001",
                doc_id: "doc_001",
                source_file_id: "sf_001",
                parse_snapshot_id: "ps_001",
                page_from: 1,
                page_to: 1,
                state: "open",
                confidence: 0.91,
                chunk_quote: null,
                why_wrong: null,
                suggested_fix: null,
                suggested_operation: null,
              },
            ],
            matched_count: 1,
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
            can_upload: false,
            can_archive: true,
            can_retract: true,
            can_reindex: true,
          },
          projection_freshness: {
            ticket_projection_updated_at: "2026-06-09T10:15:02Z",
            ticket_is_stale: false,
            document_projection_updated_at: "2026-06-09T10:15:01Z",
            document_is_stale: false,
          },
          degraded_parts: [],
          trace_id: "trc_001",
        }),
      });
    });

    await page.route("**/api/workbench/source-files/sf_001/preview", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          source_file_id: "sf_001",
          collection_id: "col_default",
          filename: "finance-report.docx",
          mime_type: "application/pdf",
          page_count: 8,
          preview_available: false,
          preview_status: "unsupported",
          preview_kind: "unsupported",
          preview_mime_type: null,
          preview_url: null,
          thumbnail_url: null,
        }),
      });
    });

    await page.route("**/api/workbench/tickets/ticket_001/decide", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ticket_id: "ticket_001",
          status: "approved",
          decision: "APPROVE",
        }),
      });
    });

    await page.route("**/api/workbench/documents/doc_001/reindex", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          final_doc_id: "doc_001",
          previous_state: "PUBLISHED",
          new_state: "REINDEXING",
          job_id: "idx_job_001",
        }),
      });
    });

    await page.goto("/documents/doc_001");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "finance-report.docx" })).toBeVisible();
    await expect(page.locator("text=Review Cockpit")).toBeVisible();
    await expect(page.locator("text=Lifecycle Actions")).toBeVisible();
    await expect(page.locator("text=Task Status")).toBeVisible();

    await page.getByRole("tab", { name: "Agent Review" }).click();
    await expect(page.locator("text=Summary omits a constraint")).toBeVisible();

    await page.getByRole("button", { name: "Reindex Document" }).click();
    await page.getByRole("dialog").getByPlaceholder("Reason").fill("refresh after parser upgrade");
    await page.getByRole("button", { name: "Confirm" }).click();

    await expect(page.locator("text=Reindex started")).toBeVisible();
  });
});
