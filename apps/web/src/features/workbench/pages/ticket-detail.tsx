"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  Layers,
  RotateCcw,
  ShieldAlert,
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
import { workbenchApi } from "@/lib/api/client";
import { isBackendGap, isApiError } from "@/lib/api/errors";
import type { Finding } from "@/features/workbench/types/finding";
import {
  formatFailureStageLabel,
  formatNextActionLabel,
  formatReviewDecisionLabel,
  formatTicketStatusLabel,
  normalizeStatus,
} from "@/lib/status";

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

export function TicketDetailPage({ ticketId, backHref = "/review" }: { ticketId: string; backHref?: string }) {
  const queryClient = useQueryClient();
  const [decisionReason, setDecisionReason] = useState("");
  const [activeTab, setActiveTab] = useState("source");
  const [searchText, setSearchText] = useState("");
  const [focusedEvidenceId, setFocusedEvidenceId] = useState<string | null>(null);

  const {
    data: ticket,
    isLoading: ticketLoading,
    error: ticketError,
  } = useQuery({
    queryKey: ["ticket", ticketId],
    queryFn: () => workbenchApi.getTicket(ticketId),
    enabled: Boolean(ticketId),
    retry: 0,
  });

  const {
    data: agentReview,
    isLoading: reviewLoading,
    error: reviewError,
  } = useQuery({
    queryKey: ["agent-review", ticketId],
    queryFn: () => workbenchApi.getAgentReview(ticketId),
    enabled: Boolean(ticket?.ticket_id),
    retry: 0,
  });

  const parseSnapshotId = ticket?.parse_snapshot_id ?? "";

  const {
    data: parseSnapshot,
    isLoading: snapshotLoading,
    error: snapshotError,
  } = useQuery({
    queryKey: ["parse-snapshot", parseSnapshotId],
    queryFn: () => workbenchApi.getParseSnapshot(parseSnapshotId),
    enabled: Boolean(parseSnapshotId),
    retry: 0,
  });

  const {
    data: chunks,
    error: chunksError,
  } = useQuery({
    queryKey: ["review-viewer-chunks", parseSnapshotId],
    queryFn: () => workbenchApi.getParseSnapshotChunks(parseSnapshotId),
    enabled: Boolean(parseSnapshotId),
    retry: 0,
  });

  const {
    data: chunkEdits,
    isLoading: chunkEditsLoading,
  } = useQuery({
    queryKey: ["review-viewer-edits", parseSnapshotId],
    queryFn: () => workbenchApi.listChunkEdits(parseSnapshotId),
    enabled: Boolean(parseSnapshotId),
    retry: 0,
  });

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
      await queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
      await queryClient.invalidateQueries({ queryKey: ["tickets"] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "Failed to submit review decision");
    },
  });

  const hasParseSnapshot = Boolean(parseSnapshotId);
  const isPending = normalizeStatus(ticket?.status) === "pending";
  const displayTitle =
    ticket?.filename?.trim() || ticket?.doc_id?.trim() || ticket?.ticket_id || ticketId;

  const editedCount = useMemo(
    () => chunkEdits?.items.length ?? 0,
    [chunkEdits?.items.length]
  );

  const reviewFindings = useMemo<Finding[]>(
    () => agentReview?.findings ?? [],
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
      sourceFilename: String(parseSnapshot.source_filename || ticket?.filename || "-"),
      sourceSuffix: String(parseSnapshot.source_suffix || "-"),
      parserId: String(parseSnapshot.parser_id || "-"),
      parserBackend: String(parseSnapshot.parser_backend || "-"),
      effectivePolicy: String(
        parseSnapshot.effective_policy || parseSnapshot.decision_reason || "-"
      ),
      previewText: String(parseSnapshot.preview_text || "").trim(),
      warnings: Array.isArray(parseSnapshot.warnings)
        ? parseSnapshot.warnings.map((item: unknown) => String(item))
        : [],
    };
  }, [parseSnapshot, ticket?.filename]);

  const warningCount = parseSnapshotSummary?.warnings.length ?? 0;

  if (ticketLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-56 rounded-lg" />
        <Skeleton className="h-36 rounded-lg" />
      </div>
    );
  }

  if (ticketError) {
    if (isBackendGap(ticketError)) {
      return <BackendGap feature="Review detail" endpoint={ticketError.endpoint} />;
    }
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{isApiError(ticketError) ? ticketError.message : String(ticketError)}</AlertDescription>
      </Alert>
    );
  }

  if (!ticket) {
    return (
      <EmptyState
        icon={FileText}
        title="Review ticket not found"
        description="The review ticket record is unavailable or you no longer have access to it."
      />
    );
  }

  return (
    <div className="space-y-6">
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
                </div>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight xl:text-4xl">
                  {displayTitle}
                </h1>
                <p className="mt-2 text-sm text-muted-foreground">
                  Human review writes back to the ticket state. Keep the source, parsed draft, and
                  agent assessment aligned before you approve publish.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:min-w-[420px]">
              <SummaryMetric label="Findings" value={reviewSummary.findings} tone="text-amber-600" />
              <SummaryMetric label="Risks" value={reviewSummary.risks} tone="text-rose-600" />
              <SummaryMetric
                label="Draft edits"
                value={chunkEditsLoading ? "-" : editedCount}
                tone="text-sky-600"
              />
              <SummaryMetric label="Warnings" value={warningCount} tone="text-violet-600" />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <MetaItem label="Ticket id" value={ticket.ticket_id} mono />
            <MetaItem label="Collection" value={ticket.collection_id} />
            <MetaItem label="Document id" value={ticket.doc_id} mono />
            <MetaItem label="Parse snapshot" value={ticket.parse_snapshot_id} mono />
          </div>
        </div>
      </section>

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
            </TabsList>

            <TabsContent value="source" className="space-y-4">
              {!hasParseSnapshot ? (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>This ticket does not currently link to a parse snapshot.</AlertDescription>
                </Alert>
              ) : (
                <DocumentViewer
                  parseSnapshotId={parseSnapshotId}
                  filename={ticket.filename || parseSnapshotSummary?.sourceFilename}
                  previewText={parseSnapshotSummary?.previewText}
                  parserId={parseSnapshotSummary?.parserId}
                  parserBackend={parseSnapshotSummary?.parserBackend}
                  warnings={parseSnapshotSummary?.warnings}
                  chunks={chunks?.items ?? []}
                  searchText={searchText}
                  onSearchComplete={(found) => {
                    if (!found) {
                      toast.info("Text not found in current view");
                    }
                  }}
                />
              )}

              {!hasParseSnapshot ? null : snapshotError ? (
                isBackendGap(snapshotError) ? (
                  <BackendGap feature="Parse snapshot" endpoint={snapshotError.endpoint} />
                ) : (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      {isApiError(snapshotError) ? snapshotError.message : String(snapshotError)}
                    </AlertDescription>
                  </Alert>
                )
              ) : snapshotLoading ? (
                <Skeleton className="h-32 rounded-2xl" />
              ) : parseSnapshotSummary ? (
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
                  <Card className="rounded-2xl">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Parse context</CardTitle>
                      <CardDescription>
                        This is the parser configuration and normalized preview context used for the
                        review ticket.
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
                        <SummaryMetric label="Chunks" value={chunks?.items.length ?? 0} tone="text-slate-900" />
                        <SummaryMetric label="Warnings" value={warningCount} tone="text-violet-600" />
                        <SummaryMetric label="Edits" value={chunkEditsLoading ? "-" : editedCount} tone="text-sky-600" />
                      </div>
                      <div className="max-h-52 overflow-auto rounded-2xl border bg-muted/10 p-4 text-sm leading-7">
                        {parseSnapshotSummary.previewText || "No preview text is available for this parse snapshot."}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ) : (
                <EmptyState
                  icon={ShieldAlert}
                  title="Parse summary is not available"
                  description="The parse snapshot exists, but the summary payload is incomplete."
                />
              )}
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
              {chunksError && isBackendGap(chunksError) ? (
                <BackendGap feature="Parse snapshot chunks" endpoint={chunksError.endpoint} />
              ) : (
                <ChunkEditorWorkbench
                  parseSnapshotId={parseSnapshotId}
                  mode="pre-publish"
                  title="Draft corrections"
                  description="Tighten chunk wording, restore broken structure, and submit governed draft edits before the human decision."
                  focusEvidenceId={focusedEvidenceId}
                />
              )}
            </TabsContent>

            <TabsContent value="agent" className="space-y-4">
              {reviewError ? (
                isBackendGap(reviewError) ? (
                  <BackendGap feature="Agent review" endpoint={reviewError.endpoint} />
                ) : (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      {isApiError(reviewError) ? reviewError.message : String(reviewError)}
                    </AlertDescription>
                  </Alert>
                )
              ) : reviewLoading ? (
                <Skeleton className="h-44 rounded-2xl" />
              ) : (
                <AgentReviewPanel
                  findings={reviewFindings}
                  onSearchInDocument={(quote) => {
                    setFocusedEvidenceId(null);
                    setSearchText(quote);
                    setActiveTab("source");
                  }}
                  onJumpToChunk={(evidenceId) => {
                    setFocusedEvidenceId(evidenceId);
                    setActiveTab("drafts");
                  }}
                />
              )}
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

              {isPending ? (
                <>
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
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border bg-muted/10 p-4 text-sm leading-6 text-muted-foreground">
                  {ticket.decision_reason?.trim() || "No additional human decision reason was recorded."}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-[24px]">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Ticket context</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <MetaItem label="Ticket id" value={ticket.ticket_id} mono />
              <MetaItem label="Collection" value={ticket.collection_id} />
              <MetaItem label="Document id" value={ticket.doc_id} mono />
              <MetaItem label="Parse snapshot" value={ticket.parse_snapshot_id} mono />
            </CardContent>
          </Card>

          {systemActionLabel || ticket.decision || ticket.failure_code || ticket.next_action ? (
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
                </div>
              </CardContent>
            </Card>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
