"use client";

import { useState, useEffect, useCallback } from "react";
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
  ExternalLink,
  Clock,
  X,
  Smartphone,
  MapPin,
  LogOut,
  AlertTriangle,
  Check,
  Eye,
  EyeOff,
  Package,
  Heart,
  Code2,
  Mail,
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
import { ConfirmDialog } from "@/components/confirm-dialog";
import { toast } from "sonner";
import { staggerContainer, staggerItem } from "@/lib/animations";
import { workbenchApi } from "@/lib/api/client";
import { useFormAutosave } from "@/hooks/use-form-autosave";

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

const notificationEvents = [
  { key: "upload", label: "文档上传完成" },
  { key: "review", label: "审核任务分配" },
  { key: "decision", label: "审核结果通知" },
  { key: "system", label: "系统公告" },
];

const shortcutsList = [
  { action: "全局搜索", key: "Ctrl + K", scope: "全局" },
  { action: "新建上传", key: "Ctrl + U", scope: "全局" },
  { action: "打开设置", key: "Ctrl + ,", scope: "全局" },
  { action: "切换侧边栏", key: "Ctrl + B", scope: "全局" },
  { action: "返回上一页", key: "Alt + ←", scope: "全局" },
  { action: "前进下一页", key: "Alt + →", scope: "全局" },
  { action: "刷新页面", key: "Ctrl + R", scope: "全局" },
  { action: "打开命令面板", key: "Ctrl + Shift + P", scope: "全局" },
];

const mockDevices = [
  { id: "d1", name: "Windows Chrome", location: "北京", lastActive: "2026-06-11 09:30", current: true },
  { id: "d2", name: "macOS Safari", location: "上海", lastActive: "2026-06-10 18:45", current: false },
  { id: "d3", name: "iPhone App", location: "深圳", lastActive: "2026-06-09 14:20", current: false },
];

const mockLoginHistory = [
  { time: "2026-06-11 09:30", device: "Windows Chrome", location: "北京", ip: "192.168.1.100", status: "success" as const },
  { time: "2026-06-10 18:45", device: "macOS Safari", location: "上海", ip: "192.168.2.50", status: "success" as const },
  { time: "2026-06-09 14:20", device: "iPhone App", location: "深圳", ip: "10.0.0.15", status: "success" as const },
  { time: "2026-06-08 08:10", device: "Windows Edge", location: "北京", ip: "192.168.1.101", status: "failed" as const },
  { time: "2026-06-07 22:30", device: "Android Chrome", location: "广州", ip: "172.16.0.20", status: "success" as const },
];

const licenses = [
  { name: "Next.js", license: "MIT", url: "https://github.com/vercel/next.js" },
  { name: "React", license: "MIT", url: "https://github.com/facebook/react" },
  { name: "Tailwind CSS", license: "MIT", url: "https://github.com/tailwindlabs/tailwindcss" },
  { name: "Framer Motion", license: "MIT", url: "https://github.com/framer/motion" },
  { name: "Zustand", license: "MIT", url: "https://github.com/pmndrs/zustand" },
  { name: "Lucide Icons", license: "ISC", url: "https://github.com/lucide-icons/lucide" },
  { name: "Base UI", license: "MIT", url: "https://github.com/mui/base-ui" },
];

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
    theme: storeTheme,
    setTheme,
    language: storeLanguage,
    setLanguage,
    notificationPrefs,
    setSiteNotification,
    setEmailEnabled,
    setEmailNotification,
    setDnd,
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

  // Security
  const [passwordForm, setPasswordForm] = useState({ current: "", new: "", confirm: "" });
  const [showPassword, setShowPassword] = useState({ current: false, new: false, confirm: false });
  const [passwordLoading, setPasswordLoading] = useState(false);

  // Account
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Autosave tracking
  const [authSaved, setAuthSaved] = useState(false);
  const [scopeSaved, setScopeSaved] = useState(false);

  // Wire form autosave hooks for auth and scope forms
  useFormAutosave({
    key: "ekb-settings-auth-token",
    value: authSaved ? tokenInput : null,
    debounceMs: 2000,
    onRestore: (saved) => {
      if (saved) setTokenInput(saved);
    },
  });
  useFormAutosave({
    key: "ekb-settings-auth-api-key",
    value: authSaved ? apiKeyInput : null,
    debounceMs: 2000,
    onRestore: (saved) => {
      if (saved) setApiKeyInput(saved);
    },
  });
  useFormAutosave({
    key: "ekb-settings-scope-form",
    value: scopeSaved ? scopeForm : null,
    debounceMs: 2000,
    onRestore: (saved) => {
      if (saved) setScopeForm(saved as typeof scopeForm);
    },
  });

  // Show a subtle success indicator for autosave
  const [autoSaved, setAutoSaved] = useState<string | null>(null);

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

  const saveAuth = () => {
    setDemoToken(tokenInput || null);
    setDemoApiKey(apiKeyInput || null);
    setAuthSaved(true);
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
    setScopeSaved(true);
    toast.success("权限范围已保存");
  };

  const handleThemeChange = (value: string) => {
    const t = value as "dark" | "light" | "system";
    setTheme(t);
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

  const handleChangePassword = async () => {
    if (!passwordForm.current || !passwordForm.new || !passwordForm.confirm) {
      toast.error("请填写所有密码字段");
      return;
    }
    if (passwordForm.new !== passwordForm.confirm) {
      toast.error("新密码与确认密码不一致");
      return;
    }
    if (passwordForm.new.length < 8) {
      toast.error("新密码至少需要 8 位");
      return;
    }
    setPasswordLoading(true);
    try {
      await workbenchApi.me();
      toast.success("密码修改成功（演示模式）");
      setPasswordForm({ current: "", new: "", confirm: "" });
    } catch {
      toast.error("密码修改失败，请检查当前密码");
    } finally {
      setPasswordLoading(false);
    }
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

  const handleExportData = () => {
    const data = {
      userInfo,
      exportTime: new Date().toISOString(),
      preferences: {
        theme: storeTheme,
        language: storeLanguage,
        uiDensity,
        sidebarOpen,
        notificationPrefs,
      },
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ekb-user-data-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("个人数据已导出");
  };

  const handleDeleteAccount = () => {
    setDeleteLoading(true);
    setTimeout(() => {
      setDeleteLoading(false);
      setDeleteDialogOpen(false);
      toast.success("账户注销申请已提交");
    }, 1500);
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
                <div className="flex items-center gap-2">
                  <Button onClick={saveAuth} className="shadow-glow">
                    <Save className="h-4 w-4 mr-2" />
                    保存认证设置
                  </Button>
                  {authSaved && (
                    <span className="flex items-center gap-1 text-[11px] text-emerald-500">
                      <Check className="h-3 w-3" />
                      已自动保存
                    </span>
                  )}
                </div>
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

                <div className="flex items-center gap-2">
                  <Button onClick={saveScope} className="shadow-glow">
                    <Save className="h-4 w-4 mr-2" />
                    保存权限范围
                  </Button>
                  {scopeSaved && (
                    <span className="flex items-center gap-1 text-[11px] text-emerald-500">
                      <Check className="h-3 w-3" />
                      已自动保存
                    </span>
                  )}
                </div>
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
                {/* Theme */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Sun className="h-3.5 w-3.5 text-muted-foreground" />
                    主题
                  </Label>
                  <RadioGroup value={storeTheme} onValueChange={handleThemeChange}>
                    <RadioItem value="dark" label="深色" />
                    <RadioItem value="light" label="浅色" />
                    <RadioItem value="system" label="跟随系统" />
                  </RadioGroup>
                </div>

                {/* Language */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                    语言
                  </Label>
                  <RadioGroup
                    value={storeLanguage}
                    onValueChange={(v) => setLanguage(v as "zh" | "en")}
                  >
                    <RadioItem value="zh" label="中文" />
                    <RadioItem value="en" label="English" />
                  </RadioGroup>
                </div>

                {/* UI Density */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <LayoutTemplate className="h-3.5 w-3.5 text-muted-foreground" />
                    界面密度
                  </Label>
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

                {/* Sidebar Default */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <PanelLeft className="h-3.5 w-3.5 text-muted-foreground" />
                    默认侧边栏状态
                  </Label>
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
            {/* Change Password */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <KeyRound className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">修改密码</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>当前密码</Label>
                  <div className="relative">
                    <Input
                      type={showPassword.current ? "text" : "password"}
                      value={passwordForm.current}
                      onChange={(e) =>
                        setPasswordForm((f) => ({ ...f, current: e.target.value }))
                      }
                      placeholder="输入当前密码"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowPassword((s) => ({ ...s, current: !s.current }))
                      }
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword.current ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>新密码</Label>
                  <div className="relative">
                    <Input
                      type={showPassword.new ? "text" : "password"}
                      value={passwordForm.new}
                      onChange={(e) =>
                        setPasswordForm((f) => ({ ...f, new: e.target.value }))
                      }
                      placeholder="至少 8 位字符"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowPassword((s) => ({ ...s, new: !s.new }))
                      }
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword.new ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>确认新密码</Label>
                  <div className="relative">
                    <Input
                      type={showPassword.confirm ? "text" : "password"}
                      value={passwordForm.confirm}
                      onChange={(e) =>
                        setPasswordForm((f) => ({ ...f, confirm: e.target.value }))
                      }
                      placeholder="再次输入新密码"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowPassword((s) => ({ ...s, confirm: !s.confirm }))
                      }
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword.confirm ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
                <Button
                  onClick={handleChangePassword}
                  disabled={passwordLoading}
                  className="shadow-glow"
                >
                  <Save className="h-4 w-4 mr-2" />
                  {passwordLoading ? "保存中..." : "修改密码"}
                </Button>
              </CardContent>
            </Card>

            {/* 2FA */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Shield className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">双重认证 (2FA)</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between py-3 px-4 rounded-lg bg-white/[0.03] border border-white/[0.05]">
                  <div className="flex items-center gap-3">
                    <Shield className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">双重认证</p>
                      <p className="text-xs text-muted-foreground">
                        通过验证码或安全密钥增强账户安全
                      </p>
                    </div>
                  </div>
                  <ComingSoonTooltip>
                    <Button size="sm" variant="outline" disabled>
                      配置
                    </Button>
                  </ComingSoonTooltip>
                </div>
              </CardContent>
            </Card>

            {/* Device Management */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Monitor className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">登录设备</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {mockDevices.map((device) => (
                  <div
                    key={device.id}
                    className="flex items-center justify-between py-3 px-4 rounded-lg bg-white/[0.03] border border-white/[0.05]"
                  >
                    <div className="flex items-center gap-3">
                      <Smartphone className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium flex items-center gap-2">
                          {device.name}
                          {device.current && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/20 text-primary">
                              当前
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <MapPin className="h-3 w-3" />
                          {device.location} · {device.lastActive}
                        </p>
                      </div>
                    </div>
                    {!device.current && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        onClick={() => toast.success(`已踢出设备：${device.name}`)}
                      >
                        <LogOut className="h-3.5 w-3.5 mr-1" />
                        踢出
                      </Button>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Login History */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Clock className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">登录历史</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {mockLoginHistory.map((log, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2.5 px-4 rounded-lg bg-white/[0.03] border border-white/[0.05]"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={
                          "w-2 h-2 rounded-full " +
                          (log.status === "success" ? "bg-emerald-400" : "bg-red-400")
                        }
                      />
                      <div>
                        <p className="text-sm">
                          {log.device} · {log.location}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {log.time} · {log.ip}
                        </p>
                      </div>
                    </div>
                    {log.status === "success" ? (
                      <Check className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <X className="h-4 w-4 text-red-400" />
                    )}
                  </div>
                ))}
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
            {/* Site Notifications */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Bell className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">站内通知</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {notificationEvents.map((evt) => (
                  <div
                    key={evt.key}
                    className="flex items-center justify-between py-2"
                  >
                    <span className="text-sm">{evt.label}</span>
                    <Switch
                      checked={notificationPrefs.site[evt.key] ?? true}
                      onChange={(e) =>
                        setSiteNotification(evt.key, e.target.checked)
                      }
                    />
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Email Notifications */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Mail className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">邮件通知</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-sm font-medium">启用邮件通知</span>
                  <Switch
                    checked={notificationPrefs.email.enabled}
                    onChange={(e) => setEmailEnabled(e.target.checked)}
                  />
                </div>
                {notificationEvents.map((evt) => (
                  <div
                    key={evt.key}
                    className="flex items-center justify-between py-2"
                  >
                    <span className="text-sm text-muted-foreground">
                      {evt.label}
                    </span>
                    <Switch
                      checked={notificationPrefs.email.events[evt.key] ?? false}
                      disabled={!notificationPrefs.email.enabled}
                      onChange={(e) =>
                        setEmailNotification(evt.key, e.target.checked)
                      }
                    />
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* DND */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Moon className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">免打扰时段</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm">启用免打扰</span>
                  <Switch
                    checked={notificationPrefs.dnd.enabled}
                    onChange={(e) =>
                      setDnd({ ...notificationPrefs.dnd, enabled: e.target.checked })
                    }
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">开始时间</Label>
                    <Input
                      type="time"
                      value={notificationPrefs.dnd.start}
                      disabled={!notificationPrefs.dnd.enabled}
                      onChange={(e) =>
                        setDnd({ ...notificationPrefs.dnd, start: e.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">结束时间</Label>
                    <Input
                      type="time"
                      value={notificationPrefs.dnd.end}
                      disabled={!notificationPrefs.dnd.enabled}
                      onChange={(e) =>
                        setDnd({ ...notificationPrefs.dnd, end: e.target.value })
                      }
                    />
                  </div>
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
                  <CardTitle className="text-base">快捷键一览</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-hidden rounded-lg border border-white/[0.05]">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-white/[0.03] border-b border-white/[0.05]">
                        <th className="text-left px-4 py-2.5 text-muted-foreground font-medium">
                          操作
                        </th>
                        <th className="text-left px-4 py-2.5 text-muted-foreground font-medium">
                          快捷键
                        </th>
                        <th className="text-left px-4 py-2.5 text-muted-foreground font-medium">
                          作用域
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {shortcutsList.map((s, idx) => (
                        <tr
                          key={s.action}
                          className={
                            idx < shortcutsList.length - 1
                              ? "border-b border-white/[0.03]"
                              : ""
                          }
                        >
                          <td className="px-4 py-3">{s.action}</td>
                          <td className="px-4 py-3">
                            <kbd className="px-2 py-0.5 rounded bg-white/10 text-xs font-mono">
                              {s.key}
                            </kbd>
                          </td>
                          <td className="px-4 py-3 text-muted-foreground text-xs">
                            {s.scope}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
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
            {/* Account Info */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <User className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">账户信息</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {userInfo ? (
                  <>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-muted-foreground">用户 ID</span>
                      <span className="font-medium">{userInfo.user_id}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-muted-foreground">邮箱</span>
                      <span className="font-medium">{userInfo.email}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-muted-foreground">角色</span>
                      <span className="font-medium">
                        {userInfo.roles.join(", ")}
                      </span>
                    </div>
                  </>
                ) : (
                  <p className="text-muted-foreground">加载中...</p>
                )}
              </CardContent>
            </Card>

            {/* Data Export */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Download className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">数据导出</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  导出您的个人数据，包括偏好设置和账户信息。
                </p>
                <Button
                  variant="outline"
                  onClick={handleExportData}
                  className="gap-2"
                >
                  <Download className="h-4 w-4" />
                  导出个人数据
                </Button>
              </CardContent>
            </Card>

            {/* Danger Zone */}
            <Card className="glass-card border-red-500/20">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-red-500/10">
                    <AlertTriangle className="h-4 w-4 text-red-400" />
                  </div>
                  <CardTitle className="text-base text-red-400">危险区域</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  账户注销后，您的所有数据将被标记为删除，此操作不可撤销。
                </p>
                <Button
                  variant="destructive"
                  onClick={() => setDeleteDialogOpen(true)}
                  className="gap-2"
                >
                  <Trash2 className="h-4 w-4" />
                  申请注销账户
                </Button>
              </CardContent>
            </Card>

            <ConfirmDialog
              open={deleteDialogOpen}
              onOpenChange={setDeleteDialogOpen}
              title="确认注销账户"
              description="此操作将永久删除您的账户及所有关联数据，无法恢复。"
              consequence="此操作不可撤销"
              confirmLabel="确认注销"
              cancelLabel="取消"
              variant="destructive"
              isLoading={deleteLoading}
              onConfirm={handleDeleteAccount}
            />
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
            {/* Version */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Package className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">版本信息</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-muted-foreground">产品版本</span>
                  <span className="font-medium">v2.4.0</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-muted-foreground">构建时间</span>
                  <span className="font-medium">2026-06-11</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/5">
                  <span className="text-muted-foreground">前端框架</span>
                  <span className="font-medium">Next.js 16 + React 19</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-muted-foreground">样式方案</span>
                  <span className="font-medium">Tailwind CSS v4</span>
                </div>
              </CardContent>
            </Card>

            {/* Licenses */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Code2 className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">开源许可证</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-1">
                {licenses.map((lic) => (
                  <a
                    key={lic.name}
                    href={lic.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-white/[0.03] transition-colors group"
                  >
                    <span className="text-sm group-hover:text-foreground transition-colors">
                      {lic.name}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {lic.license}
                      </span>
                      <ExternalLink className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </a>
                ))}
              </CardContent>
            </Card>

            {/* Service Status */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Zap className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">服务状态</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => window.open("/health", "_blank")}
                >
                  <ExternalLink className="h-4 w-4" />
                  查看服务健康状态
                </Button>
              </CardContent>
            </Card>

            {/* Team */}
            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
                    <Heart className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">团队</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Enterprise Knowledge Base — 由知识工程团队倾力打造。
                </p>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
