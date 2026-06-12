"use client";

import { useAppStore } from "@/lib/store";

/**
 * useAuthGuard — checks whether valid auth credentials are configured.
 *
 * Returns:
 * - isAuthenticated: true when a valid JWT token OR API key is present
 * - hasJwtToken: true when demoToken is a 3-segment JWT
 * - hasApiKey: true when demoApiKey is non-empty
 * - tokenMissing: true when neither JWT nor API key is configured
 * - message: user-facing guidance message
 */
export function useAuthGuard() {
  const demoToken = useAppStore((s) => s.demoToken);
  const demoApiKey = useAppStore((s) => s.demoApiKey);

  const hasJwtToken =
    !!demoToken && demoToken.split(".").length === 3;
  const hasApiKey = !!demoApiKey;
  const isAuthenticated = hasJwtToken || hasApiKey;

  let message: string | null = null;
  if (!hasJwtToken && !hasApiKey) {
    message = "请先配置 JWT 令牌或 API 密钥";
  } else if (!hasJwtToken) {
    message = "缺少 JWT 令牌，部分功能可能受限";
  }

  return {
    isAuthenticated,
    hasJwtToken,
    hasApiKey,
    tokenMissing: !isAuthenticated,
    message,
  };
}
