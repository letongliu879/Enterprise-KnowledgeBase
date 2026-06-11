"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type EmptyStateVariant =
  | "default"
  | "upload"
  | "review"
  | "documents"
  | "retrieval"
  | "collections"
  | "success";

const variantConfig: Record<
  EmptyStateVariant,
  { title?: string; description?: string }
> = {
  default: {},
  upload: {
    description: "拖拽文件到上方区域，或点击选择文件开始上传。",
  },
  review: {
    title: "恭喜，队列已清空",
    description: "当前没有待复核的工单，您可以休息一下或去上传新文档。",
  },
  documents: {
    description: "当前没有符合条件的文档，尝试调整筛选条件或上传新文档。",
  },
  retrieval: {
    description: "输入查询条件并选择集合和配置，开始检索验证。",
  },
  collections: {
    description: "当前没有知识库集合，创建一个新集合来组织文档。",
  },
  success: {
    title: "操作完成",
    description: "所有任务已处理完毕。",
  },
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  variant = "default",
  className,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title?: string;
  description?: string;
  action?: ReactNode;
  variant?: EmptyStateVariant;
  className?: string;
}) {
  const config = variantConfig[variant];
  const finalTitle = title || config.title || "暂无数据";
  const finalDesc = description || config.description;

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center relative",
        className
      )}
    >
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-48 h-48 rounded-full bg-primary/[0.03] blur-3xl" />
      </div>

      <div className="relative">
        <div className="glass rounded-2xl p-5 mb-5 inline-flex">
          <Icon className="h-8 w-8 text-primary/60" />
        </div>
        <h3 className="text-lg font-semibold text-foreground">{finalTitle}</h3>
        {finalDesc && (
          <p className="text-sm text-muted-foreground/70 mt-2 max-w-md">
            {finalDesc}
          </p>
        )}
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}
