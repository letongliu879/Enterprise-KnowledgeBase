"use client";

import { useState } from "react";
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

export default function RetrievalPage() {
  const { currentCollectionId, setCurrentCollectionId } = useAppStore();
  const [query, setQuery] = useState("");
  const [tokenBudget, setTokenBudget] = useState("2000");
  const [retrievalProfileId, setRetrievalProfileId] = useState("");
  const [debug, setDebug] = useState<"none" | "basic" | "full">("none");
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

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
    queryFn: () =>
      workbenchApi.retrieve({
        query,
        collection_id: currentCollectionId || "",
        retrieval_profile_id: retrievalProfileId,
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
      Array.from(
        { length: evidenceItems.length },
        (_, i) => i
      )
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

  const evidenceItems =
    (result?.evidence_items as Array<Record<string, unknown>>) || [];

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div variants={staggerItem}>
        <h1 className="text-2xl font-semibold tracking-tight">检索验证</h1>
        <p className="text-sm text-muted-foreground mt-1">
          验证检索结果。这是上下文工作台——展示证据片段，而非生成答案。
        </p>
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
                  onKeyDown={(e) => e.key === "Enter" && refetch()}
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
                    {retrievalProfiles.map((p: Record<string, unknown>) => (
                      <SelectItem
                        key={String(
                          p.retrieval_profile_id || p.profile_id || "default"
                        )}
                        value={String(p.retrieval_profile_id || p.profile_id)}
                      >
                        {String(p.name || "Default")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

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

              <div className="flex items-end">
                <Button
                  onClick={() => refetch()}
                  disabled={
                    !query || searching || !currentCollectionId || !retrievalProfileId
                  }
                  className="shadow-glow"
                >
                  <Search className="h-4 w-4 mr-2" />
                  {searching ? "检索中..." : "检索上下文"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

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
              <Badge
                variant="outline"
                className="border-white/10 bg-white/[0.03]"
              >
                {evidenceItems.length} 项 · 已用{" "}
                {String(result?.token_budget_used || 0)} Token
              </Badge>
            </div>
          </motion.div>

          {/* Evidence Cards */}
          <div className="space-y-3">
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
        </div>
      ) : result ? (
        <EmptyState
          icon={Search}
          title="无证据片段"
          description="检索返回空结果。请检查查询、集合范围和检索配置。"
        />
      ) : null}
    </motion.div>
  );
}
