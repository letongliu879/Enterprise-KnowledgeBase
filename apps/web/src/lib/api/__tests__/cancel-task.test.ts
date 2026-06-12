import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { workbenchApi } from "@/lib/api/client";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

describe("workbenchApi.cancelTask - 取消上传任务", () => {
  it("happy path: 取消成功返回 cancelled 状态", async () => {
    server.use(
      http.post("*/api/workbench/tasks/task-001/cancel", () =>
        HttpResponse.json({ status: "cancelled", task_id: "task-001" })
      )
    );

    const result = await workbenchApi.cancelTask("task-001");
    expect(result.status).toBe("cancelled");
    expect(result.task_id).toBe("task-001");
  });

  it("异常: 任务不存在时抛出错误", async () => {
    server.use(
      http.post("*/api/workbench/tasks/nonexistent/cancel", () =>
        HttpResponse.json({ error: "Task not found" }, { status: 404 })
      )
    );

    await expect(workbenchApi.cancelTask("nonexistent")).rejects.toThrow();
  });
});
