"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  Layers,
  MessageSquare,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  XCircle,
  Share2,
  History,
  Users,
  FileSearch,
  FileDown,
  FileType,
  FileCode,
  Link2,
  Lock,
  CalendarClock,
  Copy,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import { AgentReviewPanel } from "@/features/workbench/components/agent-review";
import { DocumentViewer } from "@/components/document-workbench/document-viewer";
import { ChunkEditorWorkbench } from "@/features/workbench/components/chunk-editor";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { workbenchApi } from "@/lib/api/client";
import { isApiError, isBackendGap, getErrorMessage } from "@/lib/api/errors";
import { BackendGap } from "@/components/backend-gap";
import type { Finding } from "@/features/workbench/types/finding";
import {
  formatFailureStageLabel,
  formatNextActionLabel,
  formatReviewDecisionLabel,
  formatTicketStatusLabel,
  normalizeStatus,
} from "@/lib/status";

type LifecycleAction = "archive" | "retract" | "reindex";

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
      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
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
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className={`break-all text-sm text-foreground ${mono ? "font-mono" : "font-medium"}`}>
        {value?.trim() || "-"}
      </p>
    </div>
  );
}

function LifecycleButton({
  label,
  icon: Icon,
  onClick,
  variant = "outline",
}: {
  label: string;
  icon: typeof RotateCcw;
  onClick: () => void;
  variant?: "outline" | "destructive" | "default";
}) {
  return (
    <Button variant={variant} onClick={onClick} className="justify-start">
      <Icon className="mr-2 h-4 w-4" />
      {label}
    </Button>
  );
}

function SidebarSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="rounded-[24px] shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function PlaceholderBadge() {
  return (
    <Badge variant="outline" className="text-[10px]">
      即将推出
    </Badge>
  );
}

const PLACEHOLDER_VERSIONS = [
  { version: "v1.2", date: "2024-05-20", author: "系统", note: "自动解析更新" },
  { version: "v1.1", date: "2024-04-12", author: "管理员", note: "内容修订" },
  { version: "v1.0", date: "2024-03-01", author: "上传者", note: "初始版本" },
];

const PLACEHOLDER_ACCESSORS = [
  { name: "张三", time: "2小时前", action: "查看" },
  { name: "李四", time: "昨天", action: "下载" },
  { name: "王五", time: "3天前", action: "查看" },
  { name: "赵六", time: "1周前", action: "编辑" },
  { name: "孙七", time: "2周前", action: "查看" },
];

const PLACEHOLDER_RELATED = [
  { title: "相关文档 A", type: "PDF", similarity: "92%" },
  { title: "相关文档 B", type: "DOCX", similarity: "85%" },
  { title: "相关文档 C", type: "TXT", similarity: "78%" },
];

function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadJSON(filename: string, content: unknown) {
  const blob = new Blob([JSON.stringify(content, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function DocumentDetailPage() {
  const { docId } = useParams<{ docId: string }>();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("source");
  const [searchText, setSearchText] = useState("");
  const [searchCaseSensitive, setSearchCaseSensitive] = useState(false);
  const [focusedEvidenceId, setFocusedEvidenceId] = useState<string | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [lifecycleAction, setLifecycleAction] = useState<LifecycleAction | null>(null);
  const [lifecycleReason, setLifecycleReason] = useState("");
  const [indexProfileId, setIndexProfileId] = useState("ragflow");
  const [shareOpen, setShareOpen] = useState(false);
  const [shareExpiry, setShareExpiry] = useState("7");
  const [sharePassword, setSharePassword] = useState("");
  const [shareReadOnly, setShareReadOnly] = useState(true);

  const {
    data: workspace,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["document-workspace", docId],
    queryFn: () => workbenchApi.getDocumentWorkspace(docId),
    enabled: Boolean(docId),
    retry: 0,
  });

  const ticket = workspace?.ticket ?? null;
  const task = workspace?.task ?? null;
  const document = workspace?.document ?? null;
  const parseSnapshot = workspace?.parse_snapshot ?? null;
  const chunks = workspace?.chunks;
  const chunkEdits = workspace?.chunk_edits;
  const agentReview = workspace?.agent_review;
  const capabilities = workspace?.capabilities;
  const degradedParts = workspace?.degraded_parts ?? [];

  const displayTitle =
    document?.filename?.trim() ||
    ticket?.filename?.trim() ||
    document?.doc_id?.trim() ||
    docId;
  const effectiveSourceFileId =
    document?.source_file_id || ticket?.source_file_id || task?.source_file_id || null;
  const effectiveParseSnapshotId =
    document?.parse_snapshot_id || ticket?.parse_snapshot_id || task?.parse_snapshot_id || "";
  const isPendingReview = normalizeStatus(ticket?.status) === "pending_review";

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
      blocking: reviewFindings.filter((item) => ["critical", "high"].includes(item.severity)).length,
      matched: reviewFindings.filter((item) => Boolean(item.evidence_id)).length,
    }),
    [reviewFindings]
  );

  const decideTicket = useMutation({
    mutationFn: (action: "APPROVE" | "REJECT" | "RETURN") => {
      if (!ticket) throw new Error("No review ticket linked to this document");
      return workbenchApi.decideTicket(ticket.ticket_id, {
        decision_request_id: `dec_${Date.now()}`,
        action,
        reason: decisionReason || undefined,
        tenant_id: ticket.tenant_id,
        collection_id: ticket.collection_id,
      });
    },
    onSuccess: async () => {
      toast.success("Review decision submitted");
      await queryClient.invalidateQueries({ queryKey: ["document-workspace", docId] });
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      if (ticket?.ticket_id) {
        await queryClient.invalidateQueries({ queryKey: ["workspace", ticket.ticket_id] });
        await queryClient.invalidateQueries({ queryKey: ["tickets"] });
      }
    },
    onError: (mutationError) => {
      toast.error(isApiError(mutationError) ? mutationError.message : getErrorMessage(mutationError));
    },
  });

  const lifecycleMutation = useMutation({
    mutationFn: async () => {
      if (!lifecycleAction || !document?.doc_id) {
        throw new Error("Lifecycle action is not ready");
      }
      const payload = {
        reason: lifecycleReason,
        index_profile_id: lifecycleAction === "reindex" ? indexProfileId || undefined : undefined,
      };
      if (lifecycleAction === "archive") {
        return workbenchApi.archiveDocument(document.doc_id, payload);
      }
      if (lifecycleAction === "retract") {
        return workbenchApi.retractDocument(document.doc_id, payload);
      }
      return workbenchApi.reindexDocument(document.doc_id, payload);
    },
    onSuccess: async (result) => {
      toast.success(
        `${lifecycleAction === "reindex" ? "Reindex" : lifecycleAction === "archive" ? "Archive" : "Retract"} started: ${result.new_state || "ok"}`
      );
      setLifecycleAction(null);
      setLifecycleReason("");
      await queryClient.invalidateQueries({ queryKey: ["document-workspace", docId] });
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      if (ticket?.ticket_id) {
        await queryClient.invalidateQueries({ queryKey: ["workspace", ticket.ticket_id] });
        await queryClient.invalidateQueries({ queryKey: ["tickets"] });
      }
    },
    onError: (mutationError) => {
      toast.error(isApiError(mutationError) ? mutationError.message : getErrorMessage(mutationError));
    },
  });

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
      return <BackendGap feature="Document workspace" endpoint={error.endpoint} />;
    }
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          {isApiError(error) ? error.message : getErrorMessage(error)}
        </AlertDescription>
      </Alert>
    );
  }

  if (!workspace || !document) {
    return (
      <EmptyState
        icon={FileText}
        title="Document workspace not found"
        description="The document is unavailable or you no longer have access to it."
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border bg-card/92 p-5 shadow-sm">
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="flex items-start gap-3">
              <Button
                variant="outline"
                size="icon"
                className="mt-1 rounded-full"
                onClick={() => {
                  window.location.href = "/documents";
                }}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">
                    {document.document_state || "UNKNOWN"}
                  </Badge>
                  {ticket?.status ? (
                    <Badge variant="secondary">
                      Review: {formatTicketStatusLabel(ticket.status)}
                    </Badge>
                  ) : null}
                  {task?.status ? (
                    <Badge variant="outline">Task: {task.status}</Badge>
                  ) : null}
                  {document.is_stale ? (
                    <Badge variant="destructive">STALE</Badge>
                  ) : null}
                  {degradedParts.length > 0 ? (
                    <Badge variant="outline">
                      Degraded: {degradedParts.join(", ")}
                    </Badge>
                  ) : null}
                </div>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight xl:text-4xl">
                  {displayTitle}
                </h1>
                <p className="mt-2 text-sm text-muted-foreground">
                  Document workspace combines source preview, parsed chunks,
                  linked review signals, and lifecycle operations.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:min-w-[420px]">
              <SummaryMetric label="Findings" value={reviewSummary.findings} tone="text-amber-600" />
              <SummaryMetric label="Blocking" value={reviewSummary.blocking} tone="text-rose-600" />
              <SummaryMetric label="Chunks" value={chunks?.total ?? document.chunk_count} tone="text-sky-600" />
              <SummaryMetric label="Draft edits" value={chunkEdits?.total ?? 0} tone="text-violet-600" />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <MetaItem label="Doc ID" value={document.doc_id} mono />
            <MetaItem label="Collection" value={document.collection_id} />
            <MetaItem label="Source File" value={effectiveSourceFileId} mono />
            <MetaItem label="Parse Snapshot" value={effectiveParseSnapshotId} mono />
          </div>
        </div>
      </section>

      {degradedParts.length > 0 ? (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Workspace data is partially degraded: {degradedParts.join(", ")}.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="Search inside the document..."
              className="max-w-sm"
            />
            <Switch
              checked={searchCaseSensitive}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchCaseSensitive(e.target.checked)}
              label="区分大小写"
            />
            {searchText ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearchText("");
                  setFocusedEvidenceId(null);
                }}
              >
                Clear Search
              </Button>
            ) : null}
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList
              variant="line"
              className="w-full justify-start gap-2 overflow-x-auto rounded-none border-0 bg-transparent p-0"
            >
              <TabsTrigger value="source">
                <FileText className="mr-1 h-3.5 w-3.5" />
                Source
              </TabsTrigger>
              <TabsTrigger value="chunks">
                <Layers className="mr-1 h-3.5 w-3.5" />
                Drafts / Chunks
              </TabsTrigger>
              <TabsTrigger value="agent">
                <ShieldAlert className="mr-1 h-3.5 w-3.5" />
                Agent Review
              </TabsTrigger>
              <TabsTrigger value="annotations">
                <MessageSquare className="mr-1 h-3.5 w-3.5" />
                批注
              </TabsTrigger>
            </TabsList>

            <TabsContent value="source" className="space-y-4">
              {!effectiveSourceFileId ? (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    This document is not linked to a source file.
                  </AlertDescription>
                </Alert>
              ) : (
                <DocumentViewer
                  sourceFileId={effectiveSourceFileId}
                  filename={displayTitle}
                  previewText={parseSnapshot?.preview_text}
                  parserId={parseSnapshot?.parser_id}
                  parserBackend={parseSnapshot?.parser_backend}
                  warnings={parseSnapshot?.warnings ?? []}
                  chunks={chunks?.items ?? []}
                  searchText={searchText}
                  searchCaseSensitive={searchCaseSensitive}
                  onSearchComplete={(found) => {
                    if (searchText.trim() && !found) {
                      toast.info("Text not found in current document view");
                    }
                  }}
                />
              )}
            </TabsContent>

            <TabsContent value="chunks" className="space-y-4">
              {!effectiveParseSnapshotId ? (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    No parse snapshot is linked to this document, so chunk tools are unavailable.
                  </AlertDescription>
                </Alert>
              ) : (
                <ChunkEditorWorkbench
                  parseSnapshotId={effectiveParseSnapshotId}
                  mode="post-publish"
                  title="Document chunk management"
                  description="Edit indexed chunks while keeping the original parse context visible."
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
                        setActiveTab("chunks");
                      }
                    : undefined
                }
              />
            </TabsContent>

            <TabsContent value="annotations" className="space-y-4">
              <EmptyState
                icon={MessageSquare}
                title="批注功能即将推出"
                description="文档批注与协作评论功能正在开发中，敬请期待。"
              />
            </TabsContent>
          </Tabs>
        </div>

        <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
          <Card className="rounded-[24px] shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Review Cockpit</CardTitle>
              <CardDescription>
                Human review stays embedded when this document is linked to a ticket.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {ticket ? (
                <>
                  <div className="rounded-2xl border bg-muted/10 p-4">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="secondary">{formatTicketStatusLabel(ticket.status)}</Badge>
                      {ticket.decision ? (
                        <Badge variant="outline">{formatReviewDecisionLabel(ticket.decision)}</Badge>
                      ) : null}
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">
                      {ticket.ticket_id}
                    </p>
                  </div>

                  {capabilities?.can_decide_ticket && isPendingReview ? (
                    <>
                      <Textarea
                        placeholder="Optional review reason"
                        value={decisionReason}
                        onChange={(event) => setDecisionReason(event.target.value)}
                        className="min-h-24"
                      />
                      <div className="grid gap-2">
                        <Button
                          onClick={() => decideTicket.mutate("APPROVE")}
                          disabled={decideTicket.isPending}
                        >
                          <CheckCircle2 className="mr-2 h-4 w-4" />
                          Approve
                        </Button>
                        <Button
                          variant="destructive"
                          onClick={() => decideTicket.mutate("REJECT")}
                          disabled={decideTicket.isPending}
                        >
                          <XCircle className="mr-2 h-4 w-4" />
                          Reject
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => decideTicket.mutate("RETURN")}
                          disabled={decideTicket.isPending}
                        >
                          <RotateCcw className="mr-2 h-4 w-4" />
                          Return
                        </Button>
                      </div>
                    </>
                  ) : (
                    <div className="rounded-2xl border bg-muted/10 p-4 text-sm text-muted-foreground">
                      {ticket.decision_reason?.trim() || "No additional review reason recorded."}
                    </div>
                  )}
                </>
              ) : (
                <EmptyState
                  icon={ShieldCheck}
                  title="No review ticket"
                  description="This document is not currently linked to a review workflow."
                />
              )}
            </CardContent>
          </Card>

          <SidebarSection title="分享" description="生成共享链接，控制访问权限与有效期。">
            <Button variant="outline" className="w-full justify-start" onClick={() => setShareOpen(true)}>
              <Share2 className="mr-2 h-4 w-4" />
              分享文档
            </Button>
          </SidebarSection>

          <SidebarSection title="导出" description="将当前文档内容导出为不同格式。">
            <div className="grid grid-cols-2 gap-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Button variant="outline" size="sm" disabled>
                      <FileDown className="mr-1.5 h-3.5 w-3.5" />
                      PDF
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>PDF 导出需要后端支持，即将推出</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Button variant="outline" size="sm" disabled>
                      <FileType className="mr-1.5 h-3.5 w-3.5" />
                      Word
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Word 导出需要后端支持，即将推出</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const text = parseSnapshot?.preview_text?.trim() || "";
                  if (!text) {
                    toast.info("当前没有可导出的解析文本");
                    return;
                  }
                  downloadText(displayTitle || "document", text);
                  toast.success("文本已下载");
                }}
              >
                <FileText className="mr-1.5 h-3.5 w-3.5" />
                Text
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const text = parseSnapshot?.preview_text?.trim() || "";
                  if (!text) {
                    toast.info("当前没有可导出的解析文本");
                    return;
                  }
                  const md = `# ${displayTitle || "Document"}\n\n${text}`;
                  downloadMarkdown(displayTitle || "document", md);
                  toast.success("Markdown 已下载");
                }}
              >
                <FileCode className="mr-1.5 h-3.5 w-3.5" />
                Markdown
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const payload = {
                    doc_id: document?.doc_id,
                    filename: displayTitle,
                    collection_id: document?.collection_id,
                    document_state: document?.document_state,
                    chunk_count: document?.chunk_count,
                    page_count: document?.page_count,
                    preview_text: parseSnapshot?.preview_text,
                    parser_id: parseSnapshot?.parser_id,
                    parser_backend: parseSnapshot?.parser_backend,
                    warnings: parseSnapshot?.warnings,
                    exported_at: new Date().toISOString(),
                  };
                  downloadJSON(displayTitle || "document", payload);
                  toast.success("JSON 已下载");
                }}
              >
                <FileCode className="mr-1.5 h-3.5 w-3.5" />
                JSON
              </Button>
            </div>
          </SidebarSection>

          <SidebarSection title="版本历史" description="查看文档的历史版本记录。">
            <div className="space-y-2">
              {PLACEHOLDER_VERSIONS.map((v) => (
                <div
                  key={v.version}
                  className="flex items-center justify-between rounded-xl border bg-muted/10 px-3 py-2"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{v.version}</span>
                      <span className="text-xs text-muted-foreground">{v.date}</span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {v.author} · {v.note}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 ml-2 shrink-0">
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger>
                          <Button variant="ghost" size="icon" className="h-7 w-7" disabled>
                            <RotateCcw className="h-3.5 w-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>恢复版本</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger>
                          <Button variant="ghost" size="icon" className="h-7 w-7" disabled>
                            <FileSearch className="h-3.5 w-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>对比版本</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </div>
              ))}
            </div>
          </SidebarSection>

          <SidebarSection title="访问记录" description="最近查看过此文档的用户。">
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">最近 10 位查看者</p>
              {PLACEHOLDER_ACCESSORS.map((a, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-xl border bg-muted/10 px-3 py-2"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Users className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-sm truncate">{a.name}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-2">
                    <Badge variant="outline" className="text-[10px]">
                      {a.action}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{a.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </SidebarSection>

          <SidebarSection title="相关文档" description="基于内容相似度推荐的相关文档。">
            <div className="space-y-2">
              {PLACEHOLDER_RELATED.map((r, i) => (
                <div
                  key={i}
                  className="group flex items-center justify-between rounded-xl border bg-muted/10 px-3 py-2 cursor-pointer hover:bg-muted/20 transition-colors"
                  onClick={() => toast.info("相关文档跳转功能即将推出")}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      <span className="text-sm font-medium truncate">{r.title}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      相似度 {r.similarity}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0 ml-2">
                    <Badge variant="outline" className="text-[10px]">
                      {r.type}
                    </Badge>
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                </div>
              ))}
            </div>
          </SidebarSection>

          <Card className="rounded-[24px]">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Lifecycle Actions</CardTitle>
              <CardDescription>
                Published-document actions stay behind admin permissions.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {capabilities?.can_archive ? (
                <LifecycleButton
                  label="Archive Document"
                  icon={Database}
                  onClick={() => setLifecycleAction("archive")}
                />
              ) : null}
              {capabilities?.can_retract ? (
                <LifecycleButton
                  label="Retract Document"
                  icon={XCircle}
                  onClick={() => setLifecycleAction("retract")}
                  variant="destructive"
                />
              ) : null}
              {capabilities?.can_reindex ? (
                <LifecycleButton
                  label="Reindex Document"
                  icon={RotateCcw}
                  onClick={() => setLifecycleAction("reindex")}
                  variant="default"
                />
              ) : null}
              {!capabilities?.can_archive &&
              !capabilities?.can_retract &&
              !capabilities?.can_reindex ? (
                <div className="rounded-2xl border bg-muted/10 p-4 text-sm text-muted-foreground">
                  Lifecycle actions are unavailable for this user or this document state.
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="rounded-[24px]">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Diagnostics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <MetaItem label="Task Status" value={task?.status || "-"} />
              <MetaItem label="Index Version" value={document.active_index_version || "-"} mono />
              <MetaItem
                label="Next Action"
                value={ticket?.next_action ? formatNextActionLabel(ticket.next_action) : "-"}
              />
              <MetaItem
                label="Failure Stage"
                value={ticket?.failure_stage ? formatFailureStageLabel(ticket.failure_stage) : "-"}
              />
              {ticket?.failure_code ? (
                <Alert variant="destructive">
                  <Clock3 className="h-4 w-4" />
                  <AlertDescription>{ticket.failure_code}</AlertDescription>
                </Alert>
              ) : null}
            </CardContent>
          </Card>
        </aside>
      </div>

      <Dialog open={lifecycleAction !== null} onOpenChange={(open) => !open && setLifecycleAction(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {lifecycleAction === "archive"
                ? "Archive document"
                : lifecycleAction === "retract"
                ? "Retract document"
                : "Reindex document"}
            </DialogTitle>
            <DialogDescription>
              This action is proxied through workbench to the admin document operations API.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Textarea
              placeholder="Reason"
              value={lifecycleReason}
              onChange={(event) => setLifecycleReason(event.target.value)}
              className="min-h-24"
            />
            {lifecycleAction === "reindex" ? (
              <Input
                value={indexProfileId}
                onChange={(event) => setIndexProfileId(event.target.value)}
                placeholder="Index profile id"
              />
            ) : null}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setLifecycleAction(null)}
              disabled={lifecycleMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={() => lifecycleMutation.mutate()}
              disabled={lifecycleMutation.isPending}
              variant={lifecycleAction === "retract" ? "destructive" : "default"}
            >
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={shareOpen} onOpenChange={setShareOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>分享文档</DialogTitle>
            <DialogDescription>
              生成共享链接，设置访问权限与有效期。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-xl border bg-muted/10 p-3">
              <div className="flex items-center gap-2">
                <Lock className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">只读链接</span>
              </div>
              <Switch
                checked={shareReadOnly}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setShareReadOnly(e.target.checked)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">有效期</label>
              <div className="flex gap-2">
                {[
                  { label: "1天", value: "1" },
                  { label: "7天", value: "7" },
                  { label: "30天", value: "30" },
                ].map((opt) => (
                  <Button
                    key={opt.value}
                    variant={shareExpiry === opt.value ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => setShareExpiry(opt.value)}
                  >
                    {opt.label}
                  </Button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">访问密码（可选）</label>
              <Input
                type="password"
                placeholder="留空表示无需密码"
                value={sharePassword}
                onChange={(e) => setSharePassword(e.target.value)}
              />
            </div>
            <Separator />
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <Button className="w-full" disabled>
                    <Link2 className="mr-2 h-4 w-4" />
                    生成链接
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>分享功能需要后端 API 支持，即将推出</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
