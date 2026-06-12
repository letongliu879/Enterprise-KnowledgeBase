"use client";

import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Edit2,
  MessageSquare,
  Send,
  Trash2,
  User,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { workbenchApi } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";
import type { TicketComment } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { BackendGap } from "@/components/backend-gap";
import { Skeleton } from "@/components/ui/skeleton";
import { staggerItem } from "@/lib/animations";

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffHours < 24) return `${diffHours} 小时前`;
  if (diffDays < 7) return `${diffDays} 天前`;
  return date.toLocaleString("zh-CN");
}

function highlightMentions(content: string): React.ReactNode {
  const parts = content.split(/(@\S+)/g);
  return parts.map((part, index) => {
    if (part.startsWith("@")) {
      return (
        <span key={index} className="font-medium text-primary">
          {part}
        </span>
      );
    }
    return <span key={index}>{part}</span>;
  });
}

function CommentItem({
  comment,
  currentUserId,
  onEdit,
  onDelete,
}: {
  comment: TicketComment;
  currentUserId?: string;
  onEdit: (comment: TicketComment) => void;
  onDelete: (commentId: string) => void;
}) {
  const isAuthor = currentUserId && comment.author_id === currentUserId;

  return (
    <motion.div
      variants={staggerItem}
      initial="hidden"
      animate="visible"
      className="group flex gap-3 rounded-2xl border bg-muted/10 p-4"
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <User className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 truncate">
            <span className="text-sm font-medium">
              {comment.author_name || comment.author_email || comment.author_id}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatRelativeTime(comment.created_at)}
            </span>
            {comment.updated_at && comment.updated_at !== comment.created_at ? (
              <span className="text-xs text-muted-foreground">(已编辑)</span>
            ) : null}
          </div>
          {isAuthor ? (
            <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                type="button"
                aria-label="编辑评论"
                onClick={() => onEdit(comment)}
                className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <Edit2 className="h-4 w-4" />
              </button>
              <button
                type="button"
                aria-label="删除评论"
                onClick={() => onDelete(comment.comment_id)}
                className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ) : null}
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
          {highlightMentions(comment.content)}
        </p>
      </div>
    </motion.div>
  );
}

export function TicketComments({ ticketId, currentUserId }: { ticketId: string; currentUserId?: string }) {
  const queryClient = useQueryClient();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["ticket-comments", ticketId],
    queryFn: () => workbenchApi.listTicketComments(ticketId),
    enabled: Boolean(ticketId),
  });

  const create = useMutation({
    mutationFn: () => workbenchApi.createTicketComment(ticketId, { content: draft.trim() }),
    onSuccess: async () => {
      setDraft("");
      toast.success("评论已发布");
      await queryClient.invalidateQueries({ queryKey: ["ticket-comments", ticketId] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "发布评论失败");
    },
  });

  const update = useMutation({
    mutationFn: ({ commentId, content }: { commentId: string; content: string }) =>
      workbenchApi.updateTicketComment(commentId, { content }),
    onSuccess: async () => {
      setEditingId(null);
      setEditDraft("");
      toast.success("评论已更新");
      await queryClient.invalidateQueries({ queryKey: ["ticket-comments", ticketId] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "更新评论失败");
    },
  });

  const remove = useMutation({
    mutationFn: (commentId: string) => workbenchApi.deleteTicketComment(commentId),
    onSuccess: async () => {
      toast.success("评论已删除");
      await queryClient.invalidateQueries({ queryKey: ["ticket-comments", ticketId] });
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "删除评论失败");
    },
  });

  const comments = useMemo(() => data?.items ?? [], [data]);

  if (error) {
    return <BackendGap feature="工单评论" endpoint={`GET /workbench/tickets/${ticketId}/comments`} />;
  }

  return (
    <Card className="rounded-[24px]">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          评论
        </CardTitle>
        <CardDescription>围绕此工单进行讨论和记录备注</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-20 w-full rounded-2xl" data-testid="comment-skeleton" />
            <Skeleton className="h-20 w-full rounded-2xl" data-testid="comment-skeleton" />
          </div>
        ) : (
          <div className="max-h-[360px] space-y-3 overflow-y-auto pr-1">
            <AnimatePresence initial={false}>
              {comments.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  暂无评论，写下第一条评论吧
                </p>
              ) : (
                comments.map((comment) =>
                  editingId === comment.comment_id ? (
                    <motion.div
                      key={comment.comment_id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="space-y-2 rounded-2xl border bg-muted/10 p-4"
                    >
                      <Textarea
                        ref={textareaRef}
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        className="min-h-[80px]"
                      />
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditingId(null);
                            setEditDraft("");
                          }}
                        >
                          取消
                        </Button>
                        <Button
                          size="sm"
                          disabled={!editDraft.trim() || update.isPending}
                          onClick={() =>
                            update.mutate({ commentId: comment.comment_id, content: editDraft.trim() })
                          }
                        >
                          保存
                        </Button>
                      </div>
                    </motion.div>
                  ) : (
                    <CommentItem
                      key={comment.comment_id}
                      comment={comment}
                      currentUserId={currentUserId}
                      onEdit={(c) => {
                        setEditingId(c.comment_id);
                        setEditDraft(c.content);
                        setTimeout(() => textareaRef.current?.focus(), 0);
                      }}
                      onDelete={(id) => remove.mutate(id)}
                    />
                  )
                )
              )}
            </AnimatePresence>
          </div>
        )}

        <div className="space-y-2">
          <Textarea
            placeholder="写下评论，使用 @用户名 提及同事..."
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="min-h-[80px]"
          />
          <div className="flex justify-end">
            <Button
              disabled={!draft.trim() || create.isPending}
              onClick={() => create.mutate()}
            >
              <Send className="mr-2 h-4 w-4" />
              发表评论
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
