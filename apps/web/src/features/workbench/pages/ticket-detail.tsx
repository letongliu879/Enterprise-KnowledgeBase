"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRightLeft,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  GitCompare,
  Layers,
  MessageSquare,
  RotateCcw,
  Send,
  ShieldAlert,
  Timer,
  UserX,
  Wand2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { ChunkEditorWorkbench } from "@/features/workbench/components/chunk-editor";
import { DocumentViewer } from "@/components/document-workbench/document-viewer";
import { AgentReviewPanel } from "@/features/workbench/components/agent-review";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { BackendGap } from "@/components/backend-gap";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { workbenchApi } from "@/lib/api/client";
import { isBackendGap, isApiError } from "@/lib/api/errors";
import type { Finding } from "@/features/workbench/types/finding";
import { TicketComments } from "@/features/workbench/components/ticket-comments";
import { TicketTransferDialog } from "@/features/workbench/components/ticket-transfer";
import { ReviewTimer } from "@/components/review-timer";
import { handleExportReport } from "@/features/workbench/utils/export-report";
import {
  formatFailureStageLabel,
  formatNextActionLabel,
  formatReviewDecisionLabel,
  formatTicketStatusLabel,
  normalizeStatus,
} from "@/lib/status";

const decisionTemplates = [
  { value: "", label: "选择常见原因..." },
  { value: "格式不规范，请重新整理后提交", label: "格式不规范" },
  { value: "包含敏感信息，需脱敏处理", label: "敏感信息" },
  { value: "内容重复，与现有文档高度相似", label: "内容重复" },
  { value: "缺少必要的上下文或元数据", label: "缺少上下文" },
  { value: "解析质量不佳，chunk 边界错误", label: "解析质量差" },
  { value: "不符合当前集合的收录标准", label: "不符合收录标准" },
];

function ticketTone(status?: string) {
  const normalized = normalizeStatus(status);
  if (normalized === "pending") return "secondary";
  if (normalized === "approved") return "default";
  return "destructive";
}

function SummaryMetric({
  label,
  value,
  tone = "text-foreground",
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="rounded-2xl border bg-background/85 p-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function MetaItem({
  label,
  value,
  mono = false,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  return (
    <div className="space-y-1.5 rounded-xl border bg-muted/10 p-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className={`break-all text-sm text-foreground ${mono ? "font-mono" : "font-medium"}`}>
        {value?.trim() || "-"}
      </p>
    </div>
  );
}

function useReviewTimer(createdAt?: string | null) {
  const [elapsed, setElapsed] = useState("");

  useEffect(() => {
    if (!createdAt) return;
    const start = new Date(createdAt).getTime();
    if (Number.isNaN(start)) return;

    const tick = () => {
      const diff = Date.now() - start;
      if (diff < 0) {
        setElapsed("");
        return;
      }
      const hours = Math.floor(diff / 3600000);
      const minutes = Math.floor((diff % 3600000) / 60000);
      if (hours > 0) {
        setElapsed(`已等待 ${hours}小时${minutes}分钟`);
      } else {
        setElapsed(`已等待 ${minutes}分钟`);
      }
    };

    tick();
    const id = setInterval(tick, 60000);
    return () => clearInterval(id);
  }, [createdAt]);

  return elapsed;
}

function ComingSoonButton({
  children,
  icon: Icon,
  variant = "outline",
  className,
}: {
  children: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  variant?: "outline" | "secondary" | "ghost";
  className?: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant={variant} className={className} disabled>
          {Icon ? <Icon className="mr-2 h-4 w-4" /> : null}
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="top">即将推出</TooltipContent>
    </Tooltip>
  );
}

function ConcurrentEditBanner() {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Alert variant="destructive" className="rounded-2xl">
        <UserX className="h-4 w-4" />
        <AlertDescription>
          <span className="font-medium">冲突警告：</span> 某某正在处理此工单。请协调以避免覆盖彼此的更改。
        </AlertDescription>
      </Alert>
    </motion.div>
  );
}

function TicketTimeline({
  createdAt,
  updatedAt,
  parseSnapshotCreatedAt,
  ticketStatus,
  ticketDecision,
}: {
  createdAt?: string | null;
  updatedAt?: string | null;
  parseSnapshotCreatedAt?: string | null;
  ticketStatus?: string | null;
  ticketDecision?: string | null;
}) {
  const normalizedStatus = normalizeStatus(ticketStatus);
  const normalizedDecision = normalizeStatus(ticketDecision);

  const nodes = useMemo(() => {
    const items: Array<{
      label: string;
      icon: React.ComponentType<{ className?: string }>;
      timestamp?: string | null;
      duration?: string;
      active: boolean;
      completed: boolean;
    }> = [];

    const created = createdAt ? new Date(createdAt).getTime() : null;
    const parseTime = parseSnapshotCreatedAt ? new Date(parseSnapshotCreatedAt).getTime() : null;
    const updated = updatedAt ? new Date(updatedAt).getTime() : null;

    items.push({
      label: "Upload",
      icon: FileText,
      timestamp: createdAt,
      active: true,
      completed: true,
    });

    items.push({
      label: "Parse",
      icon: Layers,
      timestamp: parseSnapshotCreatedAt,
      duration:
        created && parseTime && parseTime > created
          ? `${Math.round((parseTime - created) / 60000)}分钟`
          : undefined,
      active: Boolean(parseSnapshotCreatedAt),
      completed: Boolean(parseSnapshotCreatedAt),
    });

    const hasAgentReview = Boolean(normalizedStatus === "pending" || normalizedDecision || updated);
    items.push({
      label: "Agent Review",
      icon: ShieldAlert,
      timestamp: parseSnapshotCreatedAt,
      active: hasAgentReview,
      completed: hasAgentReview,
    });

    const hasHumanReview = Boolean(
      normalizedStatus === "pending" || normalizedDecision === "approve" || normalizedDecision === "reject" || normalizedDecision === "return"
    );
    items.push({
      label: "Human Review",
      icon: Clock,
      timestamp: updatedAt,
      duration:
        parseTime && updated && updated > parseTime
          ? `${Math.round((updated - parseTime) / 60000)}分钟`
          : undefined,
      active: hasHumanReview,
      completed: Boolean(normalizedDecision),
    });

    const hasDecision = Boolean(normalizedDecision);
    items.push({
      label: "Decision",
      icon: CheckCircle2,
      timestamp: normalizedDecision ? updatedAt : null,
      active: hasDecision,
      completed: hasDecision,
    });

    const isPublished = Boolean(normalizedStatus === "approved" || normalizedStatus === "published");
    items.push({
      label: "Publish",
      icon: Send,
      timestamp: isPublished ? updatedAt : null,
      active: isPublished,
      completed: isPublished,
    });

    return items;
  }, [createdAt, updatedAt, parseSnapshotCreatedAt, normalizedStatus, normalizedDecision]);

  return (
    <div className="space-y-4">
      {nodes.map((node, index) => {
        const Icon = node.icon;
        const isLast = index === nodes.length - 1;
        return (
          <motion.div
            key={node.label}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.08, duration: 0.3 }}
            className="flex items-start gap-3"
          >
            <div className="flex flex-col items-center">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full border ${
                  node.completed
                    ? "border-primary bg-primary text-primary-foreground"
                    : node.active
                      ? "border-amber-500 bg-amber-50 text-amber-600"
                      : "border-muted bg-muted text-muted-foreground"
                }`}
              >
                <Icon className="h-4 w-4" />
              </div>
              {!isLast && (
                <div
                  className={`mt-1 h-6 w-px ${
                    node.completed ? "bg-primary" : "bg-muted"
                  }`}
                />
              )}
            </div>
            <div className="flex-1 pb-2">
              <p
                className={`text-sm font-medium ${
                  node.completed
                    ? "text-foreground"
                    : node.active
                      ? "text-amber-700"
                      : "text-muted-foreground"
                }`}
              >
                {node.label}
              </p>
              {node.timestamp ? (
                <p className="text-xs text-muted-foreground">
                  {new Date(node.timestamp).toLocaleString("zh-CN")}
                </p>
              ) : null}
              {node.duration ? (
                <p className="text-xs text-muted-foreground">耗时: {node.duration}</p>
              ) : null}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

export function TicketDetailPage({ ticketId, backHref = "/review" }: { ticketId: string; backHref?: string }) {
  const queryClient = useQueryClient();
  const [decisionReason, setDecisionReason] = useState("");
  const [transferOpen, setTransferOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("source");
  const [searchText, setSearchText] = useState("");
  const [focusedEvidenceId, setFocusedEvidenceId] = useState<string | null>(null);

  const {
    data: workspace,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workspace", ticketId],
    queryFn: () => workbenchApi.getWorkspaceDetail(ticketId),
    enabled: Boolean(ticketId),
    retry: 0,
  });

  const ticket = workspace?.ticket ?? null;
  const document = workspace?.document;
  const parseSnapshot = workspace?.parse_snapshot ?? null;
  const chunks = workspace?.chunks;
  const chunkEdits = workspace?.chunk_edits;
  const agentReview = workspace?.agent_review;
  const capabilities = workspace?.capabilities;
  const degradedParts = workspace?.degraded_parts ?? [];

  const effectiveParseSnapshotId =
    document?.parse_snapshot_id || parseSnapshot?.parse_snapshot_id || "";
  const effectiveSourceFileId =
    document?.source_file_id || parseSnapshot?.source_file_id || null;
  const effectiveFilename =
    document?.filename?.trim() ||
    parseSnapshot?.source_filename?.trim() ||
    ticket?.filename?.trim() ||
    "";

  const decide = useMutation({
    mutationFn: (action: "APPROVE" | "REJECT" | "RETURN") =>
      workbenchApi.decideTicket(ticketId, {
        decision_request_id: `dec_${Date.now()}`,
        action,
        reason: decisionReason,
        tenant_id: ticket?.tenant_id ?? "",
        collection_id: ticket?.collection_id ?? "",
      }),
    onSuccess: async () => {
      toast.success("Review decision submitted");
      await queryClient.invalidateQueries({ queryKey: ["workspace", ticketId] });
      await queryClient.invalidateQueries({ queryKey: ["tickets"] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "Failed to submit review decision");
    },
  });

  const hasParseSnapshot = Boolean(effectiveParseSnapshotId);
  const hasSourceFile = Boolean(effectiveSourceFileId);
  const isPending = normalizeStatus(ticket?.status) === "pending";
  const displayTitle =
    effectiveFilename || ticket?.doc_id?.trim() || ticket?.ticket_id || ticketId;

  const reviewTimerText = useReviewTimer(ticket?.created_at);

  const reviewFindings = useMemo<Finding[]>(
    () =>
      (agentReview?.findings ?? []).map((item) => ({
        finding_id: item.finding_id,
        severity: item.severity,
        category: item.category,
        problem_summary: item.problem_summary,
        source_quote: item.source_quote || undefined,
        evidence_id: item.evidence_id || undefined,
        doc_id: item.doc_id || undefined,
        page_from: item.page_from ?? undefined,
        page_to: item.page_to ?? undefined,
        state: item.state,
        confidence: item.confidence ?? undefined,
      })),
    [agentReview?.findings]
  );

  const reviewSummary = useMemo(
    () => ({
      findings: reviewFindings.length,
      risks: reviewFindings.filter((item) => ["critical", "high"].includes(item.severity)).length,
      fixes: reviewFindings.filter((item) => Boolean(item.evidence_id)).length,
    }),
    [reviewFindings]
  );

  const systemActionLabel = useMemo(() => {
    const action = normalizeStatus(ticket?.decision);
    if (action === "approve") return "System auto-approved";
    if (action === "reject") return "System auto-rejected";
    if (action === "return") return "System returned for review";
    if (normalizeStatus(ticket?.status) === "system_decided") return "System decision recorded";
    return "";
  }, [ticket?.decision, ticket?.status]);

  const parseSnapshotSummary = useMemo(() => {
    if (!parseSnapshot) return null;
    return {
      sourceFilename: String(parseSnapshot.source_filename || effectiveFilename || "-"),
      sourceSuffix: String(parseSnapshot.source_suffix || "-"),
      parserId: String(parseSnapshot.parser_id || "-"),
      parserBackend: String(parseSnapshot.parser_backend || "-"),
      effectivePolicy: String(
        parseSnapshot.effective_policy || parseSnapshot.decision_reason || "-"
      ),
      previewText: String(parseSnapshot.preview_text || "").trim(),
      warnings: Array.isArray(parseSnapshot.warnings)
        ? parseSnapshot.warnings.map((item) => String(item))
        : [],
    };
  }, [effectiveFilename, parseSnapshot]);

  const warningCount = parseSnapshotSummary?.warnings.length ?? 0;
  const editedCount = chunkEdits?.total ?? 0;
  const chunkCount = chunks?.total ?? 0;

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-56 rounded-lg" />
        <Skeleton className="h-36 rounded-lg" />
      </div>
    );
  }

  if (error) {
    if (isBackendGap(error)) {
      return <BackendGap feature="Review detail workspace" endpoint={error.endpoint} />;
    }
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{isApiError(error) ? error.message : String(error)}</AlertDescription>
      </Alert>
    );
  }

  if (!workspace || !ticket || !document) {
    return (
      <EmptyState
        icon={FileText}
        title="Review workspace not found"
        description="The aggregated workspace view is unavailable or you no longer have access to this ticket."
      />
    );
  }

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* E7: Concurrent edit conflict banner (simulated) */}
        <ConcurrentEditBanner />

        <section className="rounded-[28px] border bg-card/92 p-5 shadow-sm">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="flex items-start gap-3">
                <Link href={backHref} prefetch={false}>
                  <Button variant="outline" size="icon" className="mt-1 rounded-full">
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                </Link>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={ticketTone(ticket.status)}>{formatTicketStatusLabel(ticket.status)}</Badge>
                    {ticket.failure_code ? <Badge variant="destructive">{ticket.failure_code}</Badge> : null}
                    {ticket.next_action ? (
                      <Badge variant="outline">{formatNextActionLabel(ticket.next_action)}</Badge>
                    ) : null}
                    {document.linkage_source !== "document_projection" ? (
                      <Badge variant="outline">Linkage: {document.linkage_source}</Badge>
                    ) : null}
                    {/* E6: Review timer */}
                    {reviewTimerText ? (
                      <Badge variant="outline" className="flex items-center gap-1">
                        <Timer className="h-3 w-3" />
                        {reviewTimerText}
                      </Badge>
                    ) : null}
                  </div>
                  <h1 className="mt-3 text-3xl font-semibold tracking-tight xl:text-4xl">
                    {displayTitle}
                  </h1>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Workspace detail is now aggregated server-side. Ticket approval state and document
                    linkage are resolved before this page renders.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:min-w-[420px]">
                <SummaryMetric label="Findings" value={reviewSummary.findings} tone="text-amber-600" />
                <SummaryMetric label="Risks" value={reviewSummary.risks} tone="text-rose-600" />
                <SummaryMetric label="Draft edits" value={editedCount} tone="text-sky-600" />
                <SummaryMetric label="Warnings" value={warningCount} tone="text-violet-600" />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <MetaItem label="Ticket id" value={ticket.ticket_id} mono />
              <MetaItem label="Collection" value={ticket.collection_id} />
              <MetaItem label="Document id" value={document.doc_id || ticket.doc_id} mono />
              <MetaItem label="Parse snapshot" value={effectiveParseSnapshotId} mono />
            </div>
          </div>
        </section>

        {degradedParts.length > 0 ? (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Workspace is partially degraded: {degradedParts.join(", ")}.
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0 space-y-4">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
              <TabsList
                variant="line"
                className="w-full justify-start gap-2 overflow-x-auto rounded-none border-0 bg-transparent p-0"
              >
                <TabsTrigger value="source">
                  <FileText className="mr-1 h-3.5 w-3.5" />
                  Source
                </TabsTrigger>
                <TabsTrigger value="drafts">
                  <Layers className="mr-1 h-3.5 w-3.5" />
                  Draft edits
                </TabsTrigger>
                <TabsTrigger value="agent">
                  <ShieldAlert className="mr-1 h-3.5 w-3.5" />
                  Agent review
                </TabsTrigger>
                {/* E4: Side-by-side comparison tab */}
                <TabsTrigger value="compare">
                  <GitCompare className="mr-1 h-3.5 w-3.5" />
                  对比
                </TabsTrigger>
              </TabsList>

              <TabsContent value="source" className="space-y-4">
                {!hasSourceFile ? (
                  <Alert>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>This workspace does not currently link to a source file.</AlertDescription>
                  </Alert>
                ) : (
                  <>
                    <DocumentViewer
                      sourceFileId={effectiveSourceFileId}
                      filename={effectiveFilename || parseSnapshotSummary?.sourceFilename}
                      previewText={parseSnapshotSummary?.previewText}
                      parserId={parseSnapshotSummary?.parserId}
                      parserBackend={parseSnapshotSummary?.parserBackend}
                      warnings={parseSnapshotSummary?.warnings}
                      chunks={chunks?.items ?? []}
                      searchText={searchText}
                      onSearchComplete={(found) => {
                        if (searchText.trim() && !found) {
                          toast.info("Text not found in current view");
                        }
                      }}
                    />
                    {!hasParseSnapshot ? (
                      <Alert>
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription>
                          This workspace does not currently link to a parse snapshot. Original source preview is still available.
                        </AlertDescription>
                      </Alert>
                    ) : null}
                  </>
                )}

                {!hasParseSnapshot ? null : parseSnapshotSummary ? (
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
                    <Card className="rounded-2xl">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Parse context</CardTitle>
                        <CardDescription>
                          This is the parser configuration and normalized preview context used by the
                          review workspace.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                          <MetaItem label="Source file" value={parseSnapshotSummary.sourceFilename} />
                          <MetaItem label="Suffix" value={parseSnapshotSummary.sourceSuffix} />
                          <MetaItem label="Parser" value={parseSnapshotSummary.parserId} />
                          <MetaItem label="Backend" value={parseSnapshotSummary.parserBackend} />
                        </div>
                        <div className="rounded-2xl border bg-muted/10 p-4">
                          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                            Effective parse policy
                          </p>
                          <p className="mt-2 text-sm leading-6 text-foreground">
                            {parseSnapshotSummary.effectivePolicy}
                          </p>
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="rounded-2xl">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Preview signal</CardTitle>
                        <CardDescription>
                          Sanity check the extracted payload before you trust the agent recommendation.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="grid grid-cols-3 gap-3">
                          <SummaryMetric label="Chunks" value={chunkCount} tone="text-slate-900" />
                          <SummaryMetric label="Warnings" value={warningCount} tone="text-violet-600" />
                          <SummaryMetric label="Edits" value={editedCount} tone="text-sky-600" />
                        </div>
                        <div className="max-h-52 overflow-auto rounded-2xl border bg-muted/10 p-4 text-sm leading-7">
                          {parseSnapshotSummary.previewText || "No preview text is available for this parse snapshot."}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                ) : null}
              </TabsContent>

              <TabsContent value="drafts" className="space-y-4">
                <Card className="rounded-2xl border-dashed bg-card/85">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Pre-publish draft layer</CardTitle>
                    <CardDescription>
                      Draft edits stay inside workbench governance. They do not mutate the live retrieval
                      index directly.
                    </CardDescription>
                  </CardHeader>
                </Card>
                {!capabilities?.can_edit_drafts || !effectiveParseSnapshotId ? (
                  <Alert>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      Draft editing is unavailable because this workspace does not expose a parse snapshot.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <ChunkEditorWorkbench
                    parseSnapshotId={effectiveParseSnapshotId}
                    mode="pre-publish"
                    title="Draft corrections"
                    description="Tighten chunk wording, restore broken structure, and submit governed draft edits before the human decision."
                    focusEvidenceId={focusedEvidenceId}
                  />
                )}
              </TabsContent>

              <TabsContent value="agent" className="space-y-4">
                <AgentReviewPanel
                  findings={reviewFindings}
                  onSearchInDocument={
                    capabilities?.can_search_in_document
                      ? (quote) => {
                          setFocusedEvidenceId(null);
                          setSearchText(quote);
                          setActiveTab("source");
                        }
                      : undefined
                  }
                  onJumpToChunk={
                    capabilities?.can_jump_to_chunk
                      ? (evidenceId) => {
                          setFocusedEvidenceId(evidenceId);
                          setActiveTab("drafts");
                        }
                      : undefined
                  }
                />
              </TabsContent>

              {/* E4: Side-by-side comparison tab content */}
              <TabsContent value="compare" className="space-y-4">
                <div className="grid gap-4 lg:grid-cols-2">
                  <Card className="rounded-2xl">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <FileText className="h-4 w-4" />
                        Source
                      </CardTitle>
                      <CardDescription>Original document source preview</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {!hasSourceFile ? (
                        <EmptyState
                          icon={FileText}
                          title="Source unavailable"
                          description="This workspace does not link to a source file."
                        />
                      ) : (
                        <DocumentViewer
                          sourceFileId={effectiveSourceFileId}
                          filename={effectiveFilename || parseSnapshotSummary?.sourceFilename}
                          previewText={parseSnapshotSummary?.previewText}
                          parserId={parseSnapshotSummary?.parserId}
                          parserBackend={parseSnapshotSummary?.parserBackend}
                          warnings={parseSnapshotSummary?.warnings}
                          chunks={chunks?.items ?? []}
                          searchText={searchText}
                          onSearchComplete={(found) => {
                            if (searchText.trim() && !found) {
                              toast.info("Text not found in current view");
                            }
                          }}
                        />
                      )}
                    </CardContent>
                  </Card>

                  <Card className="rounded-2xl">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Layers className="h-4 w-4" />
                        Parsed text
                      </CardTitle>
                      <CardDescription>Extracted text from parse snapshot</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {!hasParseSnapshot || !parseSnapshotSummary?.previewText ? (
                        <EmptyState
                          icon={Layers}
                          title="Parsed text unavailable"
                          description="No parse snapshot preview text is available."
                        />
                      ) : (
                        <div className="max-h-[780px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/10 p-4 text-sm leading-7">
                          {parseSnapshotSummary.previewText}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
            </Tabs>
          </div>

          <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
            <Card className="rounded-[24px] shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Decision cockpit</CardTitle>
                <CardDescription>
                  Keep the final human action obvious. Everything else on this page is supporting evidence.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-2xl border bg-muted/10 p-4">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={ticketTone(ticket.status)}>{formatTicketStatusLabel(ticket.status)}</Badge>
                    {ticket.decision ? (
                      <Badge variant="outline">{formatReviewDecisionLabel(ticket.decision)}</Badge>
                    ) : null}
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">
                    {isPending
                      ? "This ticket is still waiting on a human decision."
                      : "This ticket already has a terminal human or system decision recorded."}
                  </p>
                </div>

                {capabilities?.can_decide_ticket ? (
                  <>
                    <Select
                      value=""
                      onValueChange={(value) =>
                        setDecisionReason((prev) =>
                          value ? (prev ? `${prev}\n${value}` : value) : prev
                        )
                      }
                    >
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue placeholder="选择常见原因模板" />
                      </SelectTrigger>
                      <SelectContent>
                        {decisionTemplates.map((t) => (
                          <SelectItem key={t.value} value={t.value}>
                            {t.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Textarea
                      placeholder="Optional decision reason"
                      value={decisionReason}
                      onChange={(event) => setDecisionReason(event.target.value)}
                      className="min-h-28"
                    />
                    <div className="grid gap-2">
                      <Button onClick={() => decide.mutate("APPROVE")} disabled={decide.isPending}>
                        <CheckCircle2 className="mr-2 h-4 w-4" />
                        Approve
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => decide.mutate("REJECT")}
                        disabled={decide.isPending}
                      >
                        <XCircle className="mr-2 h-4 w-4" />
                        Reject
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => decide.mutate("RETURN")}
                        disabled={decide.isPending}
                      >
                        <RotateCcw className="mr-2 h-4 w-4" />
                        Return for revision
                      </Button>
                      {/* E2: Ticket transfer button */}
                      <Button
                        variant="outline"
                        onClick={() => setTransferOpen(true)}
                        className="w-full"
                      >
                        <ArrowRightLeft className="mr-2 h-4 w-4" />
                        Transfer ticket
                      </Button>
                    </div>
                  </>
                ) : (
                  <div className="rounded-2xl border bg-muted/10 p-4 text-sm leading-6 text-muted-foreground">
                    {ticket.decision_reason?.trim() || "No additional human decision reason was recorded."}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* E4: Review timer */}
            {ticket?.created_at && (
              <ReviewTimer createdAt={ticket.created_at} />
            )}

            <Card className="rounded-[24px]">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Ticket context</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <MetaItem label="Ticket id" value={ticket.ticket_id} mono />
                <MetaItem label="Collection" value={ticket.collection_id} />
                <MetaItem label="Document id" value={document.doc_id || ticket.doc_id} mono />
                <MetaItem label="Parse snapshot" value={effectiveParseSnapshotId} mono />
              </CardContent>
            </Card>

            {/* E3: Full timeline */}
            <Card className="rounded-[24px]">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Timeline
                </CardTitle>
              </CardHeader>
              <CardContent>
                <TicketTimeline
                  createdAt={ticket.created_at}
                  updatedAt={ticket.updated_at}
                  parseSnapshotCreatedAt={parseSnapshot?.created_at}
                  ticketStatus={ticket.status}
                  ticketDecision={ticket.decision}
                />
              </CardContent>
            </Card>

            {/* E1: Ticket comments/discussion */}
            <TicketComments ticketId={ticketId} currentUserId={ticket?.tenant_id} />

            {/* E5: Audit report export + templates + similar tickets */}
            <Card className="rounded-[24px]">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() =>
                    handleExportReport({
                      ticket,
                      findings: reviewFindings,
                      document: { filename: ticket?.filename, doc_id: ticket?.doc_id },
                      decisionLabel: formatReviewDecisionLabel(ticket?.decision),
                    })
                  }
                >
                  <Download className="mr-2 h-4 w-4" />
                  Export audit report
                </Button>
                <ComingSoonButton icon={Wand2} variant="outline" className="w-full">
                  Apply template
                </ComingSoonButton>
                <ComingSoonButton icon={FileText} variant="outline" className="w-full">
                  Similar tickets
                </ComingSoonButton>
              </CardContent>
            </Card>

            {systemActionLabel || ticket.decision || ticket.failure_code || ticket.next_action || degradedParts.length > 0 ? (
              <Card className="rounded-[24px]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">System and diagnostics</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {systemActionLabel || ticket.decision ? (
                    <div className="rounded-2xl border bg-muted/10 p-4">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        System decision
                      </p>
                      <p className="mt-2 text-sm font-medium text-foreground">
                        {systemActionLabel || formatTicketStatusLabel(ticket.decision)}
                        {ticket.decided_by ? ` / ${ticket.decided_by}` : ""}
                      </p>
                      {ticket.decision_reason ? (
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                          {ticket.decision_reason}
                        </p>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {ticket.failure_code ? (
                      <span className="rounded-full border bg-muted/20 px-3 py-1.5">
                        Failure: {ticket.failure_code}
                      </span>
                    ) : null}
                    {ticket.failure_stage ? (
                      <span className="rounded-full border bg-muted/20 px-3 py-1.5">
                        Stage: {formatFailureStageLabel(ticket.failure_stage)}
                      </span>
                    ) : null}
                    {ticket.next_action ? (
                      <span className="rounded-full border bg-muted/20 px-3 py-1.5">
                        Next: {formatNextActionLabel(ticket.next_action)}
                      </span>
                    ) : null}
                    {degradedParts.length > 0 ? (
                      <span className="rounded-full border bg-muted/20 px-3 py-1.5">
                        Degraded: {degradedParts.join(", ")}
                      </span>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            ) : null}
          </aside>
        </div>
      </div>

      <TicketTransferDialog
        ticketId={ticketId}
        currentAssigneeId={ticket?.assignee_user_id}
        open={transferOpen}
        onOpenChange={setTransferOpen}
        onTransferred={() => {
          queryClient.invalidateQueries({ queryKey: ["workspace", ticketId] });
        }}
      />
    </TooltipProvider>
  );
}
