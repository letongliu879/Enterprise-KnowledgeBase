"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Copy,
  ChevronDown,
  ChevronUp,
  Hash,
  FileText,
  BookOpen,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { accessApi, adminApi } from "@/lib/api/client";
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
import { BackendGap } from "@/components/backend-gap";
import { EmptyState } from "@/components/empty-state";
import { isBackendGap, isApiError } from "@/lib/api/errors";
import { toast } from "sonner";

export default function RetrievalPage() {
  const { currentCollectionId, setCurrentCollectionId } = useAppStore();
  const [query, setQuery] = useState("");
  const [tokenBudget, setTokenBudget] = useState("2000");
  const [retrievalProfileId, setRetrievalProfileId] = useState("");
  const [debug, setDebug] = useState<"none" | "basic" | "full">("none");
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
  const { data: me } = useQuery({
    queryKey: ["admin-me"],
    queryFn: () => adminApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";

  const {
    data: collectionResponse,
    isLoading: collectionsLoading,
  } = useQuery({
    queryKey: ["collections", userTenantId],
    queryFn: () => adminApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });
  const collections = collectionResponse?.items ?? [];

  const {
    data: profiles,
    isLoading: profilesLoading,
  } = useQuery({
    queryKey: ["retrieval-profiles"],
    queryFn: () => adminApi.listRetrievalProfiles("published"),
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
      accessApi.retrieve({
        query,
        collection_scope: currentCollectionId ? [currentCollectionId] : [],
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

  const copyContent = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("已复制到剪贴板");
  };

  const evidenceItems = (result?.evidence_items as Array<Record<string, unknown>>) || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          检索验证
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          验证检索结果。这是上下文工作台——展示证据片段，而非生成答案。
        </p>
      </div>

      {/* Search form */}
      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="query" className="text-xs mb-1.5 block">
                查询（标准字段）
              </Label>
              <Input
                id="query"
                placeholder="输入检索查询..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && refetch()}
              />
            </div>
            <div className="w-32">
              <Label htmlFor="token-budget" className="text-xs mb-1.5 block">
                Token 预算
              </Label>
              <Input
                id="token-budget"
                type="number"
                value={tokenBudget}
                onChange={(e) => setTokenBudget(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="w-48">
              <Label className="text-xs mb-1.5 block">集合</Label>
              <Select
                value={currentCollectionId || ""}
                onValueChange={(v) => setCurrentCollectionId(v || null)}
                disabled={collectionsLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择集合" />
                </SelectTrigger>
                <SelectContent>
                  {collections?.map((c) => (
                    <SelectItem key={c.collection_id} value={c.collection_id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-48">
              <Label className="text-xs mb-1.5 block">检索配置</Label>
              <Select
                value={retrievalProfileId}
                onValueChange={(v) => v && setRetrievalProfileId(v)}
                disabled={profilesLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择配置" />
                </SelectTrigger>
                <SelectContent>
                  {retrievalProfiles.map((p: Record<string, unknown>) => (
                    <SelectItem
                      key={String(p.retrieval_profile_id || p.profile_id || "default")}
                      value={String(p.retrieval_profile_id || p.profile_id)}
                    >
                      {String(p.name || "Default")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-36">
              <Label className="text-xs mb-1.5 block">调试</Label>
              <Select
                value={debug}
                onValueChange={(v) => setDebug(v as "none" | "basic" | "full")}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
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
              >
                <Search className="h-4 w-4 mr-2" />
                {searching ? "检索中..." : "检索上下文"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {(!currentCollectionId || !retrievalProfileId) && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            运行检索前请选择集合和已发布的检索配置。工作台不会回退到默认集合或配置 ID。
          </AlertDescription>
        </Alert>
      )}

      {/* Results */}
      {searchError ? (
        isBackendGap(searchError) ? (
          <BackendGap feature="通过访问 API 检索" endpoint={searchError.endpoint} />
        ) : (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {isApiError(searchError)
                ? searchError.message
                : String(searchError)}
            </AlertDescription>
          </Alert>
        )
      ) : evidenceItems.length > 0 ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              检索到的证据片段
            </h2>
            <Badge variant="secondary">
              {evidenceItems.length} 项 · 已用 Token 预算: {String(result?.token_budget_used || 0)}
            </Badge>
          </div>

          <div className="space-y-3">
            {evidenceItems.map((item, idx) => {
              const expanded = expandedItems.has(idx);
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                >
                  <Card>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2 shrink-0">
                          <Badge variant="outline" className="font-mono text-xs">
                            #{idx + 1}
                          </Badge>
                          <Badge variant="secondary" className="text-xs">
                            score: {Number(item.score).toFixed(4)}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 gap-1 text-xs"
                            onClick={() =>
                              copyContent(String(item.content))
                            }
                          >
                            <Copy className="h-3 w-3" />
                            复制
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0"
                            onClick={() => toggleExpand(idx)}
                          >
                            {expanded ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
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

                      <Separator className="my-3" />

                      <p
                        className={`text-sm leading-relaxed ${
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
                            <Separator className="my-3" />
                            <div className="text-xs text-muted-foreground space-y-1">
                              <p>source_stage: {String(item.source_stage)}</p>
                              <p>why_selected: {String(item.why_selected)}</p>
                              <p>
                                section_path: {JSON.stringify(item.section_path)}
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
    </div>
  );
}
