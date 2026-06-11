import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { toast } from "sonner";
import SettingsPage from "./page";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const setDemoToken = vi.fn();
const setDemoApiKey = vi.fn();
const setAccessScope = vi.fn();

let mockStore: Record<string, unknown> = {
  demoToken: null,
  setDemoToken,
  demoApiKey: null,
  setDemoApiKey,
  accessScope: null,
  setAccessScope,
};

vi.mock("@/lib/store", () => ({
  useAppStore: (selector?: (state: typeof mockStore) => unknown) =>
    selector ? selector(mockStore) : mockStore,
}));

// ── Helpers ──────────────────────────────────────────────────────────────

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function setStore(overrides: Partial<typeof mockStore>) {
  mockStore = { ...mockStore, ...overrides };
}

// ── Tests ────────────────────────────────────────────────────────────────

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStore = {
      demoToken: null,
      setDemoToken,
      demoApiKey: null,
      setDemoApiKey,
      accessScope: null,
      setAccessScope,
    };
  });

  it("renders header and description", () => {
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    expect(screen.getByRole("heading", { name: /设置/i })).toBeInTheDocument();
    expect(
      screen.getByText(/配置演示认证令牌、权限范围和个人偏好/i)
    ).toBeInTheDocument();
  });

  it("switches between Auth and Scope tabs with active indicator", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    const scopeTab = screen.getAllByRole("button").find((b) =>
      b.textContent?.includes("权限范围")
    );
    expect(scopeTab).toBeInTheDocument();

    expect(screen.getByLabelText(/演示 JWT 令牌/i)).toBeInTheDocument();

    await user.click(scopeTab!);

    await waitFor(() => {
      expect(screen.getByText(/范围类型/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.queryByLabelText(/演示 JWT 令牌/i)).not.toBeInTheDocument();
    });
  });

  it("Auth tab has JWT token and API key password inputs", () => {
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    const tokenInput = screen.getByLabelText(/演示 JWT 令牌/i);
    const apiKeyInput = screen.getByLabelText(/演示 API 密钥/i);

    expect(tokenInput).toHaveAttribute("type", "password");
    expect(apiKeyInput).toHaveAttribute("type", "password");
  });

  it("saving auth updates store and toasts success", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    const tokenInput = screen.getByLabelText(/演示 JWT 令牌/i);
    const apiKeyInput = screen.getByLabelText(/演示 API 密钥/i);

    await user.type(tokenInput, "jwt-token-123");
    await user.type(apiKeyInput, "api-key-456");

    await user.click(screen.getByRole("button", { name: /保存认证设置/i }));

    await waitFor(() => {
      expect(setDemoToken).toHaveBeenCalledWith("jwt-token-123");
    });
    expect(setDemoApiKey).toHaveBeenCalledWith("api-key-456");
    expect(toast.success).toHaveBeenCalledWith("认证设置已保存");
  });

  it("Scope tab has Internal/External segmented switch", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    await user.click(screen.getByRole("button", { name: /权限范围/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /内部/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /外部/i })).toBeInTheDocument();
  });

  it("internal mode shows department, role, user, group fields", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    await user.click(screen.getByRole("button", { name: /权限范围/i }));

    await waitFor(() => {
      expect(screen.getByText(/部门/i)).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText(/工程部/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/knowledge_admin/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/user@example.com/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/knowledge-team/i)).toBeInTheDocument();
  });

  it("external mode shows agent_type_id, api_key, customer, app fields", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    await user.click(screen.getByRole("button", { name: /权限范围/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /外部/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /外部/i }));

    await waitFor(() => {
      expect(screen.getByText(/代理类型 ID/i)).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText(/agent_support_v1/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/ak_xxx/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/acme-corp/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/support-portal/i)).toBeInTheDocument();
  });

  it("saving internal scope assembles correct object and calls setter", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    await user.click(screen.getByRole("button", { name: /权限范围/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/工程部/i)).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/工程部/i), "Engineering");
    await user.type(screen.getByPlaceholderText(/knowledge_admin/i), "admin");
    await user.type(screen.getByPlaceholderText(/user@example.com/i), "u@e.com");
    await user.type(screen.getByPlaceholderText(/knowledge-team/i), "team-a");

    await user.click(screen.getByRole("button", { name: /保存权限范围/i }));

    await waitFor(() => {
      expect(setAccessScope).toHaveBeenCalledWith({
        scope_type: "internal",
        department: "Engineering",
        role: "admin",
        user: "u@e.com",
        group: "team-a",
      });
    });
    expect(toast.success).toHaveBeenCalledWith("权限范围已保存");
  });

  it("saving external scope assembles correct object and calls setter", async () => {
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    await user.click(screen.getByRole("button", { name: /权限范围/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /外部/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /外部/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/agent_support_v1/i)).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/agent_support_v1/i), "agent_v2");
    await user.type(screen.getByPlaceholderText(/ak_xxx/i), "ak_secret");
    await user.type(screen.getByPlaceholderText(/acme-corp/i), "acme");
    await user.type(screen.getByPlaceholderText(/support-portal/i), "portal");

    await user.click(screen.getByRole("button", { name: /保存权限范围/i }));

    await waitFor(() => {
      expect(setAccessScope).toHaveBeenCalledWith({
        scope_type: "external",
        agent_type_id: "agent_v2",
        api_key: "ak_secret",
        customer: "acme",
        app: "portal",
      });
    });
    expect(toast.success).toHaveBeenCalledWith("权限范围已保存");
  });

  it("populates auth inputs from store initial values", () => {
    setStore({ demoToken: "stored-jwt", demoApiKey: "stored-key" });

    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    expect(screen.getByLabelText(/演示 JWT 令牌/i)).toHaveValue("stored-jwt");
    expect(screen.getByLabelText(/演示 API 密钥/i)).toHaveValue("stored-key");
  });

  it("populates internal scope inputs from store initial values", async () => {
    setStore({
      accessScope: {
        scope_type: "internal",
        department: "Dept",
        role: "Role",
        user: "User",
        group: "Group",
      },
    });

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    await user.click(screen.getByRole("button", { name: /权限范围/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/工程部/i)).toHaveValue("Dept");
    });
    expect(screen.getByPlaceholderText(/knowledge_admin/i)).toHaveValue("Role");
    expect(screen.getByPlaceholderText(/user@example.com/i)).toHaveValue("User");
    expect(screen.getByPlaceholderText(/knowledge-team/i)).toHaveValue("Group");
  });

  it("populates external scope inputs from store initial values", async () => {
    setStore({
      accessScope: {
        scope_type: "external",
        agent_type_id: "a1",
        api_key: "k1",
        customer: "c1",
        app: "app1",
      },
    });

    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(<SettingsPage />, { wrapper: Wrapper });

    await user.click(screen.getByRole("button", { name: /权限范围/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/agent_support_v1/i)).toHaveValue("a1");
    });
    expect(screen.getByPlaceholderText(/ak_xxx/i)).toHaveValue("k1");
    expect(screen.getByPlaceholderText(/acme-corp/i)).toHaveValue("c1");
    expect(screen.getByPlaceholderText(/support-portal/i)).toHaveValue("app1");
  });
});
