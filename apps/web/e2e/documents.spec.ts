import { test, expect } from "@playwright/test";

test.describe("Document Library", () => {
  test("document list page loads", async ({ page }) => {
    await page.goto("/documents");
    await page.waitForLoadState("networkidle");
    
    // 检查页面标题
    await expect(page.locator("h1")).toContainText("文档库");
    
    // 截图保存
    await page.screenshot({ path: "e2e/screenshots/documents-list.png", fullPage: true });
  });

  test("document detail page loads", async ({ page }) => {
    // 先访问文档列表
    await page.goto("/documents");
    await page.waitForLoadState("networkidle");
    
    // 等待文档列表加载（如果有文档的话）
    await page.waitForTimeout(1000);
    
    // 截图查看当前状态
    await page.screenshot({ path: "e2e/screenshots/documents-before-click.png", fullPage: true });
    
    // 尝试点击第一个文档卡片（如果有的话）
    const firstDoc = page.locator("a[href^='/documents/']").first();
    const count = await firstDoc.count();
    
    if (count > 0) {
      await firstDoc.click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);
      
      // 检查是否显示 Not Found
      const notFound = page.locator("text=Not Found");
      if (await notFound.isVisible().catch(() => false)) {
        await page.screenshot({ path: "e2e/screenshots/documents-detail-notfound.png", fullPage: true });
        throw new Error("Document detail page shows Not Found");
      }
      
      // 检查页面内容
      await expect(page.locator("body")).toContainText("已入库文档");
      await page.screenshot({ path: "e2e/screenshots/documents-detail.png", fullPage: true });
    } else {
      console.log("No documents found in list");
    }
  });
});