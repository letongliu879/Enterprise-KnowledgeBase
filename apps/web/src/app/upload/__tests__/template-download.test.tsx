import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

// ── CSV Template File Tests ──────────────────────────────────────────────

describe("Upload CSV Template File", () => {
  const templatePath = path.resolve(
    __dirname,
    "../../../../public/templates/upload-template.csv"
  );

  it("exists at the expected path", () => {
    expect(fs.existsSync(templatePath)).toBe(true);
  });

  it("has header row and at least one data row with filename and collection_id", () => {
    const content = fs.readFileSync(templatePath, "utf-8");
    const lines = content.trim().split("\n");
    expect(lines.length).toBeGreaterThanOrEqual(2);
    expect(lines[0].toLowerCase()).toContain("filename");
    expect(lines[0].toLowerCase()).toContain("collection_id");
    expect(lines[1]).toBeTruthy();
  });

  it("is valid UTF-8 with no BOM", () => {
    const buffer = fs.readFileSync(templatePath);
    expect(buffer[0]).not.toBe(0xef);
    expect(buffer[1]).not.toBe(0xbb);
    expect(buffer[2]).not.toBe(0xbf);
  });

  it("has valid CSV structure (same columns per row)", () => {
    const content = fs.readFileSync(templatePath, "utf-8");
    const lines = content.trim().split("\n");
    const headerCols = lines[0].split(",").length;
    for (let i = 1; i < lines.length; i++) {
      expect(lines[i].split(",").length).toBe(headerCols);
    }
  });
});
