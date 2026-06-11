"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  KeyRound,
  Globe,
  Save,
  Shield,
  Building2,
  User,
  Settings,
  Lock,
  Database,
  Bell,
  Keyboard,
  Trash2,
  Info,
  Monitor,
  Sun,
  Moon,
  LayoutTemplate,
  PanelLeft,
  PanelLeftClose,
  Zap,
  Download,
  Upload,
  HardDrive,
  ExternalLink,
  Clock,
  FileText,
  X,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { RadioGroup, RadioItem } from "@/components/ui/radio-group";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
import { staggerContainer, staggerItem } from "@/lib/animations";
import { workbenchApi } from "@/lib/api/client";

type TabValue =
  | "auth"
  | "scope"
  | "profile"
  | "preferences"
  | "security"
  | "data"
  | "notifications"
  | "shortcuts"
  | "account"
  | "about";

interface UserInfo {
  user_id: string;
  email: string;
  display_name?: string;
  roles: string[];
  tenant_id: string;
  allowed_collections: string[];
}

function ComingSoonTooltip({ children }: { children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger>{children}</TooltipTrigger>
      <TooltipContent>即将推出</TooltipContent>
    </Tooltip>
  );
}

export default function SettingsPage() {
  const {
    demoToken,
    setDemoToken,
    demoApiKey,
    setDemoApiKey,
    accessScope,
    setAccessScope,
    sidebarOpen,
    setSidebarOpen,
    uiDensity,
    setUiDensity,
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

  // Profile
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [userInfoError, setUserInfoError] = useState(false);

  // Preferences
  const [language, setLanguage] = useState<"zh" | "en">("zh");
  const [theme, setTheme] = useState<"dark" | "light" | "system">("dark");

  useEffect(() => {
    workbenchApi
      .me()
      .then((data) => {
        setUserInfo(data);
        setUserInfoError(false);
      })
      .catch(() => {
        setUserInfoError(true);
      });
  }, []);

  useEffect(() => {
    const storedLang = localStorage.getItem("ekb-language");
    if (storedLang === "zh" || storedLang === "en") setLanguage(storedLang);
    const storedTheme = localStorage.getItem("ekb-theme");
    if (storedTheme === "dark" || storedTheme === "light" || storedTheme === "system")
      setTheme(storedTheme);
  }, []);

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

  const handleLanguageChange = (value: string) => {
    const lang = value as "zh" | "en";
    setLanguage(lang);
    localStorage.setItem("ekb-language", lang);
    toast.success(lang === "zh" ? "语言已切换为中文" : "Language switched to English");
  };

  const handleThemeChange = (value: string) => {
    const t = value as "dark" | "light" | "system";
    setTheme(t);
    localStorage.setItem("ekb-theme", t);
    const root = document.documentElement;
    if (t === "dark") {
      root.classList.add("dark");
    } else if (t === "light") {
      root.classList.remove("dark");
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      if (prefersDark) root.classList.add("dark");
      else root.classList.remove("dark");
    }
    toast.success("主题已更新");
  };

  const clearLocalCache = () => {
    const keysToRemove = Object.keys(localStorage).filter(
      (k) =>
        k.startsWith("ekb-") ||
        k.startsWith("ekb_workbench") ||
        k.startsWith("zustand")
    );
    keysToRemove.forEach((k) => localStorage.removeItem(k));
    toast.success("本地缓存已清除");
  };

  const tabs: { value: TabValue; label: string; icon: typeof KeyRound }[] = [
    { value: "auth", label: "认证", icon: KeyRound },
    { value: "scope", label: "权限范围", icon: Shield },
    { value: "profile", label: "个人资料", icon: User },
    { value: "preferences", label: "偏好设置", icon: Settings },
    { value: "security", label: "安全设置", icon: Lock },
    { value: "data", label: "数据管理", icon: Database },
    { value: "notifications", label: "通知偏好", icon: Bell },
    { value: "shortcuts", label: "快捷键", icon: Keyboard },
    { value: "account", label: "账户管理", icon: Trash2 },
    { value: "about", label: "关于", icon: Info },
  ];

  const notificationEvents = [
    { key: "upload", label: "文档上传完成" },
    { key: "review", label: "审核任务分配" },
    { key: "decision", label: "审核结果通知" },
    { key: "system", label: "系统公告" },
  ];

  const shortcutsList = [
    { action: "全局搜索", key: "Ctrl + K" },
    { action: "新建上传", key: "Ctrl + U" },
    { action: "打开设置", key: "Ctrl + ," },
    { action: "切换侧边栏", key: "Ctrl + B" },
    { action: "返回上一页", key: "Alt + ←" },
    { action: "前进下一页", key: "Alt + →" },
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
          配置演示认证令牌、权限范围和个人偏好。
        </p>
      </motion.div>

      {/* Custom Tabs */}
      <motion.div variants={staggerItem}>
        <div className="glass rounded-xl p-1 inline-flex flex-wrap gap-1 mb-4">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.value;
            return (
              <button
                key={tab.value}
                onClick={() => setActiveTab(tab.value)}
                className={
                  "relative flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-200 " +
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

      <AnimatePresence mode="wait">
        {/* ── Auth Tab ── */}
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

        {/* ── Scope Tab ── */}
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

        {/* ── Profile Tab ── */}
        {activeTab === "profile" && (
          <motion.div
            key="profile"
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
                    <User className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">个人资料</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {userInfoError ? (
                  <p className="text-sm text-muted-foreground">
                    无法获取用户信息，请检查认证设置。
                  </p>
                ) : userInfo ? (
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <Label className="text-muted-foreground">用户 ID</Label>
                      <p className="font-medium">{userInfo.user_id}</p>
                    </div>
                    <div>
                      <Label className="text-muted-foreground">邮箱</Label>
                      <p className="font-medium">{userInfo.email}</p>
                    </div>
                    <div>
                      <Label className="text-muted-foreground">角色</Label>
                      <p className="font-medium">{userInfo.roles.join(", ")}</p>
                    </div>
                    <div>
                      <Label className="text-muted-foreground">租户 ID</Label>
                      <p className="font-medium">{userInfo.tenant_id}</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">加载中...</p>
                )}

                <div className="space-y-3 pt-2 border-t border-white/5">
                  <ComingSoonTooltip>
                    <div className="space-y-2">
                      <Label>头像</Label>
                      <Input disabled placeholder="头像 URL" />
                    </div>
                  </ComingSoonTooltip>
                  <ComingSoonTooltip>
                    <div className="space-y-2">
                      <Label>昵称</Label>
                      <Input disabled placeholder="您的昵称" />
                    </div>
                  </ComingSoonTooltip>
                  <ComingSoonTooltip>
                    <div className="space-y-2">
                      <Label>部门</Label>
                      <Input disabled placeholder="所属部门" />
                    </div>
                  </ComingSoonTooltip>
                  <ComingSoonTooltip>
                    <div className="space-y-2">
                      <Label>联系方式</Label>
                      <Input disabled placeholder="电话 / 其他联系方式" />
                    </div>
                  </ComingSoonTooltip>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ── Preferences Tab ── */}
        {activeTab === "preferences" && (
          <motion.div
            key="preferences"
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
                    <Settings className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">偏好设置</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <Label>语言</Label>
                  <RadioGroup
                    value={language}
                    onValueChange={handleLanguageChange}
                  >
                    <RadioItem value="zh" label="中文" />
                    <RadioItem value="en" label="English" />
                  </RadioGroup>
                </div>

                <div className="space-y-2">
                  <Label>主题</Label>
                  <RadioGroup value={theme} onValueChange={handleThemeChange}>
                    <RadioItem value="dark" label="深色" />
                    <RadioItem value="light" label="浅色" />
                    <RadioItem value="system" label="跟随系统" />
                  </RadioGroup>
                </div>

                <div className="space-y-2">
                  <Label>界面密度</Label>
                  <RadioGroup
                    value={uiDensity}
                    onValueChange={(v) =>
                      setUiDensity(v as "compact" | "comfortable")
                    }
                  >
                    <RadioItem value="compact" label="紧凑" />
                    <RadioItem value="comfortable" label="舒适" />
                  </RadioGroup>
                </div>

                <div className="space-y-2">
                  <Label>默认侧边栏状态</Label>
                  <div className="flex items-center gap-3">
                    <Button
                      variant={sidebarOpen ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSidebarOpen(true)}
                      className="gap-2"
                    >
                      <PanelLeft className="h-4 w-4" />
                      展开
                    </Button>
                    <Button
                      variant={!sidebarOpen ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSidebarOpen(false)}
                      className="gap-2"
                    >
                      <PanelLeftClose className="h-4 w-4" />
                      收起
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ── Security Tab ── */}
        {activeTab === "security" && (
          <motion.div
            key="security"
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
                    <Lock className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">安全设置</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <ComingSoonTooltip>
                  <Button disabled className="w-full justify-start gap-2">
                    <KeyRound className="h-4 w-4" />
                    修改密码
                  </Button>
                </ComingSoonTooltip>
                <ComingSoonTooltip>
                  <Button disabled className="w-full justify-start gap-2">
                    <Shield className="h-4 w-4" />
                    双重认证 (2FA)
                  </Button>
                </ComingSoonTooltip>
                <ComingSoonTooltip>
                  <Button disabled className="w-full justify-start gap-2">
                    <Monitor className="h-4 w-4" />
                    设备管理
                  </Button>
                </ComingSoonTooltip>
                <ComingSoonTooltip>
                  <Button disabled className="w-full justify-start gap-2">
                    <Clock className="h-4 w-4" />
                    登录历史
                  </Button>
                </ComingSoonTooltip>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ── Data Tab ── */}
        {activeTab === "data" && (
          <motion.div
            key="data"
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
                    <Database className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">数据管理</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button
                  variant="destructive"
                  onClick={clearLocalCache}
                  className="w-full justify-start gap-2"
                >
                  <X className="h-4 w-4" />
                  清除本地缓存
                </Button>
                <ComingSoonTooltip>
                  <Button disabled className="w-full justify-start gap-2">
                    <Download className="h-4 w-4" />
                    导出个人数据
                  </Button>
                </ComingSoonTooltip>
                <ComingSoonTooltip>
                  <Button disabled className="w-full justify-start gap-2">
                    <Upload className="h-4 w-4" />
                    导入设置
                  </Button>
                </ComingSoonTooltip>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ── Notifications Tab ── */}
        {activeTab === "notifications" && (
          <motion.div
            key="notifications"
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
                    <Bell className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">通知偏好</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  {notificationEvents.map((evt) => (
                    <ComingSoonTooltip key={evt.key}>
                      <div className="flex items-center justify-between">
                        <span className="text-sm">{evt.label}</span>
                        <Switch disabled />
                      </div>
                    </ComingSoonTooltip>
                  ))}
                </div>
                <div className="pt-2 border-t border-white/5">
                  <ComingSoonTooltip>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">邮件通知</span>
                      <Switch disabled />
                    </div>
                  </ComingSoonTooltip>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ── Shortcuts Tab ── */}
        {activeTab === "shortcuts" && (
          <motion.div
            key="shortcuts"
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
                    <Keyboard className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">快捷键</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {shortcutsList.map((s) => (
                  <ComingSoonTooltip key={s.action}>
                    <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/[0.03] border border-white/[0.05]">
                      <span className="text-sm">{s.action}</span>
                      <kbd className="px-2 py-0.5 rounded bg-white/10 text-xs font-mono">
                        {s.key}
                      </kbd>
                    </div>
                  </ComingSoonTooltip>
                ))}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ── Account Tab ── */}
        {activeTab === "account" && (
          <motion.div
            key="account"
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
                    <Trash2 className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">账户管理</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <ComingSoonTooltip>
                  <Button disabled className="w-full justify-start gap-2">
                    <X className="h-4 w-4" />
                    申请注销账户
                  </Button>
                </ComingSoonTooltip>
                <ComingSoonTooltip>
                  <Button disabled className="w-full justify-start gap-2">
                    <HardDrive className="h-4 w-4" />
                    请求删除个人数据
                  </Button>
                </ComingSoonTooltip>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ── About Tab ── */}
        {activeTab === "about" && (
          <motion.div
            key="about"
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
                    <Info className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">关于</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-muted-foreground">产品版本</span>
                  <span className="font-medium">v2.4.0</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-muted-foreground">构建时间</span>
                  <span className="font-medium">2026-06-11</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-muted-foreground">许可证</span>
                  <span className="font-medium">Enterprise License</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() =>
                    window.open("/health", "_blank")
                  }
                >
                  <ExternalLink className="h-4 w-4" />
                  查看服务健康状态
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
