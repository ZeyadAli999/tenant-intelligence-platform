import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const visualOutput = path.resolve(process.cwd(), "visual-test-output");
mkdirSync(visualOutput, { recursive: true });
const responsiveWidths = [1440, 1024, 768, 390];

test("knowledge workspace is accessible and responsive", async ({
  page,
}, testInfo) => {
  // Establish origin URL context first
  await page.goto("/login");

  // Add authentication cookie for current domain
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
          name: "Demo Tenant",
          code: "demo",
          status: "active",
        },
        roles: [],
        created_at: new Date().toISOString(),
      }),
    });
  });

  // Mock backend API endpoints
  await page.route("**/api/backend/knowledge-bases*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "11111111-1111-4111-8111-111111111111",
            name: "Demo Knowledge Base",
            description: "Approved organizational policies and documentation.",
            embedding_model:
              "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            embedding_dimension: 384,
            status: "active",
            created_by: "00000000-0000-0000-0000-000000000000",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    });
  });

  await page.route("**/api/backend/files*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "22222222-2222-4222-8222-222222222222",
            knowledge_base_id: "11111111-1111-4111-8111-111111111111",
            original_name: "Refund_Policy_2025.pdf",
            mime_type: "application/pdf",
            detected_mime_type: "application/pdf",
            extension: ".pdf",
            file_size_bytes: 1048576,
            checksum: "checksum123",
            processing_status: "ready",
            processing_error_code: null,
            processing_error_message: null,
            processing_attempts: 1,
            page_count: 12,
            extracted_text_length: 4500,
            chunk_count: 8,
            ingestion_version: 1,
            active_ingestion_version: 1,
            created_at: new Date().toISOString(),
            processing_started_at: new Date().toISOString(),
            processed_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    });
  });

  await page.goto("/knowledge");

  // Verify header & content
  await expect(
    page.getByRole("heading", { name: "Knowledge Bases" }),
  ).toBeVisible();
  await expect(page.getByText("Demo Knowledge Base")).toBeVisible();

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
    path: path.join(visualOutput, `knowledge-${testInfo.project.name}.png`),
    fullPage: true,
  });

  // Perform Axe Accessibility Audit
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
