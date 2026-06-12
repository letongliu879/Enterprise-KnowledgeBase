"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Database,
  FileText,
  Clock,
  HardDrive,
  Edit,
  Trash2,
  Shield,
  LogIn,
  Upload,
  Download,
  LayoutTemplate,
  Tag,
  FolderOpen,
  AlertCircle,
  Search,
  CheckCircle2,
  Clock3,
  Archive,
} from "lucide-react";
import { workbenchApi } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { isApiError } from "@/lib/api/errors";
import { staggerContainer, staggerItem, fadeInUp } from "@/lib/animations";
import { CollectionPermissionsDialog } from "@/features/collections/collection-permissions-dialog";

function formatRelativeTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffHours < 24) return `${diffHours} 小时前`;
  if (diffDays < 7) return `${diffDays} 天前`;
  return date.toLocaleDateString("zh-CN");
}

function getDocIcon(filename?: string | null) {
  if (!filename) return { icon: FileText, color: "text-muted-foreground", bg: "bg-white/[0.03]" };
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return { icon: FileText, color: "text-red-400", bg: "bg-red-500/10" };
  if (ext === "doc" || ext === "docx") return { icon: FileText, color: "text-blue-400", bg: "bg-blue-500/10" };
  if (ext === "ppt" || ext === "pptx") return { icon: FileText, color: "text-orange-400", bg: "bg-orange-500/10" };
  if (ext === "xls" || ext === "xlsx" || ext === "csv") return { icon: FileText, color: "text-emerald-400", bg: "bg-emerald-500/10" };
  return { icon: FileText, color: "text-muted-foreground", bg: "bg-white/[0.03]" };
}

function ActionButton({
  icon: Icon,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger>
        <Button variant="outline" size="sm" disabled className="h-8 gap-1.5 text-xs opacity-60">
          <Icon className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{label}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent>即将推出</TooltipContent>
    </Tooltip>
  );
}

export default function CollectionDetailPage() {
  const params = useParams();
  const collectionId = params.collectionId as string;
  const [searchQuery, setSearchQuery] = useState("");
  const [permOpen, setPermOpen] = useState(false);

  const { data: me } = useQuery({
    queryKey: ["workbench-me"],
    queryFn: () => workbenchApi.me(),
  });
  const userTenantId = me?.tenant_id ?? "";

  const {
    data: collectionResponse,
    isLoading: collectionsLoading,
    error: collectionsError,
  } = useQuery({
    queryKey: ["workbench-collections", userTenantId],
    queryFn: () => workbenchApi.listCollections(userTenantId),
    enabled: !!userTenantId,
  });

  const collection = useMemo(() => {
    return collectionResponse?.items.find((c) => c.collection_id === collectionId) ?? null;
  }, [collectionResponse, collectionId]);

  const {
    data: documentsResponse,
    isLoading: documentsLoading,
    error: documentsError,
  } = useQuery({
    queryKey: ["workbench-documents", collectionId],
    queryFn: () =>
      workbenchApi.listDocuments({
        collection_id: collectionId,
        limit: 50,
      }),
    enabled: !!collectionId,
  });

  const docItems = useMemo(() => documentsResponse?.items ?? [], [documentsResponse]);
  const normalizedSearch = searchQuery.trim().toLowerCase();

  const filteredDocuments = useMemo(() => {
    if (!normalizedSearch) return docItems;
    return docItems.filter(
      (doc) =>
        String(doc.filename || "").toLowerCase().includes(normalizedSearch) ||
        String(doc.doc_id || "").toLowerCase().includes(normalizedSearch)
    );
  }, [docItems, normalizedSearch]);

  const stats = useMemo(() => {
    const docCount = docItems.length;
    const totalChunks = docItems.reduce((sum, d) => sum + (d.chunk_count || 0), 0);
    const totalPages = docItems.reduce((sum, d) => sum + (d.page_count || 0), 0);
    const lastUpload = docItems
      .map((d) => d.created_at)
      .filter((v): v is string => Boolean(v))
      .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0];
    return { docCount, totalChunks, totalPages, lastUpload };
  }, [docItems]);

  const isLoading = collectionsLoading || documentsLoading;
  const error = collectionsError || documentsError;

  return (
    <TooltipProvider>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Back navigation */}
        <motion.div variants={staggerItem}>
          <Link
            href="/collections"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            返回集合列表
          </Link>
        </motion.div>

        {/* Header */}
        <motion.div variants={staggerItem} className="flex flex-col gap-4">
          {isLoading && !collection ? (
            <div className="space-y-3">
              <Skeleton className="h-8 w-64 rounded-lg" />
              <Skeleton className="h-4 w-96 rounded-lg" />
              <Skeleton className="h-4 w-48 rounded-lg" />
            </div>
          ) : collection ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10">
                  <FolderOpen className="h-5 w-5 text-primary" />
                </div>
                <h1 className="text-2xl font-semibold tracking-tight">{collection.name}</h1>
                <Badge
                  variant={collection.lifecycle_state === "active" ? "success" : "secondary"}
                  className="text-[10px] h-5"
                >
                  {collection.lifecycle_state}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground/70 max-w-2xl">
                {collection.description || "无描述"}
              </p>
              <code className="text-[11px] text-muted-foreground/50 font-mono bg-muted/30 px-2 py-1 rounded-md">
                {collection.collection_id}
              </code>
            </div>
          ) : (
            <div className="space-y-3">
              <h1 className="text-2xl font-semibold tracking-tight">集合未找到</h1>
              <p className="text-sm text-muted-foreground/70">
                无法找到 ID 为 <code className="font-mono">{collectionId}</code> 的集合
              </p>
            </div>
          )}
        </motion.div>

        {/* Error */}
        {error && (
          <motion.div variants={staggerItem}>
            <Alert variant="destructive" className="border-red-500/20 bg-red-500/5">
              <AlertCircle className="h-4 w-4 text-red-400" />
              <AlertDescription className="text-red-300">
                {isApiError(error) ? error.message : "加载数据失败"}
              </AlertDescription>
            </Alert>
          </motion.div>
        )}

        {/* Stats cards */}
        {collection && (
          <motion.div variants={staggerItem}>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="glass-card relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent pointer-events-none" />
                <CardContent className="p-4 relative">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                      <Database className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground/60">文档数量</p>
                      <p className="text-lg font-semibold">{stats.docCount}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-card relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent pointer-events-none" />
                <CardContent className="p-4 relative">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                      <HardDrive className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground/60">总块数 / 页数</p>
                      <p className="text-lg font-semibold">
                        {stats.totalChunks} / {stats.totalPages}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-card relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent pointer-events-none" />
                <CardContent className="p-4 relative">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                      <Clock className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground/60">最近上传</p>
                      <p className="text-lg font-semibold">
                        {stats.lastUpload ? formatRelativeTime(stats.lastUpload) : "-"}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-card relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent pointer-events-none" />
                <CardContent className="p-4 relative">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                      <FileText className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground/60">平均块/文档</p>
                      <p className="text-lg font-semibold">
                        {stats.docCount > 0 ? Math.round(stats.totalChunks / stats.docCount) : 0}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </motion.div>
        )}

        {/* Action buttons */}
        {collection && (
          <motion.div variants={staggerItem} className="flex flex-wrap items-center gap-2">
            <ActionButton icon={Edit} label="编辑集合" />
            <ActionButton icon={Trash2} label="删除集合" />
            <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs" onClick={() => setPermOpen(true)}>
              <Shield className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">权限</span>
            </Button>
            <ActionButton icon={LogIn} label="访问日志" />
            <ActionButton icon={Upload} label="导入" />
            <ActionButton icon={Download} label="导出" />
            <ActionButton icon={LayoutTemplate} label="模板" />
            <ActionButton icon={Tag} label="标签" />
          </motion.div>
        )}

        {/* Document list */}
        {collection && (
          <motion.div variants={staggerItem} className="space-y-4">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <h2 className="text-lg font-semibold tracking-tight">文档列表</h2>
              <div className="glass flex items-center gap-2 rounded-full px-1 py-1">
                <Search className="ml-2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="搜索文档名称或 ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-7 w-56 border-0 bg-transparent px-0 text-sm focus-visible:ring-0 focus-visible:shadow-none"
                />
              </div>
            </div>

            {documentsLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 rounded-xl" />
                ))}
              </div>
            ) : documentsError ? (
              <Alert variant="destructive" className="border-red-500/20 bg-red-500/5">
                <AlertCircle className="h-4 w-4 text-red-400" />
                <AlertDescription className="text-red-300">
                  {isApiError(documentsError) ? documentsError.message : "加载文档失败"}
                </AlertDescription>
              </Alert>
            ) : filteredDocuments.length > 0 ? (
              <Card className="glass-card overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-b border-white/5 hover:bg-transparent">
                      <TableHead className="w-[40px]"></TableHead>
                      <TableHead>文档名称</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>块数</TableHead>
                      <TableHead>页数</TableHead>
                      <TableHead>解析配置</TableHead>
                      <TableHead>更新时间</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDocuments.map((doc, index) => {
                      const iconConfig = getDocIcon(doc.filename);
                      const Icon = iconConfig.icon;
                      return (
                        <motion.tr
                          key={doc.doc_id}
                          variants={fadeInUp}
                          initial="hidden"
                          animate="visible"
                          transition={{ delay: index * 0.03 }}
                          className="border-b border-white/5 transition-colors hover:bg-muted/30"
                        >
                          <TableCell>
                            <div
                              className={`flex h-8 w-8 items-center justify-center rounded-lg ${iconConfig.bg}`}
                            >
                              <Icon className={`h-4 w-4 ${iconConfig.color}`} />
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-col">
                              <Link
                                href={`/documents/${doc.doc_id}`}
                                className="text-sm font-medium hover:underline truncate max-w-[240px]"
                              >
                                {doc.filename || doc.doc_id}
                              </Link>
                              <span className="text-[10px] text-muted-foreground/50 font-mono">
                                {doc.doc_id}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className="text-[10px] h-5 border-white/10"
                            >
                              {doc.document_state || "-"}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm">{doc.chunk_count}</TableCell>
                          <TableCell className="text-sm">{doc.page_count || 0}</TableCell>
                          <TableCell className="text-sm text-muted-foreground/70">
                            {doc.parser_profile_name || doc.parser_profile_id || "-"}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground/70">
                            {formatRelativeTime(doc.latest_updated_at || doc.updated_at)}
                          </TableCell>
                          <TableCell className="text-right">
                            <Link href={`/documents/${doc.doc_id}`}>
                              <Button variant="ghost" size="sm" className="h-7 text-xs">
                                查看
                              </Button>
                            </Link>
                          </TableCell>
                        </motion.tr>
                      );
                    })}
                  </TableBody>
                </Table>
              </Card>
            ) : (
              <EmptyState
                icon={Database}
                title="暂无文档"
                description={
                  searchQuery
                    ? "没有匹配搜索条件的文档"
                    : "该集合中还没有文档，前往上传页面添加文档。"
                }
                action={
                  !searchQuery ? (
                    <Link href="/upload">
                      <Button size="sm" className="shadow-glow">
                        <Upload className="h-4 w-4 mr-2" />
                        上传文档
                      </Button>
                    </Link>
                  ) : undefined
                }
              />
            )}
          </motion.div>
        )}
      </motion.div>

      <CollectionPermissionsDialog
        open={permOpen}
        onClose={() => setPermOpen(false)}
        collectionId={collectionId}
        tenantId={userTenantId}
      />
    </TooltipProvider>
  );
}
