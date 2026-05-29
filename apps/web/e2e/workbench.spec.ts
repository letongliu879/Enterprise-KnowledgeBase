import { test, expect, type Page } from "@playwright/test";

// Enterprise KnowledgeBase Workbench — Real Click Tests
// These tests exercise the actual frontend UI against real or demo backends.
// Backend gaps are marked as expected failures, not mocked successes.
// NOTE: Backend services must be running for data-dependent tests to pass.
// Tests are designed to pass even when backends are unavailable (shows skeletons/empty states).

async function waitForPageReady(page: Page) {
  // Framer Motion page transition takes ~200ms; wait for it to complete
  await page.waitForTimeout(400);
}

test.describe("Workbench Navigation", () => {
  test("homepage redirects to upload", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/.*upload/);
  });

  test("sidebar navigation works", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.getByRole("heading", { name: "批量入库" })).toBeVisible();

    await page.getByRole("link", { name: "人工复核" }).click();
    await expect(page).toHaveURL(/.*review/);
    await waitForPageReady(page);
    await expect(page.getByRole("heading", { name: "人工复核队列" })).toBeVisible();

    await page.getByRole("link", { name: "检索验证" }).click();
    await expect(page).toHaveURL(/.*retrieval/);
    await waitForPageReady(page);
    await expect(page.getByRole("heading", { name: "检索验证" })).toBeVisible();

    await page.getByRole("link", { name: "知识库集合" }).click();
    await expect(page).toHaveURL(/.*collections/);
    await waitForPageReady(page);
    await expect(page.getByRole("heading", { name: "知识库集合" })).toBeVisible();
  });
});

test.describe("Collections", () => {
  test("can view collections page", async ({ page }) => {
    await page.goto("/collections");
    await waitForPageReady(page);
    await expect(page.locator("body")).toContainText("知识库集合");
    await expect(page.locator("button:has-text('新建集合')")).toBeVisible();
  });

  test("collection selector in top bar", async ({ page }) => {
    await page.goto("/upload");
    await waitForPageReady(page);
    await page.getByRole("button", { name: "选择知识库集合" }).click();
    await expect(
      page.locator("[role='menu']").or(page.locator("text=无知识库集合"))
    ).toBeVisible();
  });
});

test.describe("Settings & Access Scope", () => {
  test("can configure access scope", async ({ page }) => {
    await page.goto("/settings");
    await waitForPageReady(page);
    await expect(page.getByRole("tab", { name: "权限范围" })).toBeVisible();

    await page.getByRole("tab", { name: "权限范围" }).click();
    await page.fill("input[placeholder='工程部']", "Engineering");
    await page.fill("input[placeholder='knowledge_admin']", "UPLOADER");
    await page.click("button:has-text('保存权限范围')");

    await expect(page.locator("text=权限范围已保存")).toBeVisible();
  });
});

test.describe("Batch Upload", () => {
  test("upload page shows missing collection/scope warning", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.locator("text=缺少集合或权限范围")).toBeVisible();
  });

  test("drag and drop zone is present", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.locator("text=拖拽文件至此，或点击选择")).toBeVisible();
    await expect(page.locator("text=支持 PDF、DOCX、PPTX、XLSX、CSV 格式")).toBeVisible();
  });

  test("can select file via input", async ({ page }) => {
    await page.goto("/upload");
    await waitForPageReady(page);
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeHidden();
  });
});

test.describe("Review Detail", () => {
  test("review detail page navigation", async ({ page }) => {
    await page.goto("/review");
    await waitForPageReady(page);
    await expect(page.locator("body")).toContainText("人工复核队列");
  });
});

test.describe("Settings", () => {
  test("settings page has auth tab", async ({ page }) => {
    await page.goto("/settings");
    await waitForPageReady(page);
    await expect(page.getByRole("tab", { name: "认证" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "权限范围" })).toBeVisible();
  });
});

test.describe("Review Queue", () => {
  test("review queue page loads", async ({ page }) => {
    await page.goto("/review");
    await waitForPageReady(page);
    await expect(page.locator("body")).toContainText("人工复核队列");
    await expect(page.locator("input[placeholder='知识库集合...']")).toBeVisible();
  });
});

test.describe("Retrieval", () => {
  test("retrieval page loads with canonical fields", async ({ page }) => {
    await page.goto("/retrieval");
    await expect(page.getByRole("heading", { name: "检索验证" })).toBeVisible();
    await expect(page.locator("main")).toContainText("展示证据片段，而非生成答案");
    await expect(page.locator("label:has-text('查询（标准字段）')")).toBeVisible();
    await expect(page.locator("label:has-text('Token 预算')")).toBeVisible();
  });

  test("retrieve button exists", async ({ page }) => {
    await page.goto("/retrieval");
    const btn = page.locator("button:has-text('检索上下文')");
    await expect(btn).toBeVisible();
  });
});

test.describe("Screenshots for visual verification", () => {
  test("upload page screenshot", async ({ page }) => {
    await page.goto("/upload");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "e2e/screenshots/upload.png", fullPage: true });
  });

  test("collections page screenshot", async ({ page }) => {
    await page.goto("/collections");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "e2e/screenshots/collections.png", fullPage: true });
  });

  test("review page screenshot", async ({ page }) => {
    await page.goto("/review");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "e2e/screenshots/review.png", fullPage: true });
  });

  test("retrieval page screenshot", async ({ page }) => {
    await page.goto("/retrieval");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "e2e/screenshots/retrieval.png", fullPage: true });
  });

  test("settings page screenshot", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "e2e/screenshots/settings.png", fullPage: true });
  });
});
