"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Plus,
  AlertCircle,
  Key,
  Pencil,
  Ban,
  BarChart3,
  Copy,
  Check,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import type { ApiKeyItem, ApiKeyDetail, ApiKeyUsage } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardAction,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EmptyState } from "@/components/empty-state";
import { isApiError } from "@/lib/api/errors";
import { toast } from "sonner";
import { staggerContainer, staggerItem } from "@/lib/animations";

interface ApiKeyFormData {
  name: string;
  permissions: string[];
  collection_ids: string[];
  expires_at: string;
}

const ALL_PERMISSIONS = ["read", "search", "upload", "delete", "admin", "manage"];

function emptyForm(): ApiKeyFormData {
  return {
    name: "",
    permissions: [],
    collection_ids: [],
    expires_at: "",
  };
}

function detailToForm(detail: ApiKeyDetail): ApiKeyFormData {
  return {
    name: detail.name ?? "",
    permissions: detail.permissions ?? [],
    collection_ids: detail.collection_ids ?? [],
    expires_at: detail.expires_at ? detail.expires_at.slice(0, 10) : "",
  };
}

function buildCreatePayload(form: ApiKeyFormData) {
  return {
    name: form.name,
    permissions: form.permissions.length > 0 ? form.permissions : undefined,
    collection_ids: form.collection_ids.length > 0 ? form.collection_ids : undefined,
    expires_at: form.expires_at || null,
  };
}

function buildUpdatePayload(form: ApiKeyFormData) {
  const payload: Record<string, unknown> = {};
  if (form.name) payload.name = form.name;
  payload.permissions = form.permissions;
  payload.collection_ids = form.collection_ids;
  payload.expires_at = form.expires_at || null;
  return payload;
}

export function ApiKeysPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [usageOpen, setUsageOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [usageId, setUsageId] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [form, setForm] = useState<ApiKeyFormData>(emptyForm());
  const [copied, setCopied] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const {
    data: apiKeyResponse,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workbench-api-keys"],
    queryFn: () => workbenchApi.listApiKeys(),
  });
  const apiKeys = apiKeyResponse?.items ?? [];

  const { data: detailData } = useQuery({
    queryKey: ["workbench-api-key-detail", detailId],
    queryFn: () => workbenchApi.getApiKeyDetail(detailId!),
    enabled: !!detailId,
  });

  const { data: usageData } = useQuery({
    queryKey: ["workbench-api-key-usage", usageId],
    queryFn: () => workbenchApi.getApiKeyUsage(usageId!),
    enabled: !!usageId,
  });

  const invalidateList = () => {
    queryClient.invalidateQueries({
      queryKey: ["workbench-api-keys"],
    });
  };

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => workbenchApi.createApiKey(payload as any),
    onSuccess: (data) => {
      toast.success("密钥已创建");
      setCreatedKey(data.full_key ?? null);
      invalidateList();
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "创建密钥失败");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: Record<string, unknown>;
    }) => workbenchApi.updateApiKey(id, payload as any),
    onSuccess: () => {
      toast.success("密钥已更新");
      setEditOpen(false);
      setEditingId(null);
      setForm(emptyForm());
      invalidateList();
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "更新密钥失败");
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => workbenchApi.deleteApiKey(id),
    onSuccess: () => {
      toast.success("密钥已吊销");
      setRevokeOpen(false);
      setRevokingId(null);
      invalidateList();
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "吊销密钥失败");
    },
  });

  const openCreate = () => {
    setForm(emptyForm());
    setCreatedKey(null);
    setCreateOpen(true);
  };

  const openEdit = async (key: ApiKeyItem) => {
    setEditingId(key.api_key_id);
    setForm(detailToForm(key as ApiKeyDetail));
    setEditOpen(true);
  };

  const openRevoke = (key: ApiKeyItem) => {
    setRevokingId(key.api_key_id);
    setRevokeOpen(true);
  };

  const openUsage = (key: ApiKeyItem) => {
    setUsageId(key.api_key_id);
    setUsageOpen(true);
  };

  const openDetail = (key: ApiKeyItem) => {
    setDetailId(key.api_key_id);
    setDetailOpen(true);
  };

  const handleCreateSubmit = () => {
    createMutation.mutate(buildCreatePayload(form));
  };

  const handleEditSubmit = () => {
    if (!editingId) return;
    updateMutation.mutate({
      id: editingId,
      payload: buildUpdatePayload(form),
    });
  };

  const handleRevokeConfirm = () => {
    if (!revokingId) return;
    revokeMutation.mutate(revokingId);
  };

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  const togglePermission = (perm: string) => {
    setForm((f) => ({
      ...f,
      permissions: f.permissions.includes(perm)
        ? f.permissions.filter((p) => p !== perm)
        : [...f.permissions, perm],
    }));
  };

  const isCreateSubmitting = createMutation.isPending;
  const isEditSubmitting = updateMutation.isPending;
  const isRevokeSubmitting = revokeMutation.isPending;

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div
        variants={staggerItem}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            API 密钥管理
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            管理 API 密钥，控制访问权限与有效期。
          </p>
        </div>
        <Button onClick={openCreate} className="shadow-glow">
          <Plus className="h-4 w-4 mr-2" />
          创建密钥
        </Button>
      </motion.div>

      {/* Loading */}
      {isLoading && (
        <div data-testid="api-key-skeleton" className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <Alert
          variant="destructive"
          className="border-red-500/20 bg-red-500/5"
        >
          <AlertCircle className="h-4 w-4 text-red-400" />
          <AlertDescription className="text-red-300">
            {isApiError(error) ? error.message : "加载密钥失败"}
          </AlertDescription>
        </Alert>
      )}

      {/* API Key List */}
      {apiKeys.length > 0 ? (
        <div className="space-y-4">
          {apiKeys.map((key) => (
            <motion.div
              key={key.api_key_id}
              variants={staggerItem}
              initial="hidden"
              animate="visible"
            >
              <Card className="glass relative overflow-hidden group">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                        <Key className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <CardTitle
                          className="text-base cursor-pointer hover:underline"
                          onClick={() => openDetail(key)}
                        >
                          {key.name}
                        </CardTitle>
                      </div>
                    </div>
                    <CardAction>
                      <Badge
                        variant={
                          key.state === "active" ? "success" : "destructive"
                        }
                        className="text-[10px] h-5"
                      >
                        {key.state}
                      </Badge>
                    </CardAction>
                  </div>
                  <CardDescription className="text-xs text-muted-foreground/50 mt-1 font-mono">
                    {key.key_prefix}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {key.permissions.map((perm) => (
                      <Badge
                        key={perm}
                        variant="secondary"
                        className="text-[10px] h-5"
                      >
                        {perm}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground/50">
                    <span>
                      过期时间:{" "}
                      {key.expires_at
                        ? key.expires_at.slice(0, 10)
                        : "永不过期"}
                    </span>
                    <span>
                      最后使用:{" "}
                      {key.last_used_at
                        ? new Date(key.last_used_at).toLocaleDateString("zh-CN")
                        : "从未使用"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => openEdit(key)}
                    >
                      <Pencil className="h-3 w-3 mr-1" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => openRevoke(key)}
                    >
                      <Ban className="h-3 w-3 mr-1" />
                      吊销
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => openUsage(key)}
                    >
                      <BarChart3 className="h-3 w-3 mr-1" />
                      用量
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      ) : (
        !isLoading &&
        !error && (
          <EmptyState
            icon={Key}
            title="暂无密钥"
            description="创建第一个 API 密钥以开始使用。"
            action={
              <Button onClick={openCreate} className="shadow-glow">
                <Plus className="h-4 w-4 mr-2" />
                创建密钥
              </Button>
            }
          />
        )
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent
          data-testid="create-api-key-dialog"
          className="glass-strong rounded-2xl border-white/10 max-w-md"
        >
          <DialogHeader>
            <DialogTitle className="text-lg">创建密钥</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="create-name">名称</Label>
              <Input
                id="create-name"
                value={form.name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
                placeholder="密钥名称"
              />
            </div>
            <div className="space-y-2">
              <Label>权限</Label>
              <div className="flex flex-wrap gap-2">
                {ALL_PERMISSIONS.map((perm) => (
                  <label
                    key={perm}
                    className="flex items-center gap-1.5 text-sm cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={form.permissions.includes(perm)}
                      onChange={() => togglePermission(perm)}
                    />
                    <span>{perm}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-expires">过期日期</Label>
              <Input
                id="create-expires"
                type="date"
                value={form.expires_at}
                onChange={(e) =>
                  setForm((f) => ({ ...f, expires_at: e.target.value }))
                }
              />
            </div>
            {createdKey && (
              <div className="space-y-2">
                <Label>密钥值</Label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 bg-muted/50 rounded-lg px-3 py-2 text-xs font-mono break-all">
                    {createdKey}
                  </code>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleCopy(createdKey)}
                  >
                    {copied ? (
                      <Check className="h-3 w-3" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                  </Button>
                </div>
              </div>
            )}
            <Button
              className="w-full shadow-glow"
              disabled={isCreateSubmitting || !form.name}
              onClick={handleCreateSubmit}
            >
              {isCreateSubmitting ? "创建中..." : "创建"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent
          data-testid="edit-api-key-dialog"
          className="glass-strong rounded-2xl border-white/10 max-w-md"
        >
          <DialogHeader>
            <DialogTitle className="text-lg">编辑密钥</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="edit-name">名称</Label>
              <Input
                id="edit-name"
                value={form.name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
                placeholder="密钥名称"
              />
            </div>
            <div className="space-y-2">
              <Label>权限</Label>
              <div className="flex flex-wrap gap-2">
                {ALL_PERMISSIONS.map((perm) => (
                  <label
                    key={perm}
                    className="flex items-center gap-1.5 text-sm cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={form.permissions.includes(perm)}
                      onChange={() => togglePermission(perm)}
                    />
                    <span>{perm}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-expires">过期日期</Label>
              <Input
                id="edit-expires"
                type="date"
                value={form.expires_at}
                onChange={(e) =>
                  setForm((f) => ({ ...f, expires_at: e.target.value }))
                }
              />
            </div>
            <Button
              className="w-full shadow-glow"
              disabled={isEditSubmitting || !form.name}
              onClick={handleEditSubmit}
            >
              {isEditSubmitting ? "保存中..." : "保存"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Revoke Confirm Dialog */}
      <Dialog open={revokeOpen} onOpenChange={setRevokeOpen}>
        <DialogContent
          data-testid="revoke-confirm-dialog"
          className="glass-strong rounded-2xl border-white/10 max-w-sm"
        >
          <DialogHeader>
            <DialogTitle className="text-lg">确认吊销</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground py-2">
            确定要吊销此 API 密钥吗？此操作不可撤销。
          </p>
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={() => setRevokeOpen(false)}
              disabled={isRevokeSubmitting}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={isRevokeSubmitting}
              onClick={handleRevokeConfirm}
            >
              {isRevokeSubmitting ? "吊销中..." : "确认吊销"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Usage Stats Dialog */}
      <Dialog open={usageOpen} onOpenChange={setUsageOpen}>
        <DialogContent
          data-testid="api-key-usage-dialog"
          className="glass-strong rounded-2xl border-white/10 max-w-lg"
        >
          <DialogHeader>
            <DialogTitle className="text-lg">用量统计</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {usageData ? (
              <>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">总请求数</p>
                    <p className="text-lg font-semibold">
                      {usageData.total_requests}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">总 Token 数</p>
                    <p className="text-lg font-semibold">
                      {usageData.total_tokens}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">峰值 QPS</p>
                    <p className="text-lg font-semibold">
                      {usageData.qps_peak}
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">每日统计</p>
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                            日期
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">
                            请求数
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">
                            Token 数
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {usageData.daily_stats.map((stat) => (
                          <tr
                            key={stat.date}
                            className="border-t border-border/50"
                          >
                            <td className="px-3 py-2">{stat.date}</td>
                            <td className="px-3 py-2 text-right">
                              {stat.requests}
                            </td>
                            <td className="px-3 py-2 text-right">
                              {stat.tokens}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <Skeleton className="h-16 rounded-lg" />
                <Skeleton className="h-32 rounded-lg" />
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent
          data-testid="api-key-detail-dialog"
          className="glass-strong rounded-2xl border-white/10 max-w-md"
        >
          <DialogHeader>
            <DialogTitle className="text-lg">密钥详情</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {detailData ? (
              <>
                <div className="space-y-2">
                  <Label>名称</Label>
                  <p className="text-sm">{detailData.name}</p>
                </div>
                <div className="space-y-2">
                  <Label>前缀</Label>
                  <p className="text-sm font-mono">{detailData.key_prefix}</p>
                </div>
                <div className="space-y-2">
                  <Label>状态</Label>
                  <Badge
                    variant={
                      detailData.state === "active" ? "success" : "destructive"
                    }
                  >
                    {detailData.state}
                  </Badge>
                </div>
                <div className="space-y-2">
                  <Label>权限</Label>
                  <div className="flex flex-wrap gap-2">
                    {detailData.permissions.map((perm) => (
                      <Badge key={perm} variant="secondary">
                        {perm}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>过期时间</Label>
                  <p className="text-sm">
                    {detailData.expires_at
                      ? detailData.expires_at.slice(0, 10)
                      : "永不过期"}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>最后使用</Label>
                  <p className="text-sm">
                    {detailData.last_used_at
                      ? detailData.last_used_at.slice(0, 10)
                      : "从未使用"}
                  </p>
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <Skeleton className="h-8 rounded-lg" />
                <Skeleton className="h-8 rounded-lg" />
                <Skeleton className="h-8 rounded-lg" />
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
