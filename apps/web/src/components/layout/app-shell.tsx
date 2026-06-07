"use client";

import { useState, useEffect } from "react";
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
import { useIsMobile } from "@/hooks/use-media-query";
import { overlayFade, slideInFromLeft, staggerItem } from "@/lib/animations";

const navItems = [
  { href: "/upload", label: "批量入库", icon: Upload },
  { href: "/review", label: "人工复核", icon: Inbox },
  { href: "/documents", label: "文档库", icon: Library },
  { href: "/retrieval", label: "检索验证", icon: Search },
  { href: "/collections", label: "知识库集合", icon: Database },
];

function HealthDot({ status, title }: { status?: string; title?: string }) {
  const isHealthy =
    status === "ok" || status === "healthy" || status === "UP";
  const isDegraded = status === "degraded";

  return (
    <div className="relative flex items-center justify-center" title={title}>
      <span
        className={cn(
          "inline-block h-2 w-2 rounded-full",
          isHealthy
            ? "bg-emerald-500"
            : isDegraded
            ? "bg-amber-500"
            : "bg-red-500"
        )}
      />
      {isHealthy && (
        <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-emerald-500 opacity-30" />
      )}
    </div>
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
        <span className="text-xs text-muted-foreground hidden sm:inline">
          服务状态
        </span>
      </div>
      <div className="flex items-center gap-2">
        {services.map((s) => (
          <div
            key={s.name}
            className="flex items-center gap-1"
            title={`${s.name}: ${s.status || "checking"}`}
          >
            {healthAll.isLoading ? (
              <Skeleton className="h-2 w-2 rounded-full" />
            ) : (
              <HealthDot
                status={s.status || (healthAll.error ? "down" : "ok")}
                title={s.name}
              />
            )}
            <span className="text-[10px] text-muted-foreground hidden lg:inline">
              {s.name}
            </span>
          </div>
        ))}
      </div>
      {allHealthy && (
        <Badge
          variant="outline"
          className="text-[10px] h-5 border-emerald-200 bg-emerald-50 text-emerald-600"
        >
          <span className="relative flex h-1.5 w-1.5 mr-1">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-50" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
          </span>
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

  const selected = collections?.find(
    (c) => c.collection_id === currentCollectionId
  );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "h-8 gap-1.5 rounded-full border-input bg-background hover:bg-accent hover:border-primary/30 transition-all duration-200"
        )}
      >
        <Database className="h-3.5 w-3.5 text-primary" />
        <span className="max-w-[140px] truncate">
          {isLoading ? "加载中..." : selected ? selected.name : "选择知识库集合"}
        </span>
        <ChevronDown className="h-3 w-3 opacity-50" />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-64 bg-popover rounded-xl border shadow-lg"
      >
        {collections.length === 0 && (
          <DropdownMenuItem disabled className="text-muted-foreground">
            暂无集合
          </DropdownMenuItem>
        )}
        {collections.map((c, idx) => (
          <motion.div
            key={c.collection_id}
            variants={staggerItem}
            initial="hidden"
            animate="visible"
            custom={idx}
          >
            <DropdownMenuItem
              onClick={() => setCurrentCollectionId(c.collection_id)}
              className={cn(
                "rounded-lg cursor-pointer my-0.5",
                currentCollectionId === c.collection_id &&
                  "bg-primary/5 text-primary"
              )}
            >
              <div className="flex flex-col gap-0.5">
                <span className="font-medium text-sm">{c.name}</span>
                <span className="text-[10px] text-muted-foreground">
                  {c.lifecycle_state} · {c.collection_id}
                </span>
              </div>
            </DropdownMenuItem>
          </motion.div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SidebarContent({ pathname }: { pathname: string }) {
  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-16 shrink-0 border-b border-border">
        <div className="relative">
          <Shield className="h-5 w-5 text-primary" />
          <div className="absolute inset-0 blur-md bg-primary/30 rounded-full" />
        </div>
        <span className="font-semibold text-sm tracking-tight truncate text-foreground">
          知识库工作台
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href}>
              <div
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm transition-all duration-200 cursor-pointer group",
                  active
                    ? "bg-primary/10 text-primary font-medium border border-primary/10"
                    : "text-sidebar-foreground hover:bg-accent hover:text-foreground border border-transparent"
                )}
              >
                <item.icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-transform duration-200",
                    active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
                    active && "scale-110"
                  )}
                />
                <span>{item.label}</span>
                {active && (
                  <div className="ml-auto h-1.5 w-1.5 rounded-full bg-primary animate-pulse-glow" />
                )}
              </div>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-border text-[10px] text-muted-foreground space-y-1.5 shrink-0">
        <p className="flex items-center gap-1.5">
          <span className="w-1 h-1 rounded-full bg-primary/40" />
          检索上下文工作台
        </p>
        <p className="flex items-center gap-1.5">
          <span className="w-1 h-1 rounded-full bg-muted-foreground/20" />
          非问答生成机器人
        </p>
      </div>
    </>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const pathname = usePathname();
  const isMobile = useIsMobile();

  useEffect(() => {
    if (isMobile) {
      setSidebarOpen(false);
    } else {
      setSidebarOpen(true);
    }
  }, [isMobile]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Desktop Sidebar */}
      {!isMobile && (
        <AnimatePresence initial={false}>
          {sidebarOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 260, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
              className="bg-sidebar border-r border-sidebar-border flex flex-col overflow-hidden shrink-0 shadow-sm"
            >
              <SidebarContent pathname={pathname} />
            </motion.aside>
          )}
        </AnimatePresence>
      )}

      {/* Mobile Sidebar Drawer */}
      <AnimatePresence>
        {isMobile && sidebarOpen && (
          <>
            <motion.div
              variants={overlayFade}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
              onClick={() => setSidebarOpen(false)}
            />
            <motion.aside
              variants={slideInFromLeft}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed left-0 top-0 bottom-0 z-50 w-[280px] bg-sidebar border-r border-sidebar-border flex flex-col overflow-hidden shadow-xl"
            >
              <SidebarContent pathname={pathname} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="mx-4 mt-3 mb-1 h-12 rounded-2xl bg-card border border-border shadow-sm flex items-center justify-between px-4 shrink-0 z-30">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-xl hover:bg-accent transition-colors"
              onClick={() => setSidebarOpen((o) => !o)}
              aria-label={sidebarOpen ? "关闭侧边栏" : "打开侧边栏"}
            >
              <AnimatePresence mode="wait" initial={false}>
                {sidebarOpen ? (
                  <motion.div
                    key="close"
                    initial={{ rotate: -90, opacity: 0 }}
                    animate={{ rotate: 0, opacity: 1 }}
                    exit={{ rotate: 90, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <X className="h-4 w-4" />
                  </motion.div>
                ) : (
                  <motion.div
                    key="menu"
                    initial={{ rotate: 90, opacity: 0 }}
                    animate={{ rotate: 0, opacity: 1 }}
                    exit={{ rotate: -90, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <Menu className="h-4 w-4" />
                  </motion.div>
                )}
              </AnimatePresence>
            </Button>
            <BackendHealth />
          </div>
          <div className="flex items-center gap-3">
            <CollectionSelector />
            <Link href="/settings">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 rounded-xl hover:bg-accent transition-colors"
                aria-label="打开设置"
              >
                <Settings className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </header>

        {/* Content Area */}
        <main className="flex-1 overflow-auto p-6">
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
            className="mx-auto max-w-7xl"
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}
