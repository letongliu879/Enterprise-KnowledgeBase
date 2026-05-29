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
