"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Inbox, Search, Settings, X, ChevronRight, ChevronLeft, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLocalStorage } from "@/hooks/use-local-storage";

const steps = [
  {
    id: "upload",
    title: "批量入库",
    description: "拖拽或点击上传 PDF、Word、PPT、Excel 文件，系统会自动解析并生成复核工单。",
    icon: Upload,
    target: "/upload",
  },
  {
    id: "review",
    title: "人工复核",
    description: "在复核队列中查看 Agent 审核结果，做出 Approve / Reject / Return 决策。",
    icon: Inbox,
    target: "/review",
  },
  {
    id: "retrieval",
    title: "检索验证",
    description: "选择检索配置，验证知识库召回效果，对比不同配置的检索结果。",
    icon: Search,
    target: "/retrieval",
  },
  {
    id: "settings",
    title: "设置",
    description: "配置认证令牌、权限范围和界面偏好，开始使用工作台。",
    icon: Settings,
    target: "/settings",
  },
];

export function OnboardingTour() {
  const router = useRouter();
  const [hasCompleted, setHasCompleted] = useLocalStorage("ekb-onboarding-completed", false);
  const [dismissed, setDismissed] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || hasCompleted || dismissed) return null;

  const step = steps[stepIndex];
  const Icon = step.icon;
  const isFirst = stepIndex === 0;
  const isLast = stepIndex === steps.length - 1;

  const handleNext = () => {
    if (isLast) {
      setHasCompleted(true);
    } else {
      setStepIndex((i) => i + 1);
    }
  };

  const handleSkip = () => {
    setDismissed(true);
  };

  const handleJump = () => {
    setHasCompleted(true);
    router.push(step.target);
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
        onClick={handleSkip}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 16 }}
          transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
          className="relative w-full max-w-md overflow-hidden rounded-[28px] border border-white/[0.06] bg-card shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={handleSkip}
            className="absolute right-4 top-4 rounded-full p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            aria-label="关闭引导"
          >
            <X className="h-4 w-4" />
          </button>

          <div className="bg-gradient-to-br from-primary/10 to-primary/5 p-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Sparkles className="h-6 w-6" />
            </div>
            <h2 className="mt-4 text-xl font-semibold">欢迎使用 Knowledge Workbench</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              跟随 4 步引导，快速了解核心工作流
            </p>
          </div>

          <div className="p-6">
            <div className="mb-6 flex items-center gap-2">
              {steps.map((s, i) => (
                <div
                  key={s.id}
                  className={`h-1.5 flex-1 rounded-full transition-colors ${
                    i <= stepIndex ? "bg-primary" : "bg-muted"
                  }`}
                />
              ))}
            </div>

            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    第 {stepIndex + 1} / {steps.length} 步
                  </p>
                  <h3 className="text-lg font-semibold">{step.title}</h3>
                </div>
              </div>
              <p className="text-sm leading-6 text-muted-foreground">{step.description}</p>
            </motion.div>

            <div className="mt-8 flex items-center justify-between">
              <Button variant="ghost" size="sm" onClick={handleSkip}>
                跳过
              </Button>
              <div className="flex gap-2">
                {!isFirst ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setStepIndex((i) => i - 1)}
                  >
                    <ChevronLeft className="mr-1 h-4 w-4" />
                    上一步
                  </Button>
                ) : null}
                <Button size="sm" onClick={handleNext}>
                  {isLast ? "完成" : "下一步"}
                  {!isLast ? <ChevronRight className="ml-1 h-4 w-4" /> : null}
                </Button>
              </div>
            </div>

            {!isLast ? (
              <Button
                variant="link"
                size="sm"
                className="mt-2 w-full text-muted-foreground"
                onClick={handleJump}
              >
                跳转到 {step.title} 页面
              </Button>
            ) : null}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
