"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Database, Plus, AlertCircle, FolderOpen, Check } from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
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
import { BackendGap } from "@/components/backend-gap";
import { useAppStore } from "@/lib/store";
import { isApiError, isBackendGap } from "@/lib/api/errors";
import { toast } from "sonner";
import { staggerContainer, staggerItem } from "@/lib/animations";

export default function CollectionsPage() {
  const { setCurrentCollectionId } = useAppStore();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";

  const [form, setForm] = useState({
    collection_id: "",
    tenant_id: userTenantId,
    name: "",
    description: "",
    lifecycle_state: "active" as const,
  });

  useEffect(() => {
    if (me?.tenant_id) {
      setForm((f) => ({ ...f, tenant_id: me.tenant_id }));
    }
  }, [me?.tenant_id]);

  const [gap, setGap] = useState<{ feature: string; endpoint: string } | null>(
    null
  );

  const { data: collectionResponse, isLoading, error } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });
  const collections = collectionResponse?.items ?? [];

  const createCollection = useMutation({
    mutationFn: workbenchApi.createCollection,
    onSuccess: () => {
      toast.success("集合已创建");
      setCreateOpen(false);
      queryClient.invalidateQueries({ queryKey: ["workbench-collections"] });
      setForm({
        collection_id: "",
        tenant_id: me?.tenant_id ?? "",
        name: "",
        description: "",
        lifecycle_state: "active",
      });
    },
    onError: (err) => {
      if (isBackendGap(err)) {
        setGap({ feature: "创建集合", endpoint: err.endpoint });
      } else {
        toast.error(isApiError(err) ? err.message : "创建集合失败");
      }
    },
  });

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
          <h1 className="text-2xl font-semibold tracking-tight">知识库集合</h1>
          <p className="text-sm text-muted-foreground mt-1">
            管理知识库集合。上传必须归属到某个集合。
          </p>
        </div>
        <Button
          onClick={() => setCreateOpen(true)}
          className="shadow-glow"
        >
          <Plus className="h-4 w-4 mr-2" />
          新建集合
        </Button>
      </motion.div>

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-xl" />
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
            {isApiError(error) ? error.message : "加载集合失败"}
          </AlertDescription>
        </Alert>
      )}

      {gap && <BackendGap feature={gap.feature} endpoint={gap.endpoint} />}

      {/* Collection Grid */}
      {collections.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((c, i) => (
            <motion.div
              key={c.collection_id}
              variants={staggerItem}
              initial="hidden"
              animate="visible"
              custom={i}
            >
              <Card
                interactive
                className="relative overflow-hidden group"
              >
                {/* Hover gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

                <CardHeader className="pb-3 relative">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                        <FolderOpen className="h-4 w-4 text-primary" />
                      </div>
                      <CardTitle className="text-base">{c.name}</CardTitle>
                    </div>
                    <Badge
                      variant={
                        c.lifecycle_state === "active"
                          ? "success"
                          : "secondary"
                      }
                      className="text-[10px] h-5"
                    >
                      {c.lifecycle_state}
                    </Badge>
                  </div>
                  <CardDescription className="text-[10px] text-muted-foreground/50 mt-1.5 font-mono">
                    {c.collection_id}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 relative">
                  <p className="text-sm text-muted-foreground/70 line-clamp-2 min-h-[40px]">
                    {c.description || "无描述"}
                  </p>
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground/40">
                    <span>租户: {c.tenant_id}</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full mt-2 glass border-white/10 hover:border-primary/30 hover:bg-primary/5 transition-all"
                    onClick={() => {
                      setCurrentCollectionId(c.collection_id);
                      toast.success(`已选择集合: ${c.name}`);
                    }}
                  >
                    <Check className="h-3.5 w-3.5 mr-1.5" />
                    选择用于上传
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      ) : (
        !isLoading &&
        !error && (
          <EmptyState
            icon={Database}
            title="暂无集合"
            description="创建第一个集合以开始上传文档。"
            action={
              <Button
                onClick={() => setCreateOpen(true)}
                className="shadow-glow"
              >
                <Plus className="h-4 w-4 mr-2" />
                创建集合
              </Button>
            }
          />
        )
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="glass-strong rounded-2xl border-white/10 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg">创建集合</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="coll-id">集合 ID</Label>
              <Input
                id="coll-id"
                value={form.collection_id}
                onChange={(e) =>
                  setForm((f) => ({ ...f, collection_id: e.target.value }))
                }
                placeholder="col_my_docs"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="coll-name">名称</Label>
              <Input
                id="coll-name"
                value={form.name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
                placeholder="我的文档"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="coll-desc">描述</Label>
              <Input
                id="coll-desc"
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="可选描述"
              />
            </div>
            <Button
              className="w-full shadow-glow"
              disabled={
                meLoading ||
                createCollection.isPending ||
                !form.collection_id ||
                !form.name ||
                !form.tenant_id
              }
              onClick={() => createCollection.mutate(form)}
            >
              {createCollection.isPending ? "创建中..." : "创建"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
