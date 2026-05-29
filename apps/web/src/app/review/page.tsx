"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Inbox,
  AlertCircle,
  Clock,
  CheckCircle2,
  XCircle,
  Filter,
  ChevronRight,
  FileText,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { BackendGap } from "@/components/backend-gap";
import { isBackendGap, isApiError } from "@/lib/api/errors";

export default function ReviewQueuePage() {
  const [collectionFilter, setCollectionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const { data, isLoading, error } = useQuery({
    queryKey: ["tickets", collectionFilter, statusFilter],
    queryFn: () =>
      workbenchApi.listTickets({
        collection_id: collectionFilter || undefined,
        status: statusFilter === "ALL" ? undefined : statusFilter,
      }),
  });

  const tickets = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">人工复核队列</h1>
        <p className="text-sm text-muted-foreground mt-1">
          自动入库代理拦截的文档，等待人工复核。
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="知识库集合..."
            value={collectionFilter}
            onChange={(e) => setCollectionFilter(e.target.value)}
            className="w-40 h-8"
          />
        </div>
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v ?? "ALL")}
        >
          <SelectTrigger className="w-36 h-8">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">全部</SelectItem>
            <SelectItem value="PENDING">待复核</SelectItem>
            <SelectItem value="APPROVED">已批准</SelectItem>
            <SelectItem value="REJECTED">已驳回</SelectItem>
            <SelectItem value="RETURNED">已退回</SelectItem>
          </SelectContent>
        </Select>
        {(collectionFilter || statusFilter !== "ALL") && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setCollectionFilter("");
              setStatusFilter("ALL");
            }}
          >
            清除
          </Button>
        )}
      </div>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
      )}

      {error && (
        isBackendGap(error) ? (
          <BackendGap feature="Review Queue (Tickets)" endpoint={error.endpoint} />
        ) : (
          <div className="text-red-500 text-sm">
            {isApiError(error) ? error.message : String(error)}
          </div>
        )
      )}

      {!isLoading && !error && tickets.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="暂无复核工单"
          description="所有文档已处理完毕。上传新文件以生成复核工单。"
        />
      ) : (
        <div className="space-y-2">
          {tickets.map((ticket, i) => (
            <motion.div
              key={ticket.ticket_id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <Link href={`/review/${ticket.ticket_id}`}>
                <Card className="hover:border-primary/50 transition-colors cursor-pointer">
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="shrink-0">
                      {ticket.status === "PENDING" ? (
                        <Clock className="h-5 w-5 text-amber-500" />
                      ) : ticket.status === "APPROVED" ? (
                        <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                      ) : ticket.status === "REJECTED" ? (
                        <XCircle className="h-5 w-5 text-red-500" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium truncate">
                          {ticket.doc_id ?? ticket.ticket_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <Badge variant="outline" className="text-xs">
                          {ticket.collection_id}
                        </Badge>
                        <span>
                          Updated: {ticket.updated_at ? new Date(ticket.updated_at).toLocaleString() : "—"}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge
                        variant={
                          ticket.status === "PENDING"
                            ? "secondary"
                            : ticket.status === "APPROVED"
                            ? "default"
                            : "destructive"
                        }
                      >
                        {ticket.status}
                      </Badge>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
