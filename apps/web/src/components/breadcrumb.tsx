"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import { cn } from "@/lib/utils";

const routeLabels: Record<string, string> = {
  upload: "批量入库",
  review: "人工复核",
  documents: "文档库",
  retrieval: "检索验证",
  collections: "知识库集合",
  settings: "设置",
  "api-keys": "API 密钥",
  "audit-log": "审计日志",
  "parser-profiles": "解析策略",
  trash: "回收站",
  help: "帮助中心",
  workbench: "工作台",
};

// Dynamic segment prefixes — URL segment name → display prefix for dynamic IDs
const dynamicPrefixes: Record<string, string> = {
  documents: "文档",
  review: "工单",
  tasks: "任务",
  collections: "集合",
  upload: "上传",
};

/**
 * Breadcrumb — auto-generated from the current URL path segments.
 *
 * Unrecognized segments that look like UUIDs or hex IDs are shown with a
 * generic prefix label derived from the parent segment, improving readability
 * for dynamic routes like /documents/[docId].
 */
export function Breadcrumb({ className }: { className?: string }) {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  return (
    <nav className={cn("flex items-center gap-1.5 text-sm", className)} aria-label="Breadcrumb">
      <Link
        href="/"
        className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
      >
        <Home className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">首页</span>
      </Link>

      {segments.map((segment, index) => {
        const isLast = index === segments.length - 1;
        const href = "/" + segments.slice(0, index + 1).join("/");

        // Check if this segment looks like a dynamic ID (UUID, hex, or long hash)
        const isIdSegment =
          /^[0-9a-f]{8}-[0-9a-f]{4}/i.test(segment) ||
          /^[0-9a-f]{20,}$/i.test(segment) ||
          /^\d{6,}$/.test(segment);

        let label: string;
        if (isIdSegment) {
          // Use the parent segment's dynamic prefix or a generic label
          const parentSegment = segments[index - 1] || "";
          const dynamicPrefix = dynamicPrefixes[parentSegment] || parentSegment;
          label = `${dynamicPrefix} 详情`;
        } else {
          label = routeLabels[segment] || segment;
        }

        return (
          <div key={segment + index} className="flex items-center gap-1.5">
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
            {isLast ? (
              <span className="font-medium text-foreground truncate max-w-[200px]" title={label}>
                {label}
              </span>
            ) : (
              <Link
                href={href}
                className="text-muted-foreground hover:text-foreground transition-colors truncate max-w-[200px]"
                title={label}
              >
                {label}
              </Link>
            )}
          </div>
        );
      })}
    </nav>
  );
}
