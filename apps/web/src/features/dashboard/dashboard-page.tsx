"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Upload, Clock, FileText, AlertTriangle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EmptyState } from "@/components/empty-state";
import { workbenchApi } from "@/lib/api/client";
import type { DashboardResponse } from "@/lib/api/types";

const staggerContainer = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
    },
  },
};

const fadeInUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" as const } },
};

function formatNumber(num: number): string {
  return new Intl.NumberFormat("zh-CN").format(num);
}

function formatPercent(ratio: number): string {
  if (ratio === 0) return "0%";
  if (ratio === 1) return "100%";
  const pct = ratio * 100;
  // Check if it has decimal places
  if (Number.isInteger(pct)) return `${pct}%`;
  // For values like 12.5, toFixed(0) would give 13 which is wrong.
  // We need to preserve up to 1 decimal place when present.
  return `${pct.toFixed(1).replace(/\.0$/, "")}%`;
}

const statConfig = [
  {
    key: "today_uploads" as const,
    label: "今日上传",
    icon: Upload,
  },
  {
    key: "pending_review_count" as const,
    label: "待复核",
    icon: Clock,
  },
  {
    key: "total_documents" as const,
    label: "总文档数",
    icon: FileText,
  },
  {
    key: "stale_ratio" as const,
    label: "过期比例",
    icon: AlertTriangle,
  },
];

function StatSkeletons() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} data-testid="stat-skeleton">
          <CardHeader>
            <Skeleton className="h-4 w-20" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-8 w-16" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function StatCards({ stats }: { stats: DashboardResponse["stats"] }) {
  return (
    <motion.div
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      variants={staggerContainer}
      initial="hidden"
      animate="show"
    >
      {statConfig.map((cfg) => {
        const value = stats[cfg.key];
        const displayValue =
          cfg.key === "stale_ratio" ? formatPercent(value as number) : formatNumber(value as number);
        const Icon = cfg.icon;

        return (
          <motion.div key={cfg.key} variants={fadeInUp}>
            <Card className="glass">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <div className="p-1.5 rounded-md bg-primary/10">
                    <Icon className="h-4 w-4 text-primary" />
                  </div>
                  {cfg.label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{displayValue}</div>
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
    </motion.div>
  );
}

function TicketList({ tickets }: { tickets: DashboardResponse["recent_tickets"] }) {
  const router = useRouter();

  return (
    <motion.div
      className="grid grid-cols-1 gap-3"
      variants={staggerContainer}
      initial="hidden"
      animate="show"
    >
      {tickets.map((ticket) => (
        <motion.div key={ticket.ticket_id} variants={fadeInUp}>
          <Card
            interactive
            className="glass cursor-pointer"
            data-testid="ticket-card"
            onClick={() => router.push(`/review/${ticket.ticket_id}`)}
          >
            <CardContent className="py-3">
              <div className="flex items-center justify-between">
                <div className="font-medium text-sm truncate">
                  {ticket.filename || ticket.title || ticket.ticket_id}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </motion.div>
  );
}

export function DashboardPage() {
  const { data, isLoading, isError, error } = useQuery<DashboardResponse>({
    queryKey: ["dashboard"],
    queryFn: () => workbenchApi.getDashboard(),
  });

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <StatSkeletons />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6">
        <Alert variant="destructive" role="alert">
          <AlertDescription>加载仪表盘数据失败</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-6">
        <Alert variant="destructive" role="alert">
          <AlertDescription>加载仪表盘数据失败</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (data.stats.total_documents === 0) {
    return (
      <div className="p-6">
        <EmptyState
          icon={FileText}
          title="暂无数据"
          description="当前没有文档数据，请上传文档后开始使用。"
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <StatCards stats={data.stats} />

      <div>
        <h2 className="text-lg font-semibold mb-4">最近工单</h2>
        <TicketList tickets={data.recent_tickets} />
      </div>
    </div>
  );
}
