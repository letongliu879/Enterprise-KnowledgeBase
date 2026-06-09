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
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  XCircle,
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
import { workbenchApi } from "@/lib/api/client";
import { isApiError, getErrorMessage } from "@/lib/api/errors";
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

export default function DocumentDetailPage() {
  const { docId } = useParams<{ docId: string }>();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("source");
  const [searchText, setSearchText] = useState("");
  const [focusedEvidenceId, setFocusedEvidenceId] = useState<string | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [lifecycleAction, setLifecycleAction] = useState<LifecycleAction | null>(null);
  const [lifecycleReason, setLifecycleReason] = useState("");
  const [indexProfileId, setIndexProfileId] = useState("ragflow");

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
  const isPendingReview = normalizeStatus(ticket?.status) === "pending";

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
    </div>
  );
}
