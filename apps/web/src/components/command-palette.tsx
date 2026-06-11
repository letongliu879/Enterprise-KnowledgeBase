"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  FileText,
  Inbox,
  Database,
  LayoutDashboard,
  X,
  Command,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { workbenchApi } from "@/lib/api/client";
import { useHotkeys, useEscapeKey } from "@/hooks/use-hotkeys";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface SearchResult {
  id: string;
  type: "document" | "ticket" | "collection" | "page";
  title: string;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
}

const staticPages: SearchResult[] = [
  { id: "page-upload", type: "page", title: "批量入库", icon: LayoutDashboard, href: "/upload" },
  { id: "page-review", type: "page", title: "人工复核", icon: Inbox, href: "/review" },
  { id: "page-documents", type: "page", title: "文档库", icon: FileText, href: "/documents" },
  { id: "page-retrieval", type: "page", title: "检索验证", icon: Search, href: "/retrieval" },
  { id: "page-collections", type: "page", title: "知识库集合", icon: Database, href: "/collections" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();

  useHotkeys([
    { key: "k", meta: true, handler: () => setOpen((v) => !v), preventDefault: true },
    { key: "k", ctrl: true, handler: () => setOpen((v) => !v), preventDefault: true },
  ]);
  useEscapeKey(() => setOpen(false), open);

  const { data: documentsData, isLoading: docsLoading } = useQuery({
    queryKey: ["command-palette", "documents", query],
    queryFn: () => workbenchApi.listDocuments({ limit: 20 }),
    enabled: open && query.length > 0,
    staleTime: 60000,
  });

  const { data: ticketsData, isLoading: ticketsLoading } = useQuery({
    queryKey: ["command-palette", "tickets", query],
    queryFn: () => workbenchApi.listTickets({ page_size: 20 }),
    enabled: open && query.length > 0,
    staleTime: 60000,
  });

  const { data: collectionsData, isLoading: collsLoading } = useQuery({
    queryKey: ["command-palette", "collections"],
    queryFn: () => workbenchApi.listCollections(),
    enabled: open,
    staleTime: 60000,
  });

  const results = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return staticPages;

    const items: SearchResult[] = [...staticPages];

    documentsData?.items?.forEach((d) => {
      if (
        d.filename?.toLowerCase().includes(q) ||
        d.doc_id?.toLowerCase().includes(q)
      ) {
        items.push({
          id: `doc-${d.doc_id}`,
          type: "document",
          title: d.filename || d.doc_id || "未命名文档",
          subtitle: d.doc_id,
          icon: FileText,
          href: `/documents/${d.doc_id}`,
        });
      }
    });

    ticketsData?.items?.forEach((t) => {
      if (
        t.ticket_id?.toLowerCase().includes(q) ||
        t.filename?.toLowerCase().includes(q) ||
        t.title?.toLowerCase().includes(q)
      ) {
        items.push({
          id: `ticket-${t.ticket_id}`,
          type: "ticket",
          title: t.filename || t.title || t.ticket_id,
          subtitle: t.ticket_id,
          icon: Inbox,
          href: `/review/${t.ticket_id}`,
        });
      }
    });

    collectionsData?.items?.forEach((c) => {
      if (
        c.name?.toLowerCase().includes(q) ||
        c.collection_id?.toLowerCase().includes(q)
      ) {
        items.push({
          id: `coll-${c.collection_id}`,
          type: "collection",
          title: c.name,
          subtitle: c.collection_id,
          icon: Database,
          href: `/collections`,
        });
      }
    });

    return items;
  }, [query, documentsData, ticketsData, collectionsData]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setSelectedIndex(0);
    }
  }, [open]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => (i - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = results[selectedIndex];
      if (item) {
        router.push(item.href);
        setOpen(false);
      }
    }
  };

  const isLoading = docsLoading || ticketsLoading || collsLoading;

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-[90] bg-black/40 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, y: -20, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.96 }}
              transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
              className="mx-auto mt-[15vh] w-full max-w-xl px-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-card shadow-2xl"
              >
                {/* Search Input */}
                <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3"
                >
                  <Search className="h-5 w-5 text-muted-foreground shrink-0" />
                  <Input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="搜索文档、工单、集合或页面..."
                    className="border-0 bg-transparent shadow-none focus-visible:ring-0 h-auto px-0 text-base"
                    autoFocus
                  />
                  <div className="flex items-center gap-1 text-xs text-muted-foreground shrink-0"
                  >
                    <kbd className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px]">
                      ESC
                    </kbd>
                    <button
                      onClick={() => setOpen(false)}
                      className="ml-1 rounded-md p-1 hover:bg-accent transition-colors"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Results */}
                <div className="max-h-[50vh] overflow-auto p-1.5">
                  {isLoading && query.length > 0 ? (
                    <div className="space-y-1.5 p-2">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-10 rounded-lg" />
                      ))}
                    </div>
                  ) : results.length === 0 ? (
                    <div className="py-8 text-center text-sm text-muted-foreground"
                    >
                      未找到结果
                    </div>
                  ) : (
                    <div className="space-y-0.5">
                      {results.map((item, index) => {
                        const Icon = item.icon;
                        const isSelected = index === selectedIndex;
                        return (
                          <button
                            key={item.id}
                            onClick={() => {
                              router.push(item.href);
                              setOpen(false);
                            }}
                            onMouseEnter={() => setSelectedIndex(index)}
                            className={cn(
                              "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
                              isSelected
                                ? "bg-primary/10 text-primary"
                                : "text-foreground hover:bg-accent"
                            )}
                          >
                            <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                            <div className="flex-1 min-w-0"
                            >
                              <p className="font-medium truncate"
                              >{item.title}</p
                              >
                              {item.subtitle && (
                                <p className="text-xs text-muted-foreground truncate"
                                >{item.subtitle}</p>
                              )}
                            </div>
                            <span className="text-[10px] text-muted-foreground/60 shrink-0 capitalize"
                            >
                              {item.type === "page"
                                ? "页面"
                                : item.type === "document"
                                ? "文档"
                                : item.type === "ticket"
                                ? "工单"
                                : "集合"}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="flex items-center gap-4 border-t border-white/[0.06] px-4 py-2 text-[10px] text-muted-foreground/60"
                >
                  <div className="flex items-center gap-1"
                  >
                    <Command className="h-3 w-3" />
                    <span>K 打开</span>
                  </div>
                  <span>
                    <kbd className="rounded border border-white/10 bg-white/5 px-1 font-mono">↑↓</kbd> 选择
                  </span>
                  <span>
                    <kbd className="rounded border border-white/10 bg-white/5 px-1 font-mono">↵</kbd> 跳转
                  </span>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
