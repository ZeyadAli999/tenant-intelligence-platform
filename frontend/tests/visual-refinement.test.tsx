import { readFileSync } from "node:fs";
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import LoginPage from "@/app/login/page";
import {
  CapabilitySections,
  SecurityControlList,
  SystemStatusStrip,
  WorkflowSteps,
  WorkspaceHeader,
} from "@/components/dashboard-sections";
import { FeatureEmptyPage } from "@/components/feature-empty-page";
import { PlatformStatus } from "@/components/platform-status";
import { ProductIdentity } from "@/components/product-identity";
import type { CurrentUser } from "@/lib/contracts";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));
const user: CurrentUser = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "user@example.com",
  full_name: "Workspace User",
  status: "active",
  is_tenant_admin: true,
  tenant: {
    id: "00000000-0000-4000-8000-000000000002",
    name: "Example Workspace",
    code: "example",
    status: "active",
  },
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
};

test("product identity renders an accessible wordmark and decorative vector monogram", () => {
  const { container } = render(<ProductIdentity />);
  expect(screen.getByLabelText("Tenant Intelligence")).toBeVisible();
  expect(screen.getByText("Secure intelligence workspace")).toBeVisible();
  expect(container.querySelector("svg")).toBeTruthy();
  expect(container.querySelector("[aria-hidden='true'] svg")).toBeTruthy();
});
test("login uses the structured capability composition", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("{}", { status: 200 })),
  );
  render(<LoginPage />);
  expect(
    screen.getByText(
      "Work confidently across organizational data and documents.",
    ),
  ).toBeVisible();
  expect(
    screen.getByText("Ask databases and documents in natural language"),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Sign in to Tenant Intelligence" }),
  ).toBeVisible();
});
test("real platform status represents a ready response", async () => {
  const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  render(<PlatformStatus />);
  expect(await screen.findByText("Platform ready")).toBeVisible();
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith("/api/platform-status", {
      cache: "no-store",
    }),
  );
});
test("dashboard workspace header and status strip show identity and status labels", () => {
  render(
    <>
      <WorkspaceHeader user={user} ready />
      <SystemStatusStrip live ready />
    </>,
  );
  expect(screen.getByText("Example Workspace")).toBeVisible();
  expect(screen.getByRole("heading", { name: /Welcome back/ })).toBeVisible();
  expect(screen.getByText("Frontend")).toBeVisible();
  expect(screen.getByText("Platform ready")).toBeVisible();
});
test("dashboard renders workflow and capability areas", () => {
  render(
    <>
      <WorkflowSteps />
      <CapabilitySections />
    </>,
  );
  expect(
    screen.getByRole("heading", { name: "How Tenant Intelligence works" }),
  ).toBeVisible();
  expect(screen.getByText("Validate access")).toBeVisible();
  expect(screen.getByText("Conversational intelligence")).toBeVisible();
  expect(screen.getByText("Security and governance")).toBeVisible();
});
test("security controls describe verified backend boundaries", () => {
  render(<SecurityControlList />);
  expect(screen.getByText("Tenant isolation")).toBeVisible();
  expect(screen.getByText("Read-only SQL validation")).toBeVisible();
  expect(screen.getByText("Sensitive-column masking")).toBeVisible();
});
test("refined empty routes remain honest", () => {
  render(
    <FeatureEmptyPage
      title="Chat"
      description="Governed chat"
      capabilities={["Hybrid conversations"]}
      securityNote="Tenant scoped."
    />,
  );
  expect(screen.getByText("Upcoming chat workspace")).toBeVisible();
  expect(screen.getByText(/Structural preview only/)).toBeVisible();
  expect(screen.getByText("Hybrid conversations")).toBeVisible();
});
test("light and dark semantic tokens include refined surfaces", () => {
  const css = readFileSync("app/globals.css", "utf8");
  for (const token of [
    "--sidebar",
    "--surface-elevated",
    "--border-strong",
    "--nav-selected",
    "--code-surface",
    "--disabled-opacity",
  ])
    expect(css).toContain(token);
  expect(css).toContain('[data-theme="dark"]');
  expect(css).toContain("@media (prefers-reduced-motion: no-preference)");
  expect(css).toContain("--focus: #1d4ed8");
  expect(css).toContain("--focus: #93c5fd");
});
