"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { MessageSquare, Send, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/empty-state";

interface Annotation {
  id: string;
  author: string;
  content: string;
  createdAt: string;
}

interface DocumentAnnotationsProps {
  annotations: Annotation[];
  onAdd?: (content: string) => void;
}

function formatRelativeTime(isoString: string) {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins} 分钟前`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  return date.toLocaleDateString("zh-CN");
}

export function DocumentAnnotations({ annotations, onAdd }: DocumentAnnotationsProps) {
  const [input, setInput] = useState("");

  const handleSubmit = () => {
    if (!input.trim() || !onAdd) return;
    onAdd(input.trim());
    setInput("");
  };

  return (
    <div className="space-y-4">
      {annotations.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="暂无批注"
          description="还没有人对这篇文档添加批注。"
        />
      ) : (
        <div className="space-y-3">
          {annotations.map((a, i) => (
            <motion.div
              key={a.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="rounded-2xl border bg-muted/10 p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10">
                  <User className="h-3.5 w-3.5 text-primary" />
                </div>
                <span className="text-sm font-medium">{a.author}</span>
                <span className="text-xs text-muted-foreground ml-auto">{formatRelativeTime(a.createdAt)}</span>
              </div>
              <p className="text-sm leading-6">{a.content}</p>
            </motion.div>
          ))}
        </div>
      )}

      {onAdd && (
        <div className="flex gap-2">
          <Textarea
            placeholder="添加批注..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="min-h-20"
          />
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={!input.trim()}
            className="self-end"
          >
            <Send className="h-4 w-4 mr-1" /> 提交
          </Button>
        </div>
      )}
    </div>
  );
}
