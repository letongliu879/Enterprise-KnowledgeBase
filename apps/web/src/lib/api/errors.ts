export class ApiClientError extends Error {
  constructor(
    public code: string,
    message: string,
    public status?: number,
    public downstream?: string
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export class BackendGapError extends Error {
  constructor(
    public feature: string,
    public endpoint: string,
    message = "Backend API not yet implemented"
  ) {
    super(message);
    this.name = "BackendGapError";
  }
}

export function isBackendGap(error: unknown): error is BackendGapError {
  return error instanceof BackendGapError;
}

export function isApiError(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError;
}

/**
 * Safely extract a human-readable message from any error value.
 * Prevents `[object Object]` from appearing in the UI.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) return error.message;
  if (error instanceof BackendGapError) return error.message;
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  if (error && typeof error === "object") {
    // Try common error shapes
    const obj = error as Record<string, unknown>;
    if (typeof obj.message === "string") return obj.message;
    if (typeof obj.error === "string") return obj.error;
    if (typeof obj.detail === "string") return obj.detail;
    return JSON.stringify(error);
  }
  return String(error);
}
