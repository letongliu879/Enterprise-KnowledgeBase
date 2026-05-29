"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Database,
  Plus,
  AlertCircle,
} from "lucide-react";
import { adminApi } from "@/lib/api/client";
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
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EmptyState } from "@/components/empty-state";
import { BackendGap } from "@/components/backend-gap";
import { useAppStore } from "@/lib/store";
import { isApiError, isBackendGap } from "@/lib/api/errors";
import { toast } from "sonner";

export default function CollectionsPage() {
  const { setCurrentCollectionId } = useAppStore();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ["admin-me"],
    queryFn: () => adminApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";

  const [form, setForm] = useState({
    collection_id: "",
    tenant_id: userTenantId,
    name: "",
    description: "",
    lifecycle_state: "active" as const,
  });

  // Keep tenant_id in sync with auth context once me resolves
  useEffect(() => {
    if (me?.tenant_id) {
      setForm((f) => ({ ...f, tenant_id: me.tenant_id }));
    }
  }, [me?.tenant_id]);
  const [gap, setGap] = useState<{ feature: string; endpoint: string } | null>(
    null
  );

  const {
    data: collectionResponse,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["collections", userTenantId],
    queryFn: () => adminApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });
  const collections = collectionResponse?.items ?? [];

  const createCollection = useMutation({
    mutationFn: adminApi.createCollection,
    onSuccess: () => {
      toast.success("集合已创建");
      setCreateOpen(false);
      queryClient.invalidateQueries({ queryKey: ["collections"] });
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">知识库集合</h1>
          <p className="text-sm text-muted-foreground mt-1">
            管理知识库集合。上传必须归属到某个集合。
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          新建集合
        </Button>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {isApiError(error) ? error.message : "加载集合失败"}
          </AlertDescription>
        </Alert>
      )}

      {gap && <BackendGap feature={gap.feature} endpoint={gap.endpoint} />}

      {collections.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((c, i) => (
            <motion.div
              key={c.collection_id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Card className="hover:border-primary/50 transition-colors cursor-pointer">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{c.name}</CardTitle>
                    <Badge
                      variant={
                        c.lifecycle_state === "active" ? "default" : "secondary"
                      }
                    >
                      {c.lifecycle_state}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs">
                    {c.collection_id}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {c.description || "无描述"}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>租户: {c.tenant_id}</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full mt-2"
                    onClick={() => {
                      setCurrentCollectionId(c.collection_id);
                      toast.success(`已选择集合: ${c.name}`);
                    }}
                  >
                    选择用于上传
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Database}
          title="暂无集合"
          description="创建第一个集合以开始上传文档。"
          action={
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              创建集合
            </Button>
          }
        />
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>创建集合</DialogTitle>
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
              className="w-full"
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
    </div>
  );
}
