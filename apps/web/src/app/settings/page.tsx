"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  KeyRound,
  Globe,
  Save,
  Shield,
  Building2,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { staggerContainer, staggerItem } from "@/lib/animations";

type TabValue = "auth" | "scope";

export default function SettingsPage() {
  const {
    demoToken,
    setDemoToken,
    demoApiKey,
    setDemoApiKey,
    accessScope,
    setAccessScope,
  } = useAppStore();

  const [activeTab, setActiveTab] = useState<TabValue>("auth");
  const [tokenInput, setTokenInput] = useState(demoToken || "");
  const [apiKeyInput, setApiKeyInput] = useState(demoApiKey || "");
  const [scopeForm, setScopeForm] = useState({
    scope_type: (accessScope?.scope_type as "internal" | "external") || "internal",
    department: accessScope?.department || "",
    role: accessScope?.role || "",
    user: accessScope?.user || "",
    group: accessScope?.group || "",
    agent_type_id: accessScope?.agent_type_id || "",
    api_key: accessScope?.api_key || "",
    customer: accessScope?.customer || "",
    app: accessScope?.app || "",
  });

  const saveAuth = () => {
    setDemoToken(tokenInput || null);
    setDemoApiKey(apiKeyInput || null);
    toast.success("认证设置已保存");
  };

  const saveScope = () => {
    const scope = {
      scope_type: scopeForm.scope_type,
      ...(scopeForm.scope_type === "internal"
        ? {
            department: scopeForm.department || undefined,
            role: scopeForm.role || undefined,
            user: scopeForm.user || undefined,
            group: scopeForm.group || undefined,
          }
        : {
            agent_type_id: scopeForm.agent_type_id || undefined,
            api_key: scopeForm.api_key || undefined,
            customer: scopeForm.customer || undefined,
            app: scopeForm.app || undefined,
          }),
    };
    setAccessScope(scope);
    toast.success("权限范围已保存");
  };

  const tabs: { value: TabValue; label: string; icon: typeof KeyRound }[] = [
    { value: "auth", label: "认证", icon: KeyRound },
    { value: "scope", label: "权限范围", icon: Shield },
  ];

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-6 max-w-2xl"
    >
      {/* Header */}
      <motion.div variants={staggerItem}>
        <h1 className="text-2xl font-semibold tracking-tight">设置</h1>
        <p className="text-sm text-muted-foreground mt-1">
          配置演示认证令牌和上传权限范围。
        </p>
      </motion.div>

      {/* Custom Tabs */}
      <motion.div variants={staggerItem}>
        <div className="glass rounded-xl p-1 inline-flex gap-1 mb-4">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.value;
            return (
              <button
                key={tab.value}
                onClick={() => setActiveTab(tab.value)}
                className={
                  "relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 " +
                  (isActive
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground")
                }
              >
                {isActive && (
                  <motion.div
                    layoutId="active-tab"
                    className="absolute inset-0 bg-white/[0.06] rounded-lg border border-white/[0.08]"
                    transition={{
                      type: "spring",
                      stiffness: 400,
                      damping: 30,
                    }}
                  />
                )}
                <span className="relative flex items-center gap-2">
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </span>
              </button>
            );
          })}
        </div>
      </motion.div>

      {/* Auth Tab */}
      <AnimatePresence mode="wait">
        {activeTab === "auth" && (
          <motion.div
            key="auth"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <KeyRound className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">演示认证</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="jwt-token">
                    演示 JWT 令牌（工作台 / 管理）
                  </Label>
                  <Input
                    id="jwt-token"
                    type="password"
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    placeholder="eyJhbG... 格式的 JWT 令牌"
                  />
                  <p className="text-xs text-muted-foreground/50">
                    用于工作台和管理 API 调用。
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="api-key">演示 API 密钥（访问服务）</Label>
                  <Input
                    id="api-key"
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder="123456"
                  />
                  <p className="text-xs text-muted-foreground/50">
                    用于通过访问服务进行检索（X-API-Key 请求头）。
                  </p>
                </div>
                <Button onClick={saveAuth} className="shadow-glow">
                  <Save className="h-4 w-4 mr-2" />
                  保存认证设置
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Scope Tab */}
      <AnimatePresence mode="wait">
        {activeTab === "scope" && (
          <motion.div
            key="scope"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Shield className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">权限范围</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Scope Type — Segmented Control */}
                <div className="space-y-2">
                  <Label>范围类型</Label>
                  <div className="glass rounded-xl p-1 flex gap-1">
                    {[
                      {
                        value: "internal" as const,
                        label: "内部",
                        icon: Building2,
                      },
                      {
                        value: "external" as const,
                        label: "外部",
                        icon: Globe,
                      },
                    ].map((option) => {
                      const isActive = scopeForm.scope_type === option.value;
                      return (
                        <button
                          key={option.value}
                          onClick={() =>
                            setScopeForm((f) => ({
                              ...f,
                              scope_type: option.value,
                            }))
                          }
                          className={
                            "relative flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors duration-200 " +
                            (isActive
                              ? "text-foreground"
                              : "text-muted-foreground hover:text-foreground")
                          }
                        >
                          {isActive && (
                            <motion.div
                              layoutId="scope-type"
                              className="absolute inset-0 bg-white/[0.06] rounded-lg border border-white/[0.08]"
                              transition={{
                                type: "spring",
                                stiffness: 400,
                                damping: 30,
                              }}
                            />
                          )}
                          <span className="relative flex items-center gap-2">
                            <option.icon className="h-4 w-4" />
                            {option.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {scopeForm.scope_type === "internal" ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label>部门</Label>
                      <Input
                        value={scopeForm.department}
                        onChange={(e) =>
                          setScopeForm((f) => ({
                            ...f,
                            department: e.target.value,
                          }))
                        }
                        placeholder="工程部"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>角色</Label>
                      <Input
                        value={scopeForm.role}
                        onChange={(e) =>
                          setScopeForm((f) => ({ ...f, role: e.target.value }))
                        }
                        placeholder="knowledge_admin"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>用户</Label>
                      <Input
                        value={scopeForm.user}
                        onChange={(e) =>
                          setScopeForm((f) => ({ ...f, user: e.target.value }))
                        }
                        placeholder="user@example.com"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>组</Label>
                      <Input
                        value={scopeForm.group}
                        onChange={(e) =>
                          setScopeForm((f) => ({ ...f, group: e.target.value }))
                        }
                        placeholder="knowledge-team"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label>代理类型 ID</Label>
                      <Input
                        value={scopeForm.agent_type_id}
                        onChange={(e) =>
                          setScopeForm((f) => ({
                            ...f,
                            agent_type_id: e.target.value,
                          }))
                        }
                        placeholder="agent_support_v1"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>API 密钥</Label>
                      <Input
                        value={scopeForm.api_key}
                        onChange={(e) =>
                          setScopeForm((f) => ({ ...f, api_key: e.target.value }))
                        }
                        placeholder="ak_xxx"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>客户</Label>
                      <Input
                        value={scopeForm.customer}
                        onChange={(e) =>
                          setScopeForm((f) => ({
                            ...f,
                            customer: e.target.value,
                          }))
                        }
                        placeholder="acme-corp"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>应用</Label>
                      <Input
                        value={scopeForm.app}
                        onChange={(e) =>
                          setScopeForm((f) => ({ ...f, app: e.target.value }))
                        }
                        placeholder="support-portal"
                      />
                    </div>
                  </div>
                )}

                <Button onClick={saveScope} className="shadow-glow">
                  <Save className="h-4 w-4 mr-2" />
                  保存权限范围
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
