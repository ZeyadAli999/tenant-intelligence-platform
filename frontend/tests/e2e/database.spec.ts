import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const visualOutput = path.resolve(process.cwd(), "visual-test-output");
mkdirSync(visualOutput, { recursive: true });
const responsiveWidths = [1440, 1024, 768, 390];

test("database workspace is accessible and responsive", async ({
  page,
}, testInfo) => {
  // Establish origin URL context first
  await page.goto("/login");

  // Add authentication cookie for 127.0.0.1 domain
  await page.context().addCookies([
    {
      name: "ti_access",
      value: "mock-access-token",
      url: page.url(),
    },
  ]);

  // Mock platform status endpoint
  await page.route("**/api/platform-status*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ live: true, ready: true }),
    });
  });

  // Mock session/me user endpoint
  await page.route("**/api/session/me*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "00000000-0000-0000-0000-000000000000",
        email: "admin@example.com",
        full_name: "Admin User",
        status: "active",
        is_tenant_admin: true,
        tenant: {
          id: "00000000-0000-0000-0000-000000000000",
          name: "Example Tenant",
          code: "demo",
          status: "active",
        },
        roles: [],
        created_at: new Date().toISOString(),
      }),
    });
  });

  // Mock database connection list API
  await page.route("**/api/backend/database-connections*", async (route) => {
    if (
      route.request().url().includes("schemas") ||
      route.request().url().includes("tables")
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "11111111-1111-4111-8111-111111111111",
            name: "Production PostgreSQL DB",
            database_type: "postgresql",
            host: "postgres.internal",
            port: 5432,
            database_name: "production_db",
            username: "readonly_user",
            ssl_enabled: true,
            status: "connected",
            last_tested_at: new Date().toISOString(),
            last_test_message: "Connection test succeeded",
            schema_sync_status: "succeeded",
            last_schema_sync_at: new Date().toISOString(),
            is_active: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
      }),
    });
  });

  await page.goto("/databases");

  // Verify page heading and content
  await expect(
    page.getByRole("heading", { name: "Database Connections" }),
  ).toBeVisible();
  await expect(page.getByText("Production PostgreSQL DB")).toBeVisible();

  // Test responsiveness across viewports
  for (const width of responsiveWidths) {
    await page.setViewportSize({ width, height: width <= 390 ? 800 : 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
  }

  // Take screenshot for visual audit
  await page.screenshot({
    path: path.join(visualOutput, `database-${testInfo.project.name}.png`),
    fullPage: true,
  });

  // Perform Axe Accessibility Audit
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
