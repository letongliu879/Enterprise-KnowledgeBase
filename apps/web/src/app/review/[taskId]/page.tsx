"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RotateCcw,
  FileText,
  Layers,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { BackendGap } from "@/components/backend-gap";
import { isBackendGap, isApiError } from "@/lib/api/errors";
import { toast } from "sonner";

export default function ReviewDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const queryClient = useQueryClient();
  const [decisionReason, setDecisionReason] = useState("");
  const { demoToken } = useAppStore();

  const {
    data: ticket,
    isLoading: ticketLoading,
    error: ticketError,
  } = useQuery({
    queryKey: ["ticket", taskId],
    queryFn: () => workbenchApi.getTicket(taskId),
  });

  const {
    data: agentReview,
    isLoading: reviewLoading,
    error: reviewError,
  } = useQuery({
    queryKey: ["agent-review", taskId],
    queryFn: () => workbenchApi.getAgentReview(taskId),
    enabled: !!taskId,
  });

  const {
    data: parseSnapshot,
    isLoading: snapshotLoading,
  } = useQuery({
    queryKey: ["parse-snapshot", ticket?.parse_snapshot_id],
    queryFn: () =>
      workbenchApi.getParseSnapshot(ticket?.parse_snapshot_id ?? ""),
    enabled: !!ticket?.parse_snapshot_id,
  });

  const {
    data: chunks,
    isLoading: chunksLoading,
  } = useQuery({
    queryKey: ["parse-snapshot-chunks", ticket?.parse_snapshot_id],
    queryFn: () =>
      workbenchApi.getParseSnapshotChunks(ticket?.parse_snapshot_id ?? ""),
    enabled: !!ticket?.parse_snapshot_id,
  });

  const decide = useMutation({
    mutationFn: (action: "APPROVE" | "REJECT" | "RETURN") =>
      workbenchApi.decideTicket(taskId, {
        decision_request_id: `dec_${Date.now()}`,
        action,
        reason: decisionReason,
        tenant_id: ticket?.tenant_id ?? "",
        collection_id: ticket?.collection_id ?? "",
      }),
    onSuccess: () => {
      toast.success("复核决策已记录");
      queryClient.invalidateQueries({ queryKey: ["ticket", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "复核决策失败");
    },
  });

  if (ticketLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 rounded-lg" />
      </div>
    );
  }

  if (ticketError) {
    if (isBackendGap(ticketError)) {
      return <BackendGap feature="工单详情" endpoint={ticketError.endpoint} />;
    }
    return (
      <div className="text-red-500">
        {isApiError(ticketError) ? ticketError.message : String(ticketError)}
      </div>
    );
  }

  const isPending = ticket?.status === "PENDING";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/review">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">复核详情</h1>
          <p className="text-sm text-muted-foreground">{taskId}</p>
        </div>
      </div>

      {/* Metadata */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">文档元数据</CardTitle>
            <Badge
              variant={
                ticket?.status === "PENDING"
                  ? "secondary"
                  : ticket?.status === "APPROVED"
                  ? "default"
                  : "destructive"
              }
            >
              {ticket?.status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-muted-foreground">知识库集合:</span>{" "}
              {ticket?.collection_id}
            </div>
            <div>
              <span className="text-muted-foreground">文档 ID:</span>{" "}
              {ticket?.doc_id ?? "—"}
            </div>
            <div>
              <span className="text-muted-foreground">创建时间:</span>{" "}
              {ticket?.created_at
                ? new Date(ticket.created_at).toLocaleString()
                : "—"}
            </div>
            <div>
              <span className="text-muted-foreground">更新时间:</span>{" "}
              {ticket?.updated_at
                ? new Date(ticket.updated_at).toLocaleString()
                : "—"}
            </div>
            {ticket?.decision && (
              <div>
                <span className="text-muted-foreground">决策:</span>{" "}
                {ticket.decision} · 操作人:{ticket.decided_by ?? "—"}
              </div>
            )}
            {ticket?.decision_reason && (
              <div className="col-span-2">
                <span className="text-muted-foreground">Reason:</span>{" "}
                {ticket.decision_reason}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Agent Review */}
      {reviewError && isBackendGap(reviewError) ? (
        <BackendGap feature="代理审核产物" endpoint={reviewError.endpoint} />
      ) : agentReview ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              代理拦截原因
            </CardTitle>
            <CardDescription>
              决策: {agentReview.decision}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {agentReview.quality_findings.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">质量发现</h4>
                <div className="space-y-2">
                  {agentReview.quality_findings.map((f, i) => (
                    <div key={i} className="rounded-md border p-3 text-sm">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            f.severity === "critical"
                              ? "destructive"
                              : "secondary"
                          }
                          className="text-xs"
                        >
                          {f.severity}
                        </Badge>
                        <span className="font-medium">{f.category}</span>
                      </div>
                      <p className="mt-1 text-muted-foreground">{f.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {agentReview.risk_flags.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">风险标记</h4>
                <div className="flex flex-wrap gap-2">
                  {agentReview.risk_flags.map((f, i) => (
                    <Badge key={i} variant="outline">
                      {f.flag_type}: {f.description}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            {agentReview.suggested_fixes.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">建议修复</h4>
                <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                  {agentReview.suggested_fixes.map((f, i) => (
                    <li key={i}>
                      {f.fix_type} — {f.description}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      ) : reviewLoading ? (
        <Skeleton className="h-32 rounded-lg" />
      ) : null}

      {/* Tabs: Parse Preview / Chunks / Actions */}
      <Tabs defaultValue="chunks">
        <TabsList>
          <TabsTrigger value="chunks">
            <Layers className="h-3.5 w-3.5 mr-1" />
            片段预览
          </TabsTrigger>
          <TabsTrigger value="metadata">
            <FileText className="h-3.5 w-3.5 mr-1" />
            解析元数据
          </TabsTrigger>
        </TabsList>

        <TabsContent value="chunks" className="space-y-3">
          {chunksLoading ? (
            <Skeleton className="h-40 rounded-lg" />
          ) : chunks && chunks.items.length > 0 ? (
            <div className="space-y-2">
              {chunks.items.map((chunk, i) => (
                <Card key={i}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <Badge variant="outline" className="text-xs">
                        {chunk.evidence_id}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {chunk.chunk_type ?? "text"}
                      </span>
                    </div>
                    <p className="text-sm line-clamp-4">{chunk.content}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <BackendGap
              feature="解析快照片段预览"
              endpoint="GET /workbench/parse-snapshots/{id}/chunks"
            />
          )}
        </TabsContent>

        <TabsContent value="metadata">
          {snapshotLoading ? (
            <Skeleton className="h-32 rounded-lg" />
          ) : parseSnapshot ? (
            <Card>
              <CardContent className="p-4">
                <pre className="text-xs overflow-auto max-h-96">
                  {JSON.stringify(parseSnapshot, null, 2)}
                </pre>
              </CardContent>
            </Card>
          ) : (
            <BackendGap
              feature="解析快照查看"
              endpoint="GET /workbench/parse-snapshots/{id}"
            />
          )}
        </TabsContent>
      </Tabs>

      {/* Actions */}
      {isPending && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">复核决策</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="决策原因（可选）"
              value={decisionReason}
              onChange={(e) => setDecisionReason(e.target.value)}
            />
            <div className="flex gap-3">
              <Button
                variant="default"
                className="gap-2"
                onClick={() => decide.mutate("APPROVE")}
                disabled={decide.isPending}
              >
                <CheckCircle2 className="h-4 w-4" />
                批准
              </Button>
              <Button
                variant="destructive"
                className="gap-2"
                onClick={() => decide.mutate("REJECT")}
                disabled={decide.isPending}
              >
                <XCircle className="h-4 w-4" />
                驳回
              </Button>
              <Button
                variant="outline"
                className="gap-2"
                onClick={() => decide.mutate("RETURN")}
                disabled={decide.isPending}
              >
                <RotateCcw className="h-4 w-4" />
                Return
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
