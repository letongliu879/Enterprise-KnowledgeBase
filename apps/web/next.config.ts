import type { NextConfig } from "next";

const adminTarget =
  process.env.ADMIN_BASE_URL ||
  process.env.NEXT_PUBLIC_ADMIN_API_URL ||
  "http://127.0.0.1:18084";
const workbenchTarget =
  process.env.WORKBENCH_BASE_URL ||
  process.env.NEXT_PUBLIC_WORKBENCH_API_URL ||
  "http://127.0.0.1:18083";
const accessTarget =
  process.env.ACCESS_BASE_URL ||
  process.env.NEXT_PUBLIC_ACCESS_API_URL ||
  "http://127.0.0.1:18181";
const retrievalTarget =
  process.env.RETRIEVAL_BASE_URL ||
  process.env.NEXT_PUBLIC_RETRIEVAL_API_URL ||
  "http://127.0.0.1:18182";

const nextConfig: NextConfig = {
  typescript: {
    ignoreBuildErrors: false,
  },
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: {
    root: __dirname,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/admin/health",
        destination: `${adminTarget}/health`,
      },
      {
        source: "/api/admin/:path*",
        destination: `${adminTarget}/admin/:path*`,
      },
      {
        source: "/api/workbench/:path*",
        destination: `${workbenchTarget}/workbench/:path*`,
      },
      {
        source: "/api/access/:path*",
        destination: `${accessTarget}/:path*`,
      },
      {
        source: "/api/retrieval/:path*",
        destination: `${retrievalTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
