import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { workbenchApi } from "@/lib/api/client";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

describe("workbenchApi.deleteCollection - 删除集合", () => {
  it("happy path: 删除成功返回 deleted 状态", async () => {
    server.use(
      http.delete("*/api/workbench/collections/coll-001", () =>
        HttpResponse.json({ status: "deleted" })
      )
    );

    const result = await workbenchApi.deleteCollection("coll-001");
    expect(result.status).toBe("deleted");
  });

  it("异常: 集合不存在时抛出错误", async () => {
    server.use(
      http.delete("*/api/workbench/collections/nonexistent", () =>
        HttpResponse.json({ error: "Collection not found" }, { status: 404 })
      )
    );

    await expect(workbenchApi.deleteCollection("nonexistent")).rejects.toThrow();
  });
});
