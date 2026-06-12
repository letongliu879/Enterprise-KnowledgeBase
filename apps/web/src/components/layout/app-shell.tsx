"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
  Shield,
  Library,
  Command,
  Trash2,
  HelpCircle,
  AlertTriangle,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
} from "@/components/ui/tooltip";
import { useAppStore } from "@/lib/store";
import { workbenchApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/hooks/use-media-query";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useLoadingTimeout } from "@/hooks/use-loading-timeout";
import { useBroadcastSync } from "@/hooks/use-broadcast-sync";
import { toast } from "sonner";
import { overlayFade, slideInFromLeft, staggerItem } from "@/lib/animations";
import { NotificationCenter } from "@/features/notifications/notification-center";
import { Breadcrumb } from "@/components/breadcrumb";
import { OfflineToast } from "@/components/offline-toast";
import { CommandPalette } from "@/components/command-palette";
import { OnboardingTour } from "@/components/onboarding-tour";

const navItems = [
  { href: "/upload", label: "批量入库", icon: Upload },
  { href: "/review", label: "人工复核", icon: Inbox },
  { href: "/documents", label: "文档库", icon: Library },
  { href: "/trash", label: "回收站", icon: Trash2 },
  { href: "/retrieval", label: "检索验证", icon: Search },
  { href: "/collections", label: "知识库集合", icon: Database },
];

function isTrashRoute(pathname: string): boolean {
  return pathname === "/trash";
}


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

  const { timedOut, reset } = useLoadingTimeout({
    isLoading: healthAll.isLoading,
    timeoutMs: 10000,
  });

  // Reset the timeout when data arrives or error occurs
  useEffect(() => {
    if (healthAll.data || healthAll.error) {
      reset();
    }
  }, [healthAll.data, healthAll.error, reset]);

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
          Services
        </span>
      </div>
      <div className="flex items-center gap-2">
        {timedOut ? (
          <span className="text-[10px] text-muted-foreground/60">
            Loading timeout
          </span>
        ) : (
          services.map((s) => (
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
          ))
        )}
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
          All Healthy
        </Badge>
      )}
    </div>
  );
}

function CollectionSelector() {
  const { currentCollectionId, setCurrentCollectionId } = useAppStore();
  const { isAuthenticated, message } = useAuthGuard();
  const { data: me } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
    enabled: isAuthenticated,
  });
  const userTenantId = me?.tenant_id ?? "";
  const { data: collectionResponse, isLoading } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId && isAuthenticated,
  });
  const collections = collectionResponse?.items ?? [];

  const trigger = (
    <Select
      value={currentCollectionId || ""}
      onValueChange={(value) => setCurrentCollectionId(value || null)}
      disabled={!isAuthenticated || isLoading || collections.length === 0}
    >
      <SelectTrigger
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "h-8 min-w-[200px] gap-1.5 rounded-full border-input bg-background hover:bg-accent hover:border-primary/30 transition-all duration-200"
        )}
      >
        <Database className="h-3.5 w-3.5 text-primary" />
        <SelectValue
          placeholder={
            !isAuthenticated
              ? "请先配置令牌"
              : isLoading
              ? "Loading..."
              : "Select Collection"
          }
          className="max-w-[140px] truncate"
        />
      </SelectTrigger>
      <SelectContent className="w-64 rounded-xl border bg-popover shadow-lg">
        {collections.length === 0 && (
          <SelectItem value="__empty__" disabled className="text-muted-foreground">
            No collections
          </SelectItem>
        )}
        {collections.map((c, idx) => (
          <motion.div
            key={c.collection_id}
            variants={staggerItem}
            initial="hidden"
            animate="visible"
            custom={idx}
          >
            <SelectItem
              value={c.collection_id}
              className={cn(
                "rounded-lg cursor-pointer my-0.5",
                currentCollectionId === c.collection_id &&
                  "bg-primary/5 text-primary"
              )}
            >
              <div className="flex flex-col gap-0.5">
                <span className="font-medium text-sm">{c.name}</span>
                <span className="text-[10px] text-muted-foreground">
                  {c.lifecycle_state} 路 {c.collection_id}
                </span>
              </div>
            </SelectItem>
          </motion.div>
        ))}
      </SelectContent>
    </Select>
  );

  if (!isAuthenticated) {
    return (
      <Tooltip>
        <div>{trigger}</div>
        <TooltipContent>{message}</TooltipContent>
      </Tooltip>
    );
  }

  return trigger;
}

function SidebarContent({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-16 shrink-0 border-b border-border">
        <div className="relative">
          <Shield className="h-5 w-5 text-primary" />
          <div className="absolute inset-0 blur-md bg-primary/30 rounded-full" />
        </div>
        <span className="font-semibold text-sm tracking-tight truncate text-foreground">
          Knowledge Workbench
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1" aria-label="主导航">
        {navItems.map((item) => {
          const active = item.href === "/trash"
            ? pathname === "/trash"
            : pathname.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href} onClick={onNavigate}>
              <div
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm transition-all duration-200 cursor-pointer group",
                  active
                    ? "bg-primary/10 text-primary font-medium border border-primary/10"
                    : "text-sidebar-foreground hover:bg-accent hover:text-foreground border border-transparent"
                )}
                role="navigation"
                aria-current={active ? "page" : undefined}
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
          Retrieval workbench
        </p>
        <p className="flex items-center gap-1.5">
          <span className="w-1 h-1 rounded-full bg-muted-foreground/20" />
          Non-answer-generation agent
        </p>
      </div>
    </>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const pathname = usePathname();
  const isMobile = useIsMobile();
  const sidebarOpen = isMobile ? mobileSidebarOpen : desktopSidebarOpen;
  const router = useRouter();
  const mainRef = useRef<HTMLElement>(null);
  const skipLinkRef = useRef<HTMLAnchorElement>(null);

  // Cross-tab state synchronisation
  useBroadcastSync();

  const closeSidebar = () => {
    if (isMobile) {
      setMobileSidebarOpen(false);
    }
  };

  const toggleSidebar = () => {
    if (isMobile) {
      setMobileSidebarOpen((open) => !open);
      return;
    }

    setDesktopSidebarOpen((open) => !open);
  };

  const triggerCommandPalette = useCallback(() => {
    setCommandPaletteOpen(true);
  }, []);

  // Listen for 401 events from the API client and show auth feedback
  useEffect(() => {
    const handleAuthFailure = () => {
      toast.error("认证令牌已过期或无效，请前往设置页面重新配置", {
        action: {
          label: "前往设置",
          onClick: () => router.push("/settings"),
        },
        duration: 5000,
      });
    };

    window.addEventListener("ekb:auth-failed", handleAuthFailure);
    return () => window.removeEventListener("ekb:auth-failed", handleAuthFailure);
  }, [router]);

  // Show auth warning toaster on mount if no token configured
  const { isAuthenticated } = useAuthGuard();
  const [authWarned, setAuthWarned] = useState(false);
  useEffect(() => {
    if (!isAuthenticated && !authWarned) {
      setAuthWarned(true);
      toast("尚未配置认证令牌，部分功能将不可用", {
        action: {
          label: "去配置",
          onClick: () => router.push("/settings"),
        },
        duration: 8000,
      });
    }
  }, [isAuthenticated, authWarned, router]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Skip-to-content link for keyboard/a11y users */}
      <a
        ref={skipLinkRef}
        href="#main-content"
        className="fixed left-2 top-2 z-[200] -translate-y-full focus:translate-y-0 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg transition-transform focus:outline-none focus-visible:outline-none"
        onClick={(e) => {
          e.preventDefault();
          mainRef.current?.focus();
        }}
      >
        跳转到内容
      </a>

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
              onClick={closeSidebar}
            />
            <motion.aside
              variants={slideInFromLeft}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed left-0 top-0 bottom-0 z-50 w-[280px] bg-sidebar border-r border-sidebar-border flex flex-col overflow-hidden shadow-xl"
            >
              <SidebarContent pathname={pathname} onNavigate={closeSidebar} />
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
              onClick={toggleSidebar}
              aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
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

            {/* Token warning badge — subtle indicator when unauthenticated */}
            {!isAuthenticated && (
              <Link href="/settings">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-xl hover:bg-amber-500/10 hover:text-amber-400 transition-colors relative"
                  aria-label="请配置认证令牌"
                >
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                </Button>
              </Link>
            )}

            <NotificationCenter />

            {/* Search trigger: desktop shows full button, mobile shows icon only */}
            <button
              onClick={triggerCommandPalette}
              className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:border-white/20 transition-all"
              title="Cmd+K 全局搜索"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="hidden md:inline">搜索</span>
              <kbd className="hidden md:inline-flex rounded border border-white/10 bg-white/[0.03] px-1 font-mono text-[10px]">⌘K</kbd>
            </button>

            <Link href="/help">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 rounded-xl hover:bg-accent transition-colors"
                aria-label="Open help center"
              >
                <HelpCircle className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/settings">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 rounded-xl hover:bg-accent transition-colors"
                aria-label="Open settings"
              >
                <Settings className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </header>

        {/* Content Area */}
        <main
          ref={mainRef}
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-auto p-6 focus:outline-none"
        >
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
            className="mx-auto max-w-7xl"
          >
            {/* Breadcrumb */}
            <div className="mb-4">
              <Breadcrumb />
            </div>
            {children}
          </motion.div>
        </main>

        {/* Global Overlays */}
        <CommandPalette open={commandPaletteOpen} onOpenChange={setCommandPaletteOpen} />
        <OnboardingTour />
        <OfflineToast />
      </div>
    </div>
  );
}
