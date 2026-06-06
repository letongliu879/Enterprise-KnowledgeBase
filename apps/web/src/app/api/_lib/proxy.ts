import { type NextRequest, NextResponse } from "next/server";

const SERVICE_MAP: Record<string, string> = {
  workbench: process.env.WORKBENCH_BASE_URL || "http://127.0.0.1:18083",
};

// Service-specific path prefixes applied after stripping /api/{service}
const SERVICE_PATH_PREFIX: Record<string, string> = {
  workbench: "/workbench",
};

export async function proxyRequest(
  req: NextRequest,
  service: "workbench"
) {
  const baseUrl = SERVICE_MAP[service];
  if (!baseUrl) {
    return NextResponse.json(
      { error: `Unknown service: ${service}` },
      { status: 500 }
    );
  }

  const { pathname, searchParams } = new URL(req.url);
  let relativePath = pathname.replace(new RegExp(`^/api/${service}`), "");

  // Workbench routes use /workbench prefix (e.g. /workbench/tasks).
  // The frontend calls /api/workbench/tasks, so we map it to /workbench/tasks.
  const prefix = SERVICE_PATH_PREFIX[service];
  if (prefix && !relativePath.startsWith(prefix)) {
    relativePath = prefix + relativePath;
  }

  const targetUrl = new URL(relativePath || "/", baseUrl);
  searchParams.forEach((value, key) => {
    targetUrl.searchParams.set(key, value);
  });

  // Forward headers (preserve auth)
  const headers = new Headers();
  const authHeader = req.headers.get("authorization");
  if (authHeader) headers.set("Authorization", authHeader);
  const apiKeyHeader = req.headers.get("x-api-key");
  if (apiKeyHeader) headers.set("X-API-Key", apiKeyHeader);
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);

  const method = req.method;
  const body = ["POST", "PUT", "PATCH"].includes(method) ? req.body : undefined;

  try {
    const upstream = await fetch(targetUrl.toString(), {
      method,
      headers,
      body: body as BodyInit | undefined,
      // @ts-expect-error — required by Node.js fetch when proxying a stream body
      duplex: "half",
    });

    const responseHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      responseHeaders.set(key, value);
    });

    return new NextResponse(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch (err) {
    console.error(`[API Proxy] ${service} ${method} ${targetUrl} error:`, err);
    return NextResponse.json(
      { error: `Service ${service} unreachable`, detail: String(err) },
      { status: 502 }
    );
  }
}
