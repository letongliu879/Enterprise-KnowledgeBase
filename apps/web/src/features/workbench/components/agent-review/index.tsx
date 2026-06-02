"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  FileSearch,
  ShieldAlert,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import type { Finding } from "../../types/finding";

interface AgentReviewPanelProps {
  findings: Finding[];
  onSearchInDocument?: (quote: string) => void;
  onJumpToChunk?: (evidenceId: string) => void;
}

export function AgentReviewPanel({
  findings,
  onSearchInDocument,
  onJumpToChunk,
}: AgentReviewPanelProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!findings || findings.length === 0) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="No findings"
        description="No agent review findings are available for this ticket."
      />
    );
  }

  const severityOrder: Record<string, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
    info: 4,
  };

  const sorted = [...findings].sort(
    (a, b) =>
      (severityOrder[a.severity] ?? 99) - (severityOrder[b.severity] ?? 99)
  );

  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <ShieldAlert className="h-4 w-4" />
          Agent Review Findings ({findings.length})
        </CardTitle>
        <CardDescription>
          Click a finding to expand and view details.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {sorted.map((finding) => (
          <FindingCard
            key={finding.finding_id}
            finding={finding}
            isExpanded={expandedId === finding.finding_id}
            onToggle={() =>
              setExpandedId(
                expandedId === finding.finding_id ? null : finding.finding_id
              )
            }
            onSearchInDocument={onSearchInDocument}
            onJumpToChunk={onJumpToChunk}
          />
        ))}
      </CardContent>
    </Card>
  );
}

function FindingCard({
  finding,
  isExpanded,
  onToggle,
  onSearchInDocument,
  onJumpToChunk,
}: {
  finding: Finding;
  isExpanded: boolean;
  onToggle: () => void;
  onSearchInDocument?: (quote: string) => void;
  onJumpToChunk?: (evidenceId: string) => void;
}) {
  const badgeVariant =
    finding.severity === "critical" || finding.severity === "high"
      ? "destructive"
      : finding.severity === "medium"
      ? "secondary"
      : "outline";

  const hasQuote = Boolean(finding.source_quote?.trim());
  const hasEvidence = Boolean(finding.evidence_id);

  return (
    <div className="rounded-2xl border bg-background/85 p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={badgeVariant}>{finding.severity}</Badge>
            {finding.category && (
              <Badge variant="outline">{finding.category}</Badge>
            )}
            {finding.confidence !== undefined && (
              <Badge variant="outline">{Math.round(finding.confidence * 100)}%</Badge>
            )}
          </div>
          <p className="text-sm font-medium">{finding.problem_summary}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onToggle}>
          {isExpanded ? (
            <ChevronUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>

      {isExpanded && (
        <div className="space-y-3 pt-2 border-t">
          {hasQuote && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">Source quote:</p>
              <blockquote className="border-l-2 border-muted pl-3 text-sm italic text-muted-foreground">
                {finding.source_quote}
              </blockquote>
              {onSearchInDocument && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (finding.source_quote) {
                      onSearchInDocument(finding.source_quote);
                    }
                  }}
                >
                  <FileSearch className="mr-1 h-3.5 w-3.5" />
                  Find in document
                </Button>
              )}
            </div>
          )}

          {hasEvidence && onJumpToChunk && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (finding.evidence_id) {
                  onJumpToChunk(finding.evidence_id);
                }
              }}
            >
              Edit chunk
            </Button>
          )}

          {(finding.page_from || finding.page_to) && (
            <p className="text-xs text-muted-foreground">
              Page {finding.page_from ?? "?"} - {finding.page_to ?? "?"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
