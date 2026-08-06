import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { AppShell } from "@/components/app-shell";
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));
vi.stubGlobal(
  "fetch",
  vi.fn(
    async () =>
      new Response(
        JSON.stringify({
          id: "00000000-0000-4000-8000-000000000001",
          email: "user@example.com",
          full_name: "User",
          status: "active",
          is_tenant_admin: false,
          tenant: {
            id: "00000000-0000-4000-8000-000000000002",
            name: "Tenant",
            code: "tenant",
            status: "active",
          },
          roles: [],
          created_at: "2026-01-01T00:00:00Z",
        }),
        { status: 200 },
      ),
  ),
);
test("renders sidebar and accessible mobile navigation", async () => {
  render(
    <AppShell>
      <p>Content</p>
    </AppShell>,
  );
  expect(
    screen.getAllByRole("link", { name: "Overview" }).length,
  ).toBeGreaterThan(0);
  expect(screen.getAllByText("Main").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Administration").length).toBeGreaterThan(0);
  await userEvent.click(
    screen.getByRole("button", { name: "Open navigation" }),
  );
  expect(screen.getByLabelText("Mobile navigation")).toBeVisible();
  await userEvent.click(
    screen.getAllByRole("button", { name: "Close navigation" })[1]!,
  );
  expect(screen.queryByLabelText("Mobile navigation")).not.toBeInTheDocument();
});
