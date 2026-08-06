import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { SettingsWorkspace } from "@/components/settings/settings-workspace";
import { ToastProvider } from "@/components/ui/toast";

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings",
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));

const mockUser = {
  id: "11111111-1111-4111-8111-111111111111",
  email: "admin@tenant.example",
  full_name: "Admin User",
  status: "active",
  is_tenant_admin: true,
  tenant: {
    id: "22222222-2222-4222-8222-222222222222",
    name: "Acme Corp",
    code: "acme-corp",
    status: "active",
  },
  roles: [
    {
      id: "33333333-3333-4333-8333-333333333333",
      name: "administrator",
      description: "Tenant Administrator",
    },
  ],
  created_at: "2026-01-15T10:00:00Z",
};

const mockLiveness = {
  status: "ok",
  service: "Tenant Intelligence",
  version: "0.1.0",
};

const mockReadiness = {
  status: "ready",
  checks: { database: "up" },
};

describe("SettingsWorkspace Component", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/session/me") {
          return new Response(JSON.stringify(mockUser), { status: 200 });
        }
        if (url === "/api/backend/health/live") {
          return new Response(JSON.stringify(mockLiveness), { status: 200 });
        }
        if (url === "/api/backend/health/ready") {
          return new Response(JSON.stringify(mockReadiness), { status: 200 });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
  });

  test("renders settings header and user account profile by default", async () => {
    render(<SettingsWorkspace />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading settings workspace...");

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    });

    expect(screen.getByDisplayValue("Admin User")).toBeVisible();
    expect(screen.getByDisplayValue("admin@tenant.example")).toBeVisible();
    expect(screen.getByText("administrator")).toBeVisible();
  });

  test("switches between settings tabs cleanly", async () => {
    const user = userEvent.setup();
    render(<SettingsWorkspace />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    });

    // Switch to Tenant Profile
    await user.click(screen.getByRole("tab", { name: /Tenant Profile/ }));
    expect(screen.getByDisplayValue("Acme Corp")).toBeVisible();
    expect(screen.getByDisplayValue("acme-corp")).toBeVisible();

    // Switch to Appearance
    await user.click(screen.getByRole("tab", { name: /Appearance/ }));
    expect(screen.getByRole("radiogroup", { name: "Interface Theme Mode" })).toBeVisible();

    // Switch to Session & Security
    await user.click(screen.getByRole("tab", { name: /Session & Security/ }));
    expect(screen.getByText("Active Session Status")).toBeVisible();
    expect(screen.getByRole("button", { name: /Sign Out/ })).toBeVisible();

    // Switch to System Info
    await user.click(screen.getByRole("tab", { name: /System Info/ }));
    await waitFor(() => {
      expect(screen.getByText("Tenant Intelligence")).toBeVisible();
      expect(screen.getByText("v0.1.0")).toBeVisible();
    });
  });

  test("appearance tab changes theme and updates localStorage", async () => {
    const user = userEvent.setup();
    render(<SettingsWorkspace />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    });

    await user.click(screen.getByRole("tab", { name: /Appearance/ }));

    const darkButton = screen.getByRole("radio", { name: /Dark Mode/ });
    await user.click(darkButton);

    expect(localStorage.getItem("theme")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  test("session sign out opens confirmation modal dialog", async () => {
    const user = userEvent.setup();
    render(<SettingsWorkspace />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    });

    await user.click(screen.getByRole("tab", { name: /Session & Security/ }));
    await user.click(screen.getByRole("button", { name: /Sign Out/ }));

    expect(screen.getByText("Confirm Session Sign Out")).toBeVisible();
    expect(screen.getByText(/Are you sure you want to sign out/)).toBeVisible();
  });

  test("Settings Session & Security sign out executes canonical logout and sets flash toast", async () => {
    sessionStorage.clear();
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <SettingsWorkspace />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    });

    await user.click(screen.getByRole("tab", { name: /Session & Security/ }));
    await user.click(screen.getByRole("button", { name: /Sign Out/ }));

    expect(screen.getByText("Confirm Session Sign Out")).toBeVisible();

    const confirmBtn = screen.getByRole("button", { name: "Yes, Sign Out" });
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(sessionStorage.getItem("app_flash_toast")).toBe("logout_success");
    });
  });

  test("tenant profile fields remain read-only without create/edit actions or tenant selectors", async () => {
    const user = userEvent.setup();
    render(<SettingsWorkspace />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    });

    await user.click(screen.getByRole("tab", { name: /Tenant Profile/ }));

    const nameInput = screen.getByLabelText("Organization Name");
    expect(nameInput).toHaveAttribute("readonly");
    expect(nameInput).toHaveValue("Acme Corp");

    const codeInput = screen.getByLabelText("Tenant Code");
    expect(codeInput).toHaveAttribute("readonly");
    expect(codeInput).toHaveValue("acme-corp");

    expect(screen.queryByRole("button", { name: /Edit Tenant/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Save Tenant/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Create Tenant/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Delete Tenant/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /Select Tenant/i })).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/enter tenant id/i)).not.toBeInTheDocument();

    const scopeNoticeHeading = screen.getByText("Multi-Tenancy Scope Notice");
    expect(scopeNoticeHeading).toBeVisible();

    const noticeParagraph = screen.getByText(/Tenant identity is provisioned and read-only in this release/i);
    expect(noticeParagraph).toBeVisible();
    expect(noticeParagraph.textContent).toContain("Platform Administrator");
    expect(noticeParagraph.textContent).toContain("Tenant Administrator scope");
    expect(noticeParagraph.textContent).toContain("outside the current");
  });
});
