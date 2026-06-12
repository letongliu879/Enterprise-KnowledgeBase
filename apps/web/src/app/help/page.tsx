"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Search,
  Keyboard,
  HelpCircle,
  MessageCircleQuestion,
  BookOpen,
  Sparkles,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { staggerContainer, staggerItem } from "@/lib/animations";
import Link from "next/link";

const shortcuts = [
  { keys: ["⌘", "K"], action: "全局搜索 / Command Palette" },
  { keys: ["/"], action: "聚焦当前页面搜索框" },
  { keys: ["?"], action: "打开帮助中心" },
  { keys: ["Esc"], action: "关闭弹窗 / 退出浮层" },
];

const faqs = [
  {
    q: "如何上传文档到知识库？",
    a: "进入「批量入库」页面，拖拽或点击选择文件（支持 PDF、DOCX、PPTX、XLSX、CSV），选择目标集合后即可开始上传。",
    tags: ["上传", "入库"],
  },
  {
    q: "复核工单的状态有哪些？",
    a: "工单状态包括：待复核、已批准、已拒绝、已退回。Agent 审核完成后，人工审核员可在复核详情页做出最终决策。",
    tags: ["复核", "工单"],
  },
  {
    q: "什么是检索配置（Retrieval Profile）？",
    a: "检索配置定义了重排序模型、TopK、相似度阈值、Token 预算等参数。可在「检索验证」页面选择或管理配置。",
    tags: ["检索", "配置"],
  },
  {
    q: "删除的文档还能恢复吗？",
    a: "可以。删除的文档会进入「回收站」保留 30 天，期间可随时恢复；超过 30 天后将自动永久清理。",
    tags: ["回收站", "删除"],
  },
  {
    q: "如何配置认证信息？",
    a: "进入「设置」页面，填写演示 JWT 令牌和 API 密钥，并配置内部或外部权限范围。",
    tags: ["设置", "认证"],
  },
];

export default function HelpPage() {
  const [query, setQuery] = useState("");
  const [, setHasCompletedOnboarding] = useLocalStorage("ekb-onboarding-completed", false);

  const filteredFaqs = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return faqs;
    return faqs.filter(
      (item) =>
        item.q.toLowerCase().includes(q) ||
        item.a.toLowerCase().includes(q) ||
        item.tags.some((t) => t.toLowerCase().includes(q))
    );
  }, [query]);

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border bg-card/92 p-5 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">帮助中心</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              常见问题、快捷键、功能导航与使用引导
            </p>
          </div>
          <Button variant="outline" onClick={() => setHasCompletedOnboarding(false)}>
            <Sparkles className="mr-2 h-4 w-4" />
            重新播放引导
          </Button>
        </div>
      </section>

      <div className="relative max-w-xl">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="搜索常见问题、功能..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="grid gap-4 md:grid-cols-2"
      >
        <motion.div variants={staggerItem}>
          <Link href="/upload">
            <Card className="h-full rounded-2xl transition-shadow hover:shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <BookOpen className="h-4 w-4 text-primary" />
                  快速开始
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                了解如何上传文档、创建集合、完成复核和验证检索结果。
              </CardContent>
            </Card>
          </Link>
        </motion.div>

        <motion.div variants={staggerItem}>
          <Link href="/review">
            <Card className="h-full rounded-2xl transition-shadow hover:shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <MessageCircleQuestion className="h-4 w-4 text-primary" />
                  复核指南
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                学习如何查看 Agent Findings、编辑 chunk、提交决策和处理评论。
              </CardContent>
            </Card>
          </Link>
        </motion.div>

        <motion.div variants={staggerItem}>
          <Card className="h-full rounded-2xl">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Keyboard className="h-4 w-4 text-primary" />
                快捷键
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {shortcuts.map((shortcut) => (
                <div key={shortcut.action} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{shortcut.action}</span>
                  <div className="flex gap-1">
                    {shortcut.keys.map((k) => (
                      <kbd
                        key={k}
                        className="rounded border border-white/10 bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px]"
                      >
                        {k}
                      </kbd>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={staggerItem}>
          <Card className="h-full rounded-2xl">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <HelpCircle className="h-4 w-4 text-primary" />
                需要更多帮助？
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              如遇到 Backend Gap（501 未实现）提示，说明该功能后端尚未就绪，请联系开发团队。
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>

      <Card className="rounded-2xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">常见问题</CardTitle>
          <CardDescription>
            {filteredFaqs.length === 0 ? "没有匹配的问题" : `共 ${filteredFaqs.length} 条常见问题`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {filteredFaqs.map((item, index) => (
            <motion.div
              key={item.q}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className="rounded-2xl border bg-muted/10 p-4"
            >
              <p className="font-medium">{item.q}</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.a}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {item.tags.map((tag) => (
                  <Badge key={tag} variant="outline" className="text-[10px]">{tag}</Badge>
                ))}
              </div>
            </motion.div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
