"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  Inbox,
  Search,
  Database,
  Settings,
  Menu,
  X,
  Activity,
  ChevronDown,
  Shield,
  Library,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppStore } from "@/lib/store";
import { workbenchApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/upload", label: "批量入库", icon: Upload },
  { href: "/review", label: "人工复核", icon: Inbox },
  { href: "/documents", label: "文档库", icon: Library },
  { href: "/retrieval", label: "检索验证", icon: Search },
  { href: "/collections", label: "知识库集合", icon: Database },
];

function HealthDot({ status }: { status?: string }) {
  const color =
    status === "ok" || status === "healthy" || status === "UP"
      ? "bg-emerald-500"
      : status === "degraded"
      ? "bg-amber-500"
      : "bg-red-500";
  return (
    <span className={cn("inline-block h-2 w-2 rounded-full", color)} />
  );
}

function BackendHealth() {
  const healthAll = useQuery({
    queryKey: ["health", "all"],
    queryFn: () => workbenchApi.healthAll(),
    retry: 1,
    refetchInterval: 30000,
  });

  const services = [
    { name: "Admin", status: healthAll.data?.services?.admin?.status },
    { name: "Workbench", status: healthAll.data?.workbench?.status },
    { name: "Access", status: healthAll.data?.services?.access?.status },
    { name: "Retrieval", status: healthAll.data?.services?.retrieval?.status },
    { name: "Ingestion", status: healthAll.data?.services?.ingestion?.status },
  ];

  const allHealthy = healthAll.data?.all_healthy ?? false;

  return (
    <div className="flex items-center gap-3 px-3">
      <div className="flex items-center gap-1.5">
        <Activity className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">服务状态</span>
      </div>
      <div className="flex items-center gap-2">
        {services.map((s) => (
          <div key={s.name} className="flex items-center gap-1" title={s.name}>
            {healthAll.isLoading ? (
              <Skeleton className="h-2 w-2 rounded-full" />
            ) : (
              <HealthDot status={s.status || (healthAll.error ? "down" : "ok")} />
            )}
            <span className="text-[10px] text-muted-foreground hidden lg:inline">
              {s.name}
            </span>
          </div>
        ))}
      </div>
      {allHealthy && (
        <Badge variant="secondary" className="text-[10px] h-5">
          全部正常
        </Badge>
      )}
    </div>
  );
}

function CollectionSelector() {
  const { currentCollectionId, setCurrentCollectionId } = useAppStore();
  const { data: me } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";
  const { data: collectionResponse, isLoading } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });
  const collections = collectionResponse?.items ?? [];

  const selected = collections?.find((c) => c.collection_id === currentCollectionId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "h-8 gap-1"
        )}
      >
        <Database className="h-3.5 w-3.5" />
        <span className="max-w-[140px] truncate">
          {isLoading ? "加载中..." : selected ? selected.name : "选择知识库集合"}
        </span>
        <ChevronDown className="h-3 w-3 opacity-50" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        {collections.length === 0 && (
          <DropdownMenuItem disabled>暂无集合</DropdownMenuItem>
        )}
        {collections.map((c) => (
          <DropdownMenuItem
            key={c.collection_id}
            onClick={() => setCurrentCollectionId(c.collection_id)}
          >
            <div className="flex flex-col">
              <span className="font-medium">{c.name}</span>
              <span className="text-xs text-muted-foreground">
                {c.lifecycle_state}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const pathname = usePathname();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 240, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="border-r bg-sidebar flex flex-col overflow-hidden shrink-0"
          >
            <div className="flex items-center gap-2 px-4 h-14 border-b shrink-0">
              <Shield className="h-5 w-5 text-primary" />
              <span className="font-semibold text-sm tracking-tight truncate">
                知识库工作台
              </span>
            </div>
            <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
              {navItems.map((item) => {
                const active = pathname.startsWith(item.href);
                return (
                  <Link key={item.href} href={item.href}>
                    <div
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors cursor-pointer",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                          : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                      )}
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      <span>{item.label}</span>
                    </div>
                  </Link>
                );
              })}
            </nav>
            <div className="px-3 py-3 border-t text-[10px] text-muted-foreground space-y-1 shrink-0">
              <p>检索上下文工作台</p>
              <p>非问答生成机器人</p>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top bar */}
        <header className="h-14 border-b flex items-center justify-between px-4 shrink-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setSidebarOpen((o) => !o)}
            >
              {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </Button>
            <BackendHealth />
          </div>
          <div className="flex items-center gap-3">
            <CollectionSelector />
            <Link href="/settings">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <Settings className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6">
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="mx-auto max-w-7xl"
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}
