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

test("normal users receive navigation without administration controls", async () => {
  render(
    <AppShell>
      <p>Content</p>
    </AppShell>,
  );
  expect(
    (await screen.findAllByText("zeyad.said@tenant-intelligence.example"))[0],
  ).toBeVisible();
  expect(screen.getAllByRole("link", { name: "Overview" }).length).toBeGreaterThan(0);
  expect(screen.queryByText("Administration")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument();
});

test("real Administrators receive navigation, identity, tenant, and badge", async () => {
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
  expect(screen.getAllByRole("link", { name: "Users" }).length).toBeGreaterThan(0);
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
