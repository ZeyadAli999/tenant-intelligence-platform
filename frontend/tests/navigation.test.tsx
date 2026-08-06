import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { AppShell } from "@/components/app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));

const sessionUser = (administrator: boolean) => ({
  id: "00000000-0000-4000-8000-000000000001",
  email: "zeyad.said@tenant-intelligence.example",
  full_name: "Zeyad Said",
  status: "active",
  is_tenant_admin: administrator,
  tenant: {
    id: "00000000-0000-4000-8000-000000000002",
    name: "Tenant Intelligence",
    code: "tenant-intelligence",
    status: "active",
  },
  roles: administrator
    ? [
        {
          id: "00000000-0000-4000-8000-000000000003",
          name: "administrator",
          description: "Tenant Administrator",
        },
      ]
    : [],
  created_at: "2026-01-01T00:00:00Z",
});

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(sessionUser(false)))),
  );
});

test("normal users receive navigation with Settings at bottom and without administration controls", async () => {
  render(
    <AppShell>
      <p>Content</p>
    </AppShell>,
  );
  expect(
    (await screen.findAllByText("zeyad.said@tenant-intelligence.example"))[0],
  ).toBeVisible();

  // Verify Main group navigation items
  const mainNav = screen.getByRole("navigation", { name: "Main" });
  expect(mainNav).toHaveTextContent("Overview");
  expect(mainNav).toHaveTextContent("Chat");
  expect(mainNav).toHaveTextContent("Knowledge");
  expect(mainNav).toHaveTextContent("Databases");
  expect(mainNav).not.toHaveTextContent("Settings");

  // Verify Administration group is absent for normal users
  expect(screen.queryByText("Administration")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument();

  // Verify Settings group is rendered at bottom and accessible
  const settingsNav = screen.getByRole("navigation", { name: "Settings" });
  expect(settingsNav).toHaveTextContent("Settings");
});

test("real Administrators receive navigation, identity, tenant, and badge in proper group order", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(sessionUser(true)))),
  );
  render(
    <AppShell>
      <p>Content</p>
    </AppShell>,
  );

  expect(await screen.findAllByText("Administrator")).not.toHaveLength(0);

  // Verify Administration group
  const adminNav = screen.getByRole("navigation", { name: "Administration" });
  expect(adminNav).toHaveTextContent("Users");
  expect(adminNav).toHaveTextContent("Permissions");
  expect(adminNav).not.toHaveTextContent("Settings");

  // Verify Settings group follows Administration
  const settingsNav = screen.getByRole("navigation", { name: "Settings" });
  expect(settingsNav).toHaveTextContent("Settings");

  await userEvent.click(
    screen.getAllByRole("button", { name: /Open account menu/ })[0],
  );
  expect(screen.getAllByText("Zeyad Said").length).toBeGreaterThan(0);
  expect(screen.getAllByText("zeyad.said@tenant-intelligence.example").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Tenant Intelligence").length).toBeGreaterThan(0);
  await userEvent.keyboard("{Escape}");

  await userEvent.click(screen.getByRole("button", { name: "Open navigation" }));
  expect(screen.getByLabelText("Mobile navigation")).toBeVisible();
  await userEvent.click(screen.getAllByRole("button", { name: "Close navigation" })[1]!);
  expect(screen.queryByLabelText("Mobile navigation")).not.toBeInTheDocument();
});
