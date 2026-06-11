"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Upload,
  Clock,
  FileText,
  AlertTriangle,
  Inbox,
  Search,
  Database,
  Settings,
  FolderOpen,
  Bell,
  ArrowRight,
  Sparkles,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EmptyState } from "@/components/empty-state";
import { workbenchApi } from "@/lib/api/client";
import type { DashboardResponse } from "@/lib/api/types";
import { staggerContainer, staggerItem, fadeInUp } from "@/lib/animations";

function formatNumber(num: number): string {
  return new Intl.NumberFormat("zh-CN").format(num);
}

function formatPercent(ratio: number): string {
  if (ratio === 0) return "0%";
  if (ratio === 1) return "100%";
  const pct = ratio * 100;
  if (Number.isInteger(pct)) return `${pct}%`;
  return `${pct.toFixed(1).replace(/\.0$/, "")}%`;
}

function useCurrentTime() {
  return useMemo(() => {
    const now = new Date();
    const hour = now.getHours();
    let greeting = "晚上好";
    if (hour < 12) greeting = "早上好";
    else if (hour < 18) greeting = "下午好";
    return {
      greeting,
      date: now.toLocaleDateString("zh-CN", {
        year: "numeric",
        month: "long",
        day: "numeric",
        weekday: "long",
      }),
    };
  }, []);
}

const statConfig = [
  { key: "today_uploads" as const, label: "今日上传", icon: Upload },
  { key: "pending_review_count" as const, label: "待复核", icon: Clock },
  { key: "total_documents" as const, label: "总文档数", icon: FileText },
  { key: "stale_ratio" as const, label: "过期比例", icon: AlertTriangle },
];

const quickActions = [
  {
    label: "上传文档",
    description: "批量入库",
    icon: Upload,
    href: "/upload",
    color: "bg-emerald-500/10 text-emerald-400",
  },
  {
    label: "复核队列",
    description: "待审核工单",
    icon: Inbox,
    href: "/review",
    color: "bg-amber-500/10 text-amber-400",
  },
  {
    label: "文档库",
    description: "浏览文档",
    icon: Database,
    href: "/documents",
    color: "bg-sky-500/10 text-sky-400",
  },
  {
    label: "检索验证",
    description: "验证检索效果",
    icon: Search,
    href: "/retrieval",
    color: "bg-violet-500/10 text-violet-400",
  },
  {
    label: "知识库集合",
    description: "管理集合",
    icon: FolderOpen,
    href: "/collections",
    color: "bg-rose-500/10 text-rose-400",
  },
  {
    label: "系统设置",
    description: "偏好配置",
    icon: Settings,
    href: "/settings",
    color: "bg-slate-500/10 text-slate-400",
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
      animate="visible"
    >
      {statConfig.map((cfg) => {
        const value = stats[cfg.key];
        const displayValue =
          cfg.key === "stale_ratio"
            ? formatPercent(value as number)
            : formatNumber(value as number);
        const Icon = cfg.icon;
        return (
          <motion.div key={cfg.key} variants={staggerItem}>
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

function QuickActions() {
  return (
    <motion.div
      className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3"
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {quickActions.map((action) => {
        const Icon = action.icon;
        return (
          <motion.div key={action.label} variants={staggerItem}>
            <Link href={action.href}>
              <Card
                interactive
                className="glass cursor-pointer h-full"
                data-testid="quick-action"
              >
                <CardContent className="p-4 flex flex-col items-center text-center gap-2">
                  <div className={`p-2.5 rounded-xl ${action.color}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="font-medium text-sm">{action.label}</div>
                  <div className="text-xs text-muted-foreground">{action.description}</div>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        );
      })}
    </motion.div>
  );
}

function RecentTickets({ tickets }: { tickets: DashboardResponse["recent_tickets"] }) {
  return (
    <motion.div
      className="grid grid-cols-1 gap-3"
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {tickets.map((ticket) => (
        <motion.div key={ticket.ticket_id} variants={staggerItem}>
          <Link href={`/review/${ticket.ticket_id}`}>
            <Card interactive className="glass cursor-pointer">
              <CardContent className="py-3 flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="font-medium text-sm truncate">
                    {ticket.filename || ticket.title || ticket.ticket_id}
                  </span>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
              </CardContent>
            </Card>
          </Link>
        </motion.div>
      ))}
    </motion.div>
  );
}

function AnnouncementBanner() {
  return (
    <motion.div variants={fadeInUp} initial="hidden" animate="visible">
      <Alert className="glass border-primary/20">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary shrink-0" />
          <AlertDescription className="text-sm">
            欢迎使用 Knowledge Workbench！新功能持续更新中，如有问题请联系技术支持。
          </AlertDescription>
        </div>
      </Alert>
    </motion.div>
  );
}

export default function HomePage() {
  const { greeting, date } = useCurrentTime();
  const { data, isLoading, isError, error } = useQuery<DashboardResponse>({
    queryKey: ["dashboard"],
    queryFn: () => workbenchApi.getDashboard(),
  });

  return (
    <motion.div
      className="space-y-8"
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={staggerItem} className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {greeting}，欢迎来到 Knowledge Workbench
        </h1>
        <p className="text-sm text-muted-foreground">{date}</p>
      </motion.div>

      {/* Announcement */}
      <AnnouncementBanner />

      {/* Quick Actions */}
      <motion.div variants={staggerItem} className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">快捷操作</h2>
        </div>
        <QuickActions />
      </motion.div>

      {/* Stats */}
      <motion.div variants={staggerItem} className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">数据概览</h2>
        </div>
        {isLoading ? (
          <StatSkeletons />
        ) : isError ? (
          <Alert variant="destructive" role="alert">
            <AlertDescription>加载仪表盘数据失败</AlertDescription>
          </Alert>
        ) : data?.stats.total_documents === 0 ? (
          <EmptyState
            icon={FileText}
            title="暂无数据"
            description="当前没有文档数据，请上传文档后开始使用。"
          />
        ) : data ? (
          <StatCards stats={data.stats} />
        ) : null}
      </motion.div>

      {/* Recent Tickets */}
      <motion.div variants={staggerItem} className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">最近工单</h2>
          <Link href="/review">
            <Badge variant="outline" className="cursor-pointer hover:bg-white/[0.06]">
              查看全部
            </Badge>
          </Link>
        </div>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-xl" />
            ))}
          </div>
        ) : data?.recent_tickets && data.recent_tickets.length > 0 ? (
          <RecentTickets tickets={data.recent_tickets} />
        ) : (
          <EmptyState
            icon={Inbox}
            variant="review"
            action={
              <Link href="/upload">
                <Badge variant="outline" className="cursor-pointer">去上传文档</Badge>
              </Link>
            }
          />
        )}
      </motion.div>
    </motion.div>
  );
}
