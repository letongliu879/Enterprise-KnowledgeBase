"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Plus,
  AlertCircle,
  Settings,
  Pencil,
  Trash2,
  Copy,
  Rocket,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import type { RetrievalProfileDetail } from "@/lib/api/types";
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

interface ProfileFormData {
  name: string;
  description: string;
  rerank_model: string;
  top_k: string;
  similarity_threshold: string;
  token_budget_limit: string;
}

function emptyForm(): ProfileFormData {
  return {
    name: "",
    description: "",
    rerank_model: "",
    top_k: "",
    similarity_threshold: "",
    token_budget_limit: "",
  };
}

function detailToForm(detail: RetrievalProfileDetail): ProfileFormData {
  return {
    name: detail.name ?? "",
    description: detail.description ?? "",
    rerank_model: detail.config?.rerank_model ?? "",
    top_k: detail.config?.top_k != null ? String(detail.config.top_k) : "",
    similarity_threshold:
      detail.config?.similarity_threshold != null
        ? String(detail.config.similarity_threshold)
        : "",
    token_budget_limit:
      detail.config?.token_budget_limit != null
        ? String(detail.config.token_budget_limit)
        : "",
  };
}

function buildConfigPayload(form: ProfileFormData): Record<string, unknown> {
  const config: Record<string, unknown> = {};
  if (form.rerank_model) config.rerank_model = form.rerank_model;
  if (form.top_k) config.top_k = Number(form.top_k);
  if (form.similarity_threshold)
    config.similarity_threshold = Number(form.similarity_threshold);
  if (form.token_budget_limit)
    config.token_budget_limit = Number(form.token_budget_limit);
  return config;
}

function buildCreatePayload(form: ProfileFormData) {
  return {
    name: form.name,
    description: form.description || undefined,
    config: buildConfigPayload(form),
  };
}

function buildUpdatePayload(form: ProfileFormData) {
  const payload: Record<string, unknown> = {};
  if (form.name) payload.name = form.name;
  if (form.description) payload.description = form.description;
  const config = buildConfigPayload(form);
  if (Object.keys(config).length > 0) payload.config = config;
  return payload;
}

export function RetrievalProfilesPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [form, setForm] = useState<ProfileFormData>(emptyForm());

  const {
    data: profileResponse,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workbench-retrieval-profiles"],
    queryFn: () => workbenchApi.listRetrievalProfiles(),
  });
  const profiles = profileResponse?.items ?? [];

  const invalidateList = () => {
    queryClient.invalidateQueries({
      queryKey: ["workbench-retrieval-profiles"],
    });
  };

  const createMutation = useMutation({
    mutationFn: (payload: Parameters<typeof workbenchApi.createRetrievalProfile>[0]) => workbenchApi.createRetrievalProfile(payload),
    onSuccess: () => {
      toast.success("配置已创建");
      setCreateOpen(false);
      setForm(emptyForm());
      invalidateList();
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "创建配置失败");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: Parameters<typeof workbenchApi.updateRetrievalProfile>[1];
    }) => workbenchApi.updateRetrievalProfile(id, payload),
    onSuccess: () => {
      toast.success("配置已更新");
      setEditOpen(false);
      setEditingId(null);
      setForm(emptyForm());
      invalidateList();
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "更新配置失败");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => workbenchApi.deleteRetrievalProfile(id),
    onSuccess: () => {
      toast.success("配置已删除");
      setDeleteOpen(false);
      setDeletingId(null);
      invalidateList();
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "删除配置失败");
    },
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => workbenchApi.publishRetrievalProfile(id),
    onSuccess: () => {
      toast.success("配置已发布");
      invalidateList();
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "发布配置失败");
    },
  });

  const cloneMutation = useMutation({
    mutationFn: (id: string) => workbenchApi.cloneRetrievalProfile(id),
    onSuccess: () => {
      toast.success("配置已克隆");
      invalidateList();
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : "克隆配置失败");
    },
  });

  const openCreate = () => {
    setForm(emptyForm());
    setCreateOpen(true);
  };

  const openEdit = async (profile: RetrievalProfileDetail) => {
    setEditingId(profile.retrieval_profile_id);
    setForm(detailToForm(profile));
    setEditOpen(true);
  };

  const openDelete = (profile: RetrievalProfileDetail) => {
    setDeletingId(profile.retrieval_profile_id);
    setDeleteOpen(true);
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

  const handleDeleteConfirm = () => {
    if (!deletingId) return;
    deleteMutation.mutate(deletingId);
  };

  const isCreateSubmitting = createMutation.isPending;
  const isEditSubmitting = updateMutation.isPending;
  const isDeleteSubmitting = deleteMutation.isPending;

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
            检索配置管理
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            管理检索配置，控制检索行为和参数。
          </p>
        </div>
        <Button onClick={openCreate} className="shadow-glow">
          <Plus className="h-4 w-4 mr-2" />
          新建配置
        </Button>
      </motion.div>

      {/* Loading */}
      {isLoading && (
        <div data-testid="profile-skeleton" className="space-y-4">
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
            {isApiError(error) ? error.message : "加载配置失败"}
          </AlertDescription>
        </Alert>
      )}

      {/* Profile List */}
      {profiles.length > 0 ? (
        <div className="space-y-4">
          {profiles.map((profile) => (
            <motion.div
              key={profile.retrieval_profile_id}
              variants={staggerItem}
              initial="hidden"
              animate="visible"
            >
              <Card className="glass relative overflow-hidden group">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                        <Settings className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <CardTitle className="text-base">
                          {profile.name}
                        </CardTitle>
                      </div>
                    </div>
                    <CardAction>
                      <Badge
                        variant={
                          profile.state === "published"
                            ? "success"
                            : "secondary"
                        }
                        className="text-[10px] h-5"
                      >
                        {profile.state}
                      </Badge>
                    </CardAction>
                  </div>
                  <CardDescription className="text-xs text-muted-foreground/50 mt-1 font-mono">
                    {profile.retrieval_profile_id}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-muted-foreground/70 line-clamp-2 min-h-[20px]">
                    {profile.description || "无描述"}
                  </p>
                  <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground/50">
                    {profile.config?.rerank_model && (
                      <span>rerank: {String(profile.config.rerank_model)}</span>
                    )}
                    {profile.config?.top_k != null && (
                      <span>top_k: {String(profile.config.top_k)}</span>
                    )}
                    {profile.config?.similarity_threshold != null && (
                      <span>
                        threshold: {String(profile.config.similarity_threshold)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => openEdit(profile as RetrievalProfileDetail)}
                    >
                      <Pencil className="h-3 w-3 mr-1" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() =>
                        openDelete(profile as RetrievalProfileDetail)
                      }
                    >
                      <Trash2 className="h-3 w-3 mr-1" />
                      删除
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() =>
                        cloneMutation.mutate(
                          (profile as RetrievalProfileDetail).retrieval_profile_id
                        )
                      }
                      disabled={cloneMutation.isPending}
                    >
                      <Copy className="h-3 w-3 mr-1" />
                      克隆
                    </Button>
                    {profile.state === "draft" && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() =>
                          publishMutation.mutate(
                            (profile as RetrievalProfileDetail).retrieval_profile_id
                          )
                        }
                        disabled={publishMutation.isPending}
                      >
                        <Rocket className="h-3 w-3 mr-1" />
                        发布
                      </Button>
                    )}
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
            icon={Settings}
            title="暂无配置"
            description="创建第一个检索配置以开始使用。"
            action={
              <Button onClick={openCreate} className="shadow-glow">
                <Plus className="h-4 w-4 mr-2" />
                新建配置
              </Button>
            }
          />
        )
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent
          data-testid="create-profile-dialog"
          className="glass-strong rounded-2xl border-white/10 max-w-md"
        >
          <DialogHeader>
            <DialogTitle className="text-lg">新建配置</DialogTitle>
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
                placeholder="配置名称"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-desc">描述</Label>
              <Input
                id="create-desc"
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="可选描述"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-rerank">rerank_model</Label>
              <Input
                id="create-rerank"
                value={form.rerank_model}
                onChange={(e) =>
                  setForm((f) => ({ ...f, rerank_model: e.target.value }))
                }
                placeholder="default"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-topk">top_k</Label>
              <Input
                id="create-topk"
                type="number"
                value={form.top_k}
                onChange={(e) =>
                  setForm((f) => ({ ...f, top_k: e.target.value }))
                }
                placeholder="10"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-threshold">similarity_threshold</Label>
              <Input
                id="create-threshold"
                type="number"
                step="0.01"
                value={form.similarity_threshold}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    similarity_threshold: e.target.value,
                  }))
                }
                placeholder="0.75"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-budget">token_budget_limit</Label>
              <Input
                id="create-budget"
                type="number"
                value={form.token_budget_limit}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    token_budget_limit: e.target.value,
                  }))
                }
                placeholder="4096"
              />
            </div>
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
          data-testid="edit-profile-dialog"
          className="glass-strong rounded-2xl border-white/10 max-w-md"
        >
          <DialogHeader>
            <DialogTitle className="text-lg">编辑配置</DialogTitle>
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
                placeholder="配置名称"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-desc">描述</Label>
              <Input
                id="edit-desc"
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="可选描述"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-rerank">rerank_model</Label>
              <Input
                id="edit-rerank"
                value={form.rerank_model}
                onChange={(e) =>
                  setForm((f) => ({ ...f, rerank_model: e.target.value }))
                }
                placeholder="default"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-topk">top_k</Label>
              <Input
                id="edit-topk"
                type="number"
                value={form.top_k}
                onChange={(e) =>
                  setForm((f) => ({ ...f, top_k: e.target.value }))
                }
                placeholder="10"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-threshold">similarity_threshold</Label>
              <Input
                id="edit-threshold"
                type="number"
                step="0.01"
                value={form.similarity_threshold}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    similarity_threshold: e.target.value,
                  }))
                }
                placeholder="0.75"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-budget">token_budget_limit</Label>
              <Input
                id="edit-budget"
                type="number"
                value={form.token_budget_limit}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    token_budget_limit: e.target.value,
                  }))
                }
                placeholder="4096"
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

      {/* Delete Confirm Dialog */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent
          data-testid="delete-confirm-dialog"
          className="glass-strong rounded-2xl border-white/10 max-w-sm"
        >
          <DialogHeader>
            <DialogTitle className="text-lg">确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground py-2">
            确定要删除此检索配置吗？此操作不可撤销。
          </p>
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(false)}
              disabled={isDeleteSubmitting}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={isDeleteSubmitting}
              onClick={handleDeleteConfirm}
            >
              {isDeleteSubmitting ? "删除中..." : "删除"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
