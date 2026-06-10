import { test, expect } from "@playwright/test";

test.describe("Review Workspace Aggregation", () => {
  test("hides parsed-text affordances when workspace has no parse snapshot", async ({ page }) => {
    await page.route("**/api/workbench/tickets/ticket_workspace_no_parse/workspace", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ticket_id: "ticket_workspace_no_parse",
          ticket: {
            ticket_id: "ticket_workspace_no_parse",
            collection_id: "test2",
            status: "pending",
            tenant_id: "tenant_acme",
            doc_id: "doc_workspace_no_parse",
            source_file_id: "sf_workspace_no_parse",
            parse_snapshot_id: null,
            upload_id: "upload_workspace_no_parse",
            filename: "workspace-no-parse.docx",
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
            updated_at: "2026-06-09T10:10:00Z",
            projection_updated_at: "2026-06-09T10:10:01Z",
            is_stale: false,
            source: "merged",
          },
          document: {
            doc_id: "doc_workspace_no_parse",
            tenant_id: "tenant_acme",
            collection_id: "test2",
            source_file_id: "sf_workspace_no_parse",
            parse_snapshot_id: null,
            published_doc_id: null,
            upload_id: "upload_workspace_no_parse",
            filename: "workspace-no-parse.docx",
            mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            document_state: "ACTIVE",
            publish_state: "published",
            active_index_version: "idx_v1",
            chunk_count: 0,
            page_count: 4,
            parser_profile_id: null,
            parser_profile_name: null,
            projection_updated_at: "2026-06-09T10:10:01Z",
            is_stale: false,
            degraded_reason: null,
            linkage_source: "document_projection",
          },
          source_file: {
            source_file_id: "sf_workspace_no_parse",
            upload_id: "upload_workspace_no_parse",
            tenant_id: "tenant_acme",
            collection_id: "test2",
            filename: "workspace-no-parse.docx",
            mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes: 1024,
            state: "ready",
            intake_job_id: "job_workspace_no_parse",
            scan_verdict: "clean",
            created_at: "2026-06-09T09:58:00Z",
            updated_at: "2026-06-09T10:00:00Z",
          },
          parse_snapshot: null,
          chunks: { items: [], total: 0 },
          chunk_edits: { items: [], total: 0 },
          agent_review: {
            ticket_id: "ticket_workspace_no_parse",
            decision: "REVIEW",
            source_file_id: "sf_workspace_no_parse",
            parse_snapshot_id: null,
            findings: [
              {
                finding_id: "finding_001",
                severity: "high",
                category: "factual_error",
                problem_summary: "Missing parse snapshot should disable document search",
                source_quote: "quoted text",
                evidence_id: null,
                doc_id: "doc_workspace_no_parse",
                source_file_id: "sf_workspace_no_parse",
                parse_snapshot_id: null,
                page_from: null,
                page_to: null,
                state: "open",
                confidence: 0.91,
                chunk_quote: null,
                why_wrong: null,
                suggested_fix: null,
                suggested_operation: null,
              },
            ],
            matched_count: 0,
            unmatched_count: 1,
            source: "projection",
          },
          capabilities: {
            can_view_source: true,
            can_view_parsed_text: false,
            can_search_in_document: false,
            can_edit_drafts: false,
            can_jump_to_chunk: false,
            can_decide_ticket: true,
            can_approve: true,
            can_reject: true,
            can_upload: false,
          },
          projection_freshness: {
            ticket_projection_updated_at: "2026-06-09T10:10:01Z",
            ticket_is_stale: false,
            document_projection_updated_at: "2026-06-09T10:10:01Z",
            document_is_stale: false,
          },
          degraded_parts: [],
          trace_id: "trc_workspace_no_parse",
        }),
      });
    });

    await page.route("**/api/workbench/source-files/sf_workspace_no_parse/preview", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          source_file_id: "sf_workspace_no_parse",
          collection_id: "test2",
          filename: "workspace-no-parse.docx",
          mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          page_count: 4,
          preview_available: false,
          preview_status: "unsupported",
          preview_kind: "unsupported",
          preview_mime_type: null,
          preview_url: null,
          thumbnail_url: null,
        }),
      });
    });

    await page.goto("/review/ticket_workspace_no_parse");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "workspace-no-parse.docx" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Parsed text" })).toHaveCount(0);
    await expect(page.locator("body")).toContainText("does not currently link to a parse snapshot");

    await page.getByRole("tab", { name: "Agent review" }).click();
    await expect(page.getByRole("button", { name: "Find in document" })).toHaveCount(0);
  });
});
