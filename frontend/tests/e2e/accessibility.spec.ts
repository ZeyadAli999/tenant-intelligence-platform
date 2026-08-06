import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const administrator = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "zeyad.said@tenant-intelligence.example",
  full_name: "Zeyad Said",
  status: "active",
  is_tenant_admin: true,
  tenant: {
    id: "00000000-0000-4000-8000-000000000002",
    name: "Tenant Intelligence",
    code: "tenant-intelligence",
    status: "active",
  },
  roles: [
    {
      id: "00000000-0000-4000-8000-000000000003",
      name: "administrator",
      description: "Tenant Administrator",
    },
  ],
  created_at: "2026-01-01T00:00:00Z",
};

const tenantUser = {
  ...administrator,
  tenant: undefined,
  updated_at: "2026-01-01T00:00:00Z",
};

async function mockApplication(page: Page) {
  await page.route("**/api/platform-status*", (route) =>
    route.fulfill({ json: { live: true, ready: true } }),
  );
  await page.route("**/api/session/me*", (route) =>
    route.fulfill({ json: administrator }),
  );
  await page.route("**/api/backend/**", (route) => {
    const url = route.request().url();
    if (url.includes("/health/")) return route.fulfill({ json: { status: "ok" } });
    if (url.includes("/roles"))
      return route.fulfill({
        json: {
          items: [{ ...administrator.roles[0], created_at: administrator.created_at }],
          total: 1,
          page: 1,
          page_size: 100,
        },
      });
    if (url.includes("/users"))
      return route.fulfill({
        json: { items: [tenantUser], total: 1, page: 1, page_size: 100 },
      });
    return route.fulfill({
      json: { items: [], total: 0, page: 1, page_size: 100 },
    });
  });
}

async function expectNoViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
}

test("core account and administration surfaces pass Axe in light and dark themes", async ({
  page,
}) => {
  await mockApplication(page);

  for (const theme of ["light", "dark"] as const) {
    await page.goto("/login");
    await page.evaluate((value) => {
      localStorage.setItem("theme", value);
    }, theme);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Sign in to Tenant Intelligence" }),
    ).toBeVisible();
    await expectNoViolations(page);
  }

  await page.context().addCookies([
    { name: "ti_access", value: "offline-access", url: page.url() },
  ]);

  for (const theme of ["light", "dark"] as const) {
    await page.evaluate((value) => {
      localStorage.setItem("theme", value);
    }, theme);
    for (const [path, heading] of [
      ["/dashboard", /Welcome back/],
      ["/chat", "Chat workspace"],
      ["/users", "Users"],
      ["/permissions", "Permissions"],
      ["/settings", "Settings"],
    ] as const) {
      await page.goto(path);
      await expect(
        page.getByRole("heading", { name: heading, exact: true }),
      ).toBeVisible();
      await expectNoViolations(page);

      if (path === "/users") {
        await page.getByRole("button", { name: "Open account menu" }).first().click();
        await expect(page.getByRole("menu")).toBeVisible();
        await expectNoViolations(page);
        await page.keyboard.press("Escape");
      }
    }
  }
});
