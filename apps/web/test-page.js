(async () => {
  const { chromium } = await import("playwright");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on("console", (msg) =>
    console.log("PAGE CONSOLE:", msg.type(), msg.text())
  );
  page.on("pageerror", (err) => console.log("PAGE ERROR:", err.message));
  console.log("Navigating to http://localhost:3000 ...");
  await page.goto("http://localhost:3000/", {
    waitUntil: "networkidle",
    timeout: 30000,
  });
  console.log("Page loaded, waiting 10s...");
  await page.waitForTimeout(10000);
  console.log("Done, closing browser.");
  await browser.close();
})();
