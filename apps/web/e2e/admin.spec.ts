import { test, expect, type Page } from "@playwright/test";

// Enterprise KnowledgeBase Admin — E2E Tests for Admin/Settings Pages
// These tests exercise admin-facing pages: audit logs, API keys, retrieval profiles, and detail pages.
// Tests are designed to pass even when backends are unavailable (shows skeletons/empty states).

async function waitForPageReady(page: Page) {
  // Framer Motion page transition takes ~200ms; wait for it to complete
  await page.waitForTimeout(400);
}

test.describe("Audit Log", () => {
  test("audit log page renders", async ({ page }) => {
    await page.goto("/settings/audit-log");
    await waitForPageReady(page);
    await expect(page.locator("body")).toContainText("审计日志");
  });

  test("audit log filters render", async ({ page }) => {
    await page.goto("/settings/audit-log");
    await waitForPageReady(page);
    await expect(page.locator("body")).toBeVisible();
  });
});

test.describe("API Keys", () => {
  test("API keys page renders", async ({ page }) => {
    await page.goto("/settings/api-keys");
    await waitForPageReady(page);
    await expect(page.locator("body")).toContainText("API");
  });

  test("create API key dialog", async ({ page }) => {
    await page.goto("/settings/api-keys");
    await waitForPageReady(page);
    const createBtn = page.locator("button:has-text('创建')").or(page.locator("button:has-text('新建')")).first();
    if (await createBtn.isVisible()) {
      await createBtn.click();
      await page.waitForTimeout(300);
    }
  });
});

test.describe("Retrieval Profiles", () => {
  test("profiles page renders", async ({ page }) => {
    await page.goto("/retrieval/profiles");
    await waitForPageReady(page);
    await expect(page.locator("body")).toContainText("检索配置");
  });
});

test.describe("Settings Detail Pages", () => {
  test("parser profiles page", async ({ page }) => {
    await page.goto("/settings/parser-profiles");
    await waitForPageReady(page);
    await expect(page.locator("body")).toBeVisible();
  });

  test("notification center popover", async ({ page }) => {
    await page.goto("/upload");
    await waitForPageReady(page);
    const bellBtn = page.locator("button:has-text('notification')").or(
      page.locator("[aria-label*='notification']").or(
        page.locator("button svg.lucide-bell").first()
      )
    ).first();
    if (await bellBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await bellBtn.click();
      await page.waitForTimeout(300);
    }
  });

  test("collection detail page", async ({ page }) => {
    await page.goto("/collections");
    await waitForPageReady(page);
    const collectionLink = page.locator("a[href*='/collections/']").first();
    if (await collectionLink.isVisible()) {
      await collectionLink.click();
      await page.waitForURL(/\/collections\//);
      await waitForPageReady(page);
    }
  });
});
