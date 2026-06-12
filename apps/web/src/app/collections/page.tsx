"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Database,
  Plus,
  AlertCircle,
  FolderOpen,
  Check,
  Search,
  ArrowRight,
  Pencil,
} from "lucide-react";
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
import { SortDropdown } from "@/components/sort-dropdown";
import type { AdminCollection } from "@/lib/api/types";

const SORT_OPTIONS = [
  { value: "name", label: "名称" },
  { value: "created_at", label: "创建时间" },
];

export default function CollectionsPage() {
  const { setCurrentCollectionId } = useAppStore();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingCollection, setEditingCollection] = useState<AdminCollection | null>(null);
  const [editForm, setEditForm] = useState({ name: "", description: "" });
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";

  const [form, setForm] = useState({
    collection_id: "",
    name: "",
    description: "",
    lifecycle_state: "active" as const,
  });

  const [gap, setGap] = useState<{ feature: string; endpoint: string } | null>(
    null
  );

  const { data: collectionResponse, isLoading, error } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });
  const items = useMemo(() => collectionResponse?.items ?? [], [collectionResponse]);

  const normalizedSearch = searchQuery.trim().toLowerCase();

  const filteredCollections = useMemo(() => {
    let result = items;
    if (normalizedSearch) {
      result = result.filter((c) =>
        c.name.toLowerCase().includes(normalizedSearch)
      );
    }
    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortBy === "name") {
        cmp = a.name.localeCompare(b.name, "zh-CN");
      } else if (sortBy === "created_at") {
        cmp =
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return result;
  }, [items, normalizedSearch, sortBy, sortDir]);

  const createCollection = useMutation({
    mutationFn: workbenchApi.createCollection,
    onSuccess: () => {
      toast.success("集合已创建");
      setCreateOpen(false);
      queryClient.invalidateQueries({ queryKey: ["workbench-collections"] });
      setForm({
        collection_id: "",
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

  const updateCollection = useMutation({
    mutationFn: (payload: {
      collection_id: string;
      name?: string;
      description?: string;
    }) =>
      workbenchApi.updateCollection(payload.collection_id, {
        name: payload.name,
        description: payload.description,
      }),
    onSuccess: () => {
      toast.success("集合已更新");
      setEditOpen(false);
      setEditingCollection(null);
      queryClient.invalidateQueries({ queryKey: ["workbench-collections"] });
    },
    onError: (err) => {
      if (isBackendGap(err)) {
        setGap({ feature: "更新集合", endpoint: err.endpoint });
      } else {
        toast.error(isApiError(err) ? err.message : "更新集合失败");
      }
    },
  });

  function openEditDialog(collection: AdminCollection) {
    setEditingCollection(collection);
    setEditForm({
      name: collection.name,
      description: collection.description || "",
    });
    setEditOpen(true);
  }

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

      {/* Search & Sort */}
      <motion.div variants={staggerItem} className="flex items-center gap-3 flex-wrap">
        <div className="glass flex items-center gap-2 rounded-full px-1 py-1 flex-1 max-w-sm">
          <Search className="ml-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="搜索集合名称..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-7 border-0 bg-transparent px-0 text-sm focus-visible:ring-0 focus-visible:shadow-none"
          />
        </div>
        <SortDropdown
          options={SORT_OPTIONS}
          value={sortBy}
          direction={sortDir}
          onChange={(value, direction) => {
            setSortBy(value);
            setSortDir(direction);
          }}
        />
        <span className="text-xs text-muted-foreground/50 ml-auto">
          {filteredCollections.length} 个集合
        </span>
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
      {filteredCollections.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCollections.map((c, i) => (
            <motion.div
              key={c.collection_id}
              variants={staggerItem}
              initial="hidden"
              animate="visible"
              custom={i}
            >
              <Link href={`/collections/${c.collection_id}`} className="block">
                <Card
                  interactive
                  className="relative overflow-hidden group h-full"
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
                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 glass border-white/10 hover:border-primary/30 hover:bg-primary/5 transition-all"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setCurrentCollectionId(c.collection_id);
                          toast.success(`已选择集合: ${c.name}`);
                        }}
                      >
                        <Check className="h-3.5 w-3.5 mr-1.5" />
                        选择用于上传
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          openEditDialog(c);
                        }}
                      >
                        <Pencil className="h-4 w-4 text-muted-foreground/50" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                      >
                        <ArrowRight className="h-4 w-4 text-muted-foreground/50" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      ) : (
        !isLoading &&
        !error && (
          <EmptyState
            icon={Database}
            title={searchQuery ? "无匹配集合" : "暂无集合"}
            description={
              searchQuery
                ? "没有符合搜索条件的集合，尝试其他关键词。"
                : "创建第一个集合以开始上传文档。"
            }
            action={
              !searchQuery ? (
                <Button
                  onClick={() => setCreateOpen(true)}
                  className="shadow-glow"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  创建集合
                </Button>
              ) : undefined
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
                !userTenantId
              }
              onClick={() =>
                createCollection.mutate({
                  ...form,
                  tenant_id: userTenantId,
                })
              }
            >
              {createCollection.isPending ? "创建中..." : "创建"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="glass-strong rounded-2xl border-white/10 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg">编辑集合</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="edit-coll-name">名称</Label>
              <Input
                id="edit-coll-name"
                value={editForm.name}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, name: e.target.value }))
                }
                placeholder="集合名称"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-coll-desc">描述</Label>
              <Input
                id="edit-coll-desc"
                value={editForm.description}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="可选描述"
              />
            </div>
            <Button
              className="w-full shadow-glow"
              disabled={
                updateCollection.isPending ||
                !editForm.name ||
                !editingCollection
              }
              onClick={() => {
                if (!editingCollection) return;
                updateCollection.mutate({
                  collection_id: editingCollection.collection_id,
                  name: editForm.name,
                  description: editForm.description,
                });
              }}
            >
              {updateCollection.isPending ? "保存中..." : "保存"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
