"use client";

import { useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";

export default function SettingsPage() {
  const {
    demoToken,
    setDemoToken,
    demoApiKey,
    setDemoApiKey,
    accessScope,
    setAccessScope,
  } = useAppStore();

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

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">设置</h1>
        <p className="text-sm text-muted-foreground mt-1">
          配置演示认证令牌和上传权限范围。
        </p>
      </div>

      <Tabs defaultValue="auth">
        <TabsList>
          <TabsTrigger value="auth">
            <KeyRound className="h-3.5 w-3.5 mr-1" />
            认证
          </TabsTrigger>
          <TabsTrigger value="scope">
            <Shield className="h-3.5 w-3.5 mr-1" />
            权限范围
          </TabsTrigger>
        </TabsList>

        <TabsContent value="auth" className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">演示认证</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="jwt-token">演示 JWT 令牌（工作台 / 管理）</Label>
                <Input
                  id="jwt-token"
                  type="password"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="eyJhbG... 格式的 JWT 令牌"
                />
                <p className="text-xs text-muted-foreground">
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
                <p className="text-xs text-muted-foreground">
                  用于通过访问服务进行检索（X-API-Key 请求头）。
                </p>
              </div>
              <Button onClick={saveAuth}>
                <Save className="h-4 w-4 mr-2" />
                保存认证设置
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="scope" className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">权限范围</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>范围类型</Label>
                <Select
                  value={scopeForm.scope_type}
                  onValueChange={(v) =>
                    setScopeForm((f) => ({ ...f, scope_type: v as "internal" | "external" }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="internal">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-3.5 w-3.5" />
                        内部（部门/角色/用户/组）
                      </div>
                    </SelectItem>
                    <SelectItem value="external">
                      <div className="flex items-center gap-2">
                        <Globe className="h-3.5 w-3.5" />
                        外部（代理/API 密钥/客户/应用）
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {scopeForm.scope_type === "internal" ? (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label>部门</Label>
                    <Input
                      value={scopeForm.department}
                      onChange={(e) =>
                        setScopeForm((f) => ({ ...f, department: e.target.value }))
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
                        setScopeForm((f) => ({ ...f, agent_type_id: e.target.value }))
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
                        setScopeForm((f) => ({ ...f, customer: e.target.value }))
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

              <Button onClick={saveScope}>
                <Save className="h-4 w-4 mr-2" />
                保存权限范围
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
