"use client";

import { useState, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Hash,
  FileText,
  BookOpen,
  Sparkles,
  AlertCircle,
  Info,
  ThumbsUp,
  ThumbsDown,
  Download,
  Clock,
  History,
  Lightbulb,
  Settings,
  BarChart3,
  Code,
  SlidersHorizontal,
  Eye,
  GitCompare,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { BackendGap } from "@/components/backend-gap";
import { EmptyState } from "@/components/empty-state";
import { isBackendGap, isApiError } from "@/lib/api/errors";
import { toast } from "sonner";
import { staggerContainer, staggerItem } from "@/lib/animations";
import { useLocalStorage } from "@/hooks/use-local-storage";
import Link from "next/link";

const EXAMPLE_QUERIES = [
  "产品手册使用规范",
  "API 调用方法",
  "安全合规要求",
  "故障排查指南",
  "部署配置说明",
];

const RECENT_QUERIES_KEY = "ekb-recent-queries";
const MAX_RECENT_QUERIES = 5;

interface QueryRunItem {
  query_run_id: string;
  query: string;
  collection_id: string;
  retrieval_profile_id: string;
  created_at: string;
  latency_ms?: number;
}

export default function RetrievalPage() {
  const { currentCollectionId, setCurrentCollectionId } = useAppStore();
  const [query, setQuery] = useState("");
  const [tokenBudget, setTokenBudget] = useState("2000");
  const [retrievalProfileId, setRetrievalProfileId] = useState("");
  const [debug, setDebug] = useState<"none" | "basic" | "full">("none");
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // H8: Advanced mode state
  const [advancedMode, setAdvancedMode] = useState(false);
  const [booleanMode, setBooleanMode] = useState(false);
  const [docIdFilter, setDocIdFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // H2: Comparison mode state
  const [compareMode, setCompareMode] = useState(false);
  const [compareProfileId, setCompareProfileId] = useState("");

  // Search timing: frontend-measured latency
  const [frontendLatency, setFrontendLatency] = useState<number | null>(null);
  const searchStartTimeRef = useRef<number | null>(null);

  // Recent queries from localStorage
  const [recentQueriesStorage, setRecentQueriesStorage] = useLocalStorage<string[]>(
    RECENT_QUERIES_KEY,
    []
  );

  // Query input focus state for showing suggestions
  const [queryFocused, setQueryFocused] = useState(false);

  const { data: me } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";

  const { data: collectionResponse, isLoading: collectionsLoading } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });
  const collections = collectionResponse?.items ?? [];

  const { data: profiles, isLoading: profilesLoading } = useQuery({
    queryKey: ["workbench-retrieval-profiles"],
    queryFn: () => workbenchApi.listRetrievalProfiles("published"),
  });
  const retrievalProfiles = profiles?.items ?? [];

  // H1: Query runs history
  const { data: queryRunsResponse } = useQuery({
    queryKey: ["query-runs"],
    queryFn: () => workbenchApi.listQueryRuns({ limit: 20 }),
    enabled: true,
  });
  const queryRuns = (queryRunsResponse?.items ?? []) as QueryRunItem[];
  const recentQueries = queryRuns.slice(0, 20);

  // Helper to save query to localStorage history
  const saveQueryToHistory = useCallback((q: string) => {
    if (!q.trim()) return;
    setRecentQueriesStorage((prev) => {
      const filtered = prev.filter((item) => item !== q);
      return [q, ...filtered].slice(0, MAX_RECENT_QUERIES);
    });
  }, [setRecentQueriesStorage]);

  // Main retrieve query
  const {
    data: result,
    isLoading: searching,
    error: searchError,
    refetch,
  } = useQuery({
    queryKey: [
      "retrieve",
      query,
      currentCollectionId,
      retrievalProfileId,
      tokenBudget,
    ],
    queryFn: async () => {
      const res = await workbenchApi.retrieve({
        query,
        collection_id: currentCollectionId || "",
        retrieval_profile_id: retrievalProfileId,
        token_budget: parseInt(tokenBudget, 10) || 2000,
        debug,
      });
      return res;
    },
    enabled: false,
  });

  // H2: Comparison retrieve query
  const {
    data: compareResult,
    isLoading: compareSearching,
    error: compareSearchError,
    refetch: refetchCompare,
  } = useQuery({
    queryKey: [
      "retrieve-compare",
      query,
      currentCollectionId,
      compareProfileId,
      tokenBudget,
    ],
    queryFn: () =>
      workbenchApi.retrieve({
        query,
        collection_id: currentCollectionId || "",
        retrieval_profile_id: compareProfileId,
        token_budget: parseInt(tokenBudget, 10) || 2000,
        debug,
      }),
    enabled: false,
  });

  const toggleExpand = (idx: number) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const expandAll = () => {
    const all = new Set(
      Array.from({ length: evidenceItems.length }, (_, i) => i)
    );
    setExpandedItems(all);
  };

  const collapseAll = () => {
    setExpandedItems(new Set());
  };

  const copyContent = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    toast.success("已复制到剪贴板");
    setTimeout(() => setCopiedIndex(null), 1500);
  };

  // H4: Export results
  const exportResults = (format: "json" | "markdown") => {
    if (!result) return;

    let content: string;
    let mimeType: string;
    let extension: string;

    if (format === "json") {
      content = JSON.stringify(result, null, 2);
      mimeType = "application/json";
      extension = "json";
    } else {
      const items = evidenceItems
        .map((item, idx) => {
          return `## 证据 ${idx + 1}\n\n- **doc_id**: ${String(item.doc_id)}\n- **evidence_id**: ${String(item.evidence_id)}\n- **score**: ${Number(item.score).toFixed(4)}\n- **source_stage**: ${String(item.source_stage)}\n- **why_selected**: ${String(item.why_selected)}\n\n${String(item.content)}\n`;
        })
        .join("\n---\n\n");
      content = `# 检索结果\n\n**查询**: ${query}\n**集合**: ${currentCollectionId}\n**配置**: ${retrievalProfileId}\n**延迟**: ${result.latency_ms}ms\n**Token 已用**: ${result.token_budget_used}\n\n---\n\n${items}`;
      mimeType = "text/markdown";
      extension = "md";
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `retrieval-results-${new Date().toISOString().slice(0, 10)}.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success(`已导出为 ${format.toUpperCase()}`);
  };

  // H1: Click history item to refill and search
  const handleHistoryClick = (run: QueryRunItem) => {
    setQuery(run.query);
    if (run.collection_id) {
      setCurrentCollectionId(run.collection_id);
    }
    if (run.retrieval_profile_id) {
      setRetrievalProfileId(run.retrieval_profile_id);
    }
    // Execute search after state updates (use timeout to allow state to settle)
    setTimeout(() => {
      handleSearch(run.query);
    }, 50);
  };

  // H6: Handle example query click — fill and trigger search
  const handleExampleClick = (exampleQuery: string) => {
    setQuery(exampleQuery);
    setTimeout(() => {
      handleSearch(exampleQuery);
    }, 0);
  };

  // Handle recent query from localStorage click
  const handleRecentQueryClick = (recentQuery: string) => {
    setQuery(recentQuery);
    setTimeout(() => {
      handleSearch(recentQuery);
    }, 0);
  };

  const evidenceItems =
    (result?.evidence_items as Array<Record<string, unknown>>) || [];
  const compareEvidenceItems =
    (compareResult?.evidence_items as Array<Record<string, unknown>>) || [];

  const isSearchEnabled =
    !!query && !!currentCollectionId && !!retrievalProfileId;
  const isCompareEnabled = isSearchEnabled && !!compareProfileId;

  const handleSearch = (explicitQuery?: string) => {
    const q = explicitQuery || query;
    if (!q || !currentCollectionId || !retrievalProfileId) return;

    // Start frontend timing
    searchStartTimeRef.current = Date.now();
    setFrontendLatency(null);

    saveQueryToHistory(q);

    refetch().then(() => {
      if (searchStartTimeRef.current) {
        setFrontendLatency(Date.now() - searchStartTimeRef.current);
      }
    });

    if (compareMode && compareProfileId) {
      setTimeout(() => refetchCompare(), 50);
    }
  };

  const collectionNameMap = new Map(collections.map((c) => [c.collection_id, c.name]));
  const profileNameMap = new Map(
    retrievalProfiles.map((p) => [
      String(p.retrieval_profile_id),
      String(p.name || "Default"),
    ])
  );

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div variants={staggerItem}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">检索验证</h1>
            <p className="text-sm text-muted-foreground mt-1">
              验证检索结果。这是上下文工作台——展示证据片段，而非生成答案。
            </p>
          </div>
          {/* H7: Profile management link */}
          <Link href="/retrieval/profiles">
            <Button variant="outline" size="sm" className="h-8 text-xs">
              <Settings className="h-3.5 w-3.5 mr-1.5" />
              管理检索配置
            </Button>
          </Link>
        </div>
      </motion.div>

      {/* Search Form */}
      <motion.div variants={staggerItem}>
        <Card className="glass-card">
          <CardContent className="p-5 space-y-5">
            {/* Query + Token Budget */}
            <div className="flex gap-3">
              <div className="flex-1">
                <Label
                  htmlFor="query"
                  className="text-xs mb-1.5 block text-muted-foreground/80"
                >
                  查询（标准字段）
                </Label>
                <Input
                  id="query"
                  placeholder="输入检索查询..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  onFocus={() => setQueryFocused(true)}
                  onBlur={() => setTimeout(() => setQueryFocused(false), 150)}
                  className="h-10"
                />
              </div>
              <div className="w-28">
                <Label
                  htmlFor="token-budget"
                  className="text-xs mb-1.5 block text-muted-foreground/80"
                >
                  Token 预算
                </Label>
                <Input
                  id="token-budget"
                  type="number"
                  value={tokenBudget}
                  onChange={(e) => setTokenBudget(e.target.value)}
                  className="h-10"
                />
              </div>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-3">
              <div className="w-44">
                <Label className="text-xs mb-1.5 block text-muted-foreground/80">
                  集合
                </Label>
                <Select
                  value={currentCollectionId || ""}
                  onValueChange={(v) => setCurrentCollectionId(v || null)}
                  disabled={collectionsLoading}
                >
                  <SelectTrigger className="h-9 glass rounded-xl border-white/10">
                    <SelectValue placeholder="选择集合" />
                  </SelectTrigger>
                  <SelectContent className="glass-strong rounded-xl border-white/10">
                    {collections?.map((c) => (
                      <SelectItem key={c.collection_id} value={c.collection_id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="w-44">
                <Label className="text-xs mb-1.5 block text-muted-foreground/80">
                  检索配置
                </Label>
                <Select
                  value={retrievalProfileId}
                  onValueChange={(v) => v && setRetrievalProfileId(v)}
                  disabled={profilesLoading}
                >
                  <SelectTrigger className="h-9 glass rounded-xl border-white/10">
                    <SelectValue placeholder="选择配置" />
                  </SelectTrigger>
                  <SelectContent className="glass-strong rounded-xl border-white/10">
                    {retrievalProfiles.map((p) => (
                      <SelectItem
                        key={p.retrieval_profile_id}
                        value={p.retrieval_profile_id}
                      >
                        {p.name || "Default"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* H2: Comparison profile select */}
              <AnimatePresence>
                {compareMode && (
                  <motion.div
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: "auto" }}
                    exit={{ opacity: 0, width: 0 }}
                    className="w-44 overflow-hidden"
                  >
                    <Label className="text-xs mb-1.5 block text-muted-foreground/80">
                      对比配置
                    </Label>
                    <Select
                      value={compareProfileId}
                      onValueChange={(v) => v && setCompareProfileId(v)}
                      disabled={profilesLoading}
                    >
                      <SelectTrigger className="h-9 glass rounded-xl border-white/10">
                        <SelectValue placeholder="选择对比配置" />
                      </SelectTrigger>
                      <SelectContent className="glass-strong rounded-xl border-white/10">
                        {retrievalProfiles
                          .filter(
                            (p) => p.retrieval_profile_id !== retrievalProfileId
                          )
                          .map((p) => (
                            <SelectItem
                              key={p.retrieval_profile_id}
                              value={p.retrieval_profile_id}
                            >
                              {p.name || "Default"}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="w-32">
                <div className="flex items-center gap-1 mb-1.5">
                  <Label className="text-xs text-muted-foreground/80">
                    调试
                  </Label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <span className="cursor-help">
                          <Info className="h-3 w-3 text-muted-foreground/40" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent
                        side="top"
                        className="glass-strong max-w-xs"
                      >
                        <p className="text-xs">
                          <strong>无</strong>: 仅返回结果
                          <br />
                          <strong>基础</strong>: 包含评分和来源
                          <br />
                          <strong>完整</strong>: 包含完整调试信息
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <Select
                  value={debug}
                  onValueChange={(v) => setDebug(v as "none" | "basic" | "full")}
                >
                  <SelectTrigger className="h-9 glass rounded-xl border-white/10">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="glass-strong rounded-xl border-white/10">
                    <SelectItem value="none">无</SelectItem>
                    <SelectItem value="basic">基础</SelectItem>
                    <SelectItem value="full">完整</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end gap-2">
                {/* H2: Compare mode toggle */}
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Button
                        variant={compareMode ? "default" : "outline"}
                        size="sm"
                        className="h-9 px-3"
                        onClick={() => {
                          setCompareMode((prev) => !prev);
                          if (compareMode) setCompareProfileId("");
                        }}
                      >
                        <GitCompare className="h-4 w-4 mr-1.5" />
                        对比模式
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="glass-strong">
                      <p className="text-xs">开启后可选第二个配置并行对比</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>

                {/* H8: Advanced mode toggle */}
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Button
                        variant={advancedMode ? "default" : "outline"}
                        size="sm"
                        className="h-9 px-3"
                        onClick={() => setAdvancedMode((prev) => !prev)}
                      >
                        <SlidersHorizontal className="h-4 w-4 mr-1.5" />
                        高级检索
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="glass-strong">
                      <p className="text-xs">布尔表达式、字段过滤等高级选项</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>

                <Button
                  onClick={() => handleSearch()}
                  disabled={
                    !isSearchEnabled || searching || (compareMode && compareSearching)
                  }
                  className="shadow-glow"
                >
                  <Search className="h-4 w-4 mr-2" />
                  {searching || compareSearching ? "检索中..." : "检索上下文"}
                </Button>
              </div>
            </div>

            {/* H8: Advanced filters panel */}
            <AnimatePresence>
              {advancedMode && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="pt-4 mt-4 border-t border-white/[0.06] space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BarChart3 className="h-4 w-4 text-primary" />
                        <span className="text-sm font-medium">高级检索选项</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">布尔表达式</span>
                        <Switch
                          checked={booleanMode}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setBooleanMode(e.target.checked)}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="space-y-1.5">
                        <Label className="text-xs text-muted-foreground/80">Doc ID 过滤</Label>
                        <Input
                          placeholder="doc_001,doc_002 或 *"
                          value={docIdFilter}
                          onChange={(e) => setDocIdFilter(e.target.value)}
                          className="h-9"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label className="text-xs text-muted-foreground/80">开始日期</Label>
                        <Input
                          type="date"
                          value={dateFrom}
                          onChange={(e) => setDateFrom(e.target.value)}
                          className="h-9"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label className="text-xs text-muted-foreground/80">结束日期</Label>
                        <Input
                          type="date"
                          value={dateTo}
                          onChange={(e) => setDateTo(e.target.value)}
                          className="h-9"
                        />
                      </div>
                    </div>

                    {booleanMode && (
                      <Alert className="bg-blue-500/5 border-blue-500/20">
                        <Info className="h-4 w-4 text-blue-400" />
                        <AlertDescription className="text-blue-300 text-xs">
                          布尔模式已开启。支持 AND / OR / NOT 组合，例如：
                          <code>(安全 OR 合规) AND NOT 草案</code>
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </motion.div>

      {/* H6: Empty query suggestions panel — shown when input is focused and query is empty */}
      <AnimatePresence>
        {queryFocused && !query && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Card className="glass-card">
              <CardContent className="p-5 space-y-4">
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-amber-400" />
                  <h3 className="text-sm font-medium">查询建议</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Recent queries from localStorage */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground/60">
                      <History className="h-3 w-3" />
                      <span>最近查询</span>
                    </div>
                    {recentQueriesStorage.length > 0 ? (
                      <div className="space-y-1.5">
                        {recentQueriesStorage.map((recentQuery, idx) => (
                          <button
                            key={`${recentQuery}-${idx}`}
                            onClick={() => handleRecentQueryClick(recentQuery)}
                            className="w-full text-left px-3 py-2 rounded-lg text-xs bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
                          >
                            <span className="font-medium text-foreground/80 truncate">
                              {recentQuery}
                            </span>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground/30 px-3 py-2">
                        暂无历史查询
                      </p>
                    )}
                  </div>

                  {/* Example / hot queries */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground/60">
                      <Sparkles className="h-3 w-3" />
                      <span>热门查询</span>
                    </div>
                    <div className="space-y-1.5">
                      {EXAMPLE_QUERIES.map((example) => (
                        <button
                          key={example}
                          onClick={() => handleExampleClick(example)}
                          className="w-full text-left px-3 py-2 rounded-lg text-xs bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
                        >
                          <span className="font-medium text-foreground/80">
                            {example}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Alert */}
      <AnimatePresence>
        {(!currentCollectionId || !retrievalProfileId) && (
          <motion.div
            variants={staggerItem}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Alert className="glass-card border-amber-500/20 bg-amber-500/5">
              <AlertCircle className="h-4 w-4 text-amber-400" />
              <AlertDescription className="text-amber-300">
                运行检索前请选择集合和已发布的检索配置。工作台不会回退到默认集合或配置
                ID。
              </AlertDescription>
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {/* H1: Search History (below search form, always visible when query exists) */}
      <AnimatePresence>
        {query && recentQueries.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Card className="glass-card">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <History className="h-4 w-4 text-muted-foreground/50" />
                  <h3 className="text-sm font-medium">最近查询</h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  {recentQueries.slice(0, 10).map((run) => (
                    <button
                      key={run.query_run_id}
                      onClick={() => handleHistoryClick(run)}
                      className="px-3 py-1.5 rounded-lg text-xs bg-white/[0.03] hover:bg-white/[0.08] transition-colors border border-white/[0.06]"
                    >
                      <span className="text-foreground/70">{run.query}</span>
                      <span className="text-muted-foreground/30 ml-2">
                        {collectionNameMap.get(run.collection_id) || run.collection_id}
                      </span>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      {searchError ? (
        isBackendGap(searchError) ? (
          <BackendGap
            feature="通过访问 API 检索"
            endpoint={searchError.endpoint}
          />
        ) : (
          <Alert
            variant="destructive"
            className="border-red-500/20 bg-red-500/5"
          >
            <AlertCircle className="h-4 w-4 text-red-400" />
            <AlertDescription className="text-red-300">
              {isApiError(searchError)
                ? searchError.message
                : String(searchError)}
            </AlertDescription>
          </Alert>
        )
      ) : evidenceItems.length > 0 ? (
        <div className="space-y-4">
          {/* Results Header */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center justify-between glass rounded-xl px-4 py-3"
          >
            <h2 className="text-lg font-medium flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              检索到的证据片段
              {/* H5: Latency display — frontend + backend */}
              {(frontendLatency != null || result?.latency_ms != null) && (
                <span className="text-xs text-muted-foreground/50 font-normal flex items-center gap-1 ml-2">
                  <Clock className="h-3 w-3" />
                  {frontendLatency != null && `检索耗时 ${frontendLatency}ms`}
                  {result?.latency_ms != null && frontendLatency != null && " · "}
                  {result?.latency_ms != null && `后端 ${result.latency_ms}ms`}
                </span>
              )}
            </h2>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs hover:bg-white/[0.06]"
                  onClick={expandAll}
                >
                  <ChevronDown className="h-3 w-3 mr-1" />
                  展开全部
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs hover:bg-white/[0.06]"
                  onClick={collapseAll}
                >
                  <ChevronUp className="h-3 w-3 mr-1" />
                  收起全部
                </Button>
              </div>
              {/* H4: Export buttons */}
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <span className="inline-flex">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs hover:bg-white/[0.06]"
                        onClick={() => exportResults("json")}
                      >
                        <Download className="h-3 w-3 mr-1" />
                        JSON
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="glass-strong">
                    <p className="text-xs">导出为 JSON</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <span className="inline-flex">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs hover:bg-white/[0.06]"
                        onClick={() => exportResults("markdown")}
                      >
                        <Download className="h-3 w-3 mr-1" />
                        Markdown
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="glass-strong">
                    <p className="text-xs">导出为 Markdown</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Badge
                variant="outline"
                className="border-white/10 bg-white/[0.03]"
              >
                {evidenceItems.length} 项 · 已用{" "}
                {String(result?.token_budget_used || 0)} Token
              </Badge>
            </div>
          </motion.div>

          {/* H2: Comparison results header */}
          {compareMode && compareResult && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center justify-between glass rounded-xl px-4 py-3 border-primary/20"
            >
              <h2 className="text-lg font-medium flex items-center gap-2">
                <GitCompare className="h-5 w-5 text-primary" />
                对比结果
                <span className="text-xs text-muted-foreground/50 font-normal">
                  {profileNameMap.get(compareProfileId) || compareProfileId}
                </span>
                {compareResult?.latency_ms != null && (
                  <span className="text-xs text-muted-foreground/50 font-normal flex items-center gap-1 ml-2">
                    <Clock className="h-3 w-3" />
                    检索完成 · {compareResult.latency_ms}ms
                  </span>
                )}
              </h2>
              <Badge
                variant="outline"
                className="border-white/10 bg-white/[0.03]"
              >
                {compareEvidenceItems.length} 项 · 已用{" "}
                {String(compareResult?.token_budget_used || 0)} Token
              </Badge>
            </motion.div>
          )}

          {/* Evidence Cards */}
          <div className={compareMode && compareResult ? "grid grid-cols-1 lg:grid-cols-2 gap-4" : "space-y-3"}>
            {/* Main results */}
            <div className="space-y-3">
              {compareMode && compareResult && (
                <div className="text-xs text-muted-foreground/50 px-1 flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-primary" />
                  主配置: {profileNameMap.get(retrievalProfileId) || retrievalProfileId}
                </div>
              )}
              {evidenceItems.map((item, idx) => {
                const expanded = expandedItems.has(idx);
                const isCopied = copiedIndex === idx;
                const score = Number(item.score);
                const scorePercent = Math.min(Math.max(score * 100, 0), 100);

                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                  >
                    <Card interactive className="overflow-hidden">
                      <CardContent className="p-5">
                        {/* Header */}
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2 shrink-0">
                            {/* Number badge */}
                            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-gradient-to-br from-primary to-primary/60 text-white text-xs font-bold">
                              {idx + 1}
                            </div>

                            {/* Score */}
                            <div className="flex flex-col gap-1">
                              <div className="flex items-center gap-1.5">
                                <span className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">
                                  Score
                                </span>
                                <span className="text-xs font-mono font-medium text-primary">
                                  {score.toFixed(4)}
                                </span>
                              </div>
                              <div className="w-24 h-1 rounded-full bg-white/[0.06] overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-gradient-to-r from-primary/60 to-primary transition-all duration-500"
                                  style={{ width: `${scorePercent}%` }}
                                />
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-1">
                            {/* H3: Feedback buttons */}
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger>
                                  <span className="inline-flex">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-7 w-7 p-0 hover:bg-white/[0.06]"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        toast.success("已记录正面反馈");
                                      }}
                                    >
                                      <ThumbsUp className="h-3.5 w-3.5 text-emerald-400" />
                                    </Button>
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent side="top" className="glass-strong">
                                  <p className="text-xs">正面反馈</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger>
                                  <span className="inline-flex">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-7 w-7 p-0 hover:bg-white/[0.06]"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        toast.info("已记录负面反馈");
                                      }}
                                    >
                                      <ThumbsDown className="h-3.5 w-3.5 text-rose-400" />
                                    </Button>
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent side="top" className="glass-strong">
                                  <p className="text-xs">负面反馈</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 gap-1 text-xs hover:bg-white/[0.06]"
                              onClick={(e) => {
                                e.stopPropagation();
                                copyContent(String(item.content), idx);
                              }}
                            >
                              {isCopied ? (
                                <>
                                  <Check className="h-3 w-3 text-emerald-400" />
                                  <span className="text-emerald-400">已复制</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="h-3 w-3" />
                                  复制
                                </>
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 hover:bg-white/[0.06]"
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleExpand(idx);
                              }}
                            >
                              {expanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </div>

                        {/* Metadata */}
                        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-[11px] text-muted-foreground/60">
                          <span className="flex items-center gap-1">
                            <FileText className="h-3 w-3" />
                            doc_id: {String(item.doc_id)}
                          </span>
                          <span className="flex items-center gap-1">
                            <Hash className="h-3 w-3" />
                            evidence_id: {String(item.evidence_id)}
                          </span>
                          <span className="flex items-center gap-1">
                            <BookOpen className="h-3 w-3" />
                            {String(item.collection_id)}
                          </span>
                        </div>

                        <Separator className="my-3 bg-white/[0.06]" />

                        {/* Content */}
                        <p
                          className={`text-sm leading-relaxed text-foreground/90 ${
                            expanded ? "" : "line-clamp-4"
                          }`}
                        >
                          {String(item.content)}
                        </p>

                        {/* Expanded details */}
                        <AnimatePresence>
                          {expanded && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: "auto" }}
                              exit={{ opacity: 0, height: 0 }}
                              className="overflow-hidden"
                            >
                              <Separator className="my-3 bg-white/[0.06]" />
                              <div className="text-xs text-muted-foreground/70 space-y-1.5">
                                <p>
                                  <span className="text-muted-foreground/40">
                                    source_stage:
                                  </span>{" "}
                                  {String(item.source_stage)}
                                </p>
                                <p>
                                  <span className="text-muted-foreground/40">
                                    why_selected:
                                  </span>{" "}
                                  {String(item.why_selected)}
                                </p>
                                <p>
                                  <span className="text-muted-foreground/40">
                                    section_path:
                                  </span>{" "}
                                  {JSON.stringify(item.section_path)}
                                </p>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </CardContent>
                    </Card>
                  </motion.div>
                );
              })}
            </div>

            {/* H2: Comparison results column */}
            {compareMode && compareResult && (
              <div className="space-y-3">
                <div className="text-xs text-muted-foreground/50 px-1 flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-amber-400" />
                  对比配置: {profileNameMap.get(compareProfileId) || compareProfileId}
                </div>
                {compareEvidenceItems.length > 0 ? (
                  compareEvidenceItems.map((item, idx) => {
                    const expanded = expandedItems.has(idx + 1000);
                    const score = Number(item.score);
                    const scorePercent = Math.min(Math.max(score * 100, 0), 100);

                    return (
                      <motion.div
                        key={`compare-${idx}`}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.05 }}
                      >
                        <Card interactive className="overflow-hidden border-amber-500/10">
                          <CardContent className="p-5">
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-center gap-2 shrink-0">
                                <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 text-white text-xs font-bold">
                                  {idx + 1}
                                </div>
                                <div className="flex flex-col gap-1">
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">
                                      Score
                                    </span>
                                    <span className="text-xs font-mono font-medium text-amber-400">
                                      {score.toFixed(4)}
                                    </span>
                                  </div>
                                  <div className="w-24 h-1 rounded-full bg-white/[0.06] overflow-hidden">
                                    <div
                                      className="h-full rounded-full bg-gradient-to-r from-amber-400/60 to-amber-400 transition-all duration-500"
                                      style={{ width: `${scorePercent}%` }}
                                    />
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 w-7 p-0 hover:bg-white/[0.06]"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleExpand(idx + 1000);
                                  }}
                                >
                                  {expanded ? (
                                    <ChevronUp className="h-4 w-4" />
                                  ) : (
                                    <ChevronDown className="h-4 w-4" />
                                  )}
                                </Button>
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-[11px] text-muted-foreground/60">
                              <span className="flex items-center gap-1">
                                <FileText className="h-3 w-3" />
                                doc_id: {String(item.doc_id)}
                              </span>
                              <span className="flex items-center gap-1">
                                <Hash className="h-3 w-3" />
                                evidence_id: {String(item.evidence_id)}
                              </span>
                            </div>
                            <Separator className="my-3 bg-white/[0.06]" />
                            <p
                              className={`text-sm leading-relaxed text-foreground/90 ${
                                expanded ? "" : "line-clamp-4"
                              }`}
                            >
                              {String(item.content)}
                            </p>
                            <AnimatePresence>
                              {expanded && (
                                <motion.div
                                  initial={{ opacity: 0, height: 0 }}
                                  animate={{ opacity: 1, height: "auto" }}
                                  exit={{ opacity: 0, height: 0 }}
                                  className="overflow-hidden"
                                >
                                  <Separator className="my-3 bg-white/[0.06]" />
                                  <div className="text-xs text-muted-foreground/70 space-y-1.5">
                                    <p>
                                      <span className="text-muted-foreground/40">source_stage:</span>{" "}
                                      {String(item.source_stage)}
                                    </p>
                                    <p>
                                      <span className="text-muted-foreground/40">why_selected:</span>{" "}
                                      {String(item.why_selected)}
                                    </p>
                                  </div>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </CardContent>
                        </Card>
                      </motion.div>
                    );
                  })
                ) : (
                  <EmptyState
                    icon={Search}
                    title="无对比结果"
                    description="对比配置返回空结果。"
                  />
                )}
              </div>
            )}
          </div>
        </div>
      ) : result ? (
        <EmptyState
          icon={Search}
          title="无证据片段"
          description="检索返回空结果。请检查查询、集合范围和检索配置。"
        />
      ) : null}

      {/* H8: Advanced features placeholders */}
      <motion.div variants={staggerItem}>
        <Card className="glass-card">
          <CardContent className="p-5 space-y-4">
            <h3 className="text-sm font-medium flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-muted-foreground/50" />
              高级功能
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <span className="inline-flex w-full">
                      <Button variant="outline" size="sm" className="h-9 text-xs w-full" disabled>
                        <BarChart3 className="h-3.5 w-3.5 mr-1.5" />
                        可视化分析
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="glass-strong">
                    <p className="text-xs">即将推出</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <span className="inline-flex w-full">
                      <Button variant="outline" size="sm" className="h-9 text-xs w-full" disabled>
                        <Code className="h-3.5 w-3.5 mr-1.5" />
                        API 代码片段
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="glass-strong">
                    <p className="text-xs">即将推出</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <span className="inline-flex w-full">
                      <Button variant="outline" size="sm" className="h-9 text-xs w-full" disabled>
                        <Eye className="h-3.5 w-3.5 mr-1.5" />
                        检索预设
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="glass-strong">
                    <p className="text-xs">即将推出</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <span className="inline-flex w-full">
                      <Button variant="outline" size="sm" className="h-9 text-xs w-full" disabled>
                        <SlidersHorizontal className="h-3.5 w-3.5 mr-1.5" />
                        高级搜索
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="glass-strong">
                    <p className="text-xs">即将推出</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
