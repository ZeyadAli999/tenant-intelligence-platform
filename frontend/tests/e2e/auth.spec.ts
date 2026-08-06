import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const visualOutput = path.resolve(process.cwd(), "visual-test-output");
mkdirSync(visualOutput, { recursive: true });
const responsiveWidths = [1440, 1280, 1024, 768, 390, 360];

test("validates login fields and remains accessible", async ({
  page,
}, testInfo) => {
  await page.route("**/api/platform-status*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ live: true, ready: true }),
    });
  });
  await page.goto("/login");
  await page.screenshot({
    path: path.join(visualOutput, `login-${testInfo.project.name}.png`),
    fullPage: true,
  });
  await expect(page.locator("main > section")).toHaveCount(2);
  if (testInfo.project.name === "desktop")
    await expect(
      page.getByText("Ask databases and documents in natural language"),
    ).toBeVisible();
  await expect(
    page
      .getByText("Platform ready")
      .nth(testInfo.project.name === "desktop" ? 0 : 1),
  ).toBeVisible();
  for (const width of responsiveWidths) {
    await page.setViewportSize({ width, height: width <= 390 ? 800 : 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
  }
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Tenant code is required")).toBeVisible();
  await expect(page.getByText("Enter a valid email address")).toBeVisible();
  await expect(page.getByText("Password is required")).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
test("real disposable identity signs in, persists, navigates, and signs out", async ({
  page,
  context,
}, testInfo) => {
  const tenant = process.env.E2E_TENANT_CODE;
  const email = process.env.E2E_USER_EMAIL;
  const password = process.env.E2E_USER_PASSWORD;
  test.skip(
    !tenant || !email || !password,
    "Disposable backend identity not configured",
  );
  await page.goto("/login");
  await page.getByLabel("Tenant code").fill(tenant!);
  await page.getByLabel("Email address").fill(email!);
  await page.getByRole("textbox", { name: "Password" }).fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "How Tenant Intelligence works" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Capability areas" }),
  ).toBeVisible();
  const dashboardAccessibility = await new AxeBuilder({ page }).analyze();
  expect(dashboardAccessibility.violations).toEqual([]);
  for (const width of responsiveWidths) {
    await page.setViewportSize({ width, height: width <= 390 ? 800 : 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
  }
  await page.setViewportSize(
    testInfo.project.name === "desktop"
      ? { width: 1440, height: 1000 }
      : { width: 390, height: 844 },
  );
  const cookies = await context.cookies();
  expect(
    cookies
      .filter((c) => c.name.includes("ti_"))
      .every((c) => c.httpOnly && c.sameSite === "Lax"),
  ).toBeTruthy();
  const accessCookie = cookies.find((cookie) => cookie.name === "ti_access");
  expect(accessCookie).toBeDefined();
  await context.addCookies([
    { ...accessCookie!, value: "expired-access-test-value" },
  ]);
  expect(
    await page.evaluate(async () => (await fetch("/api/session/me")).status),
  ).toBe(200);
  const rotatedAccess = (await context.cookies()).find(
    (cookie) => cookie.name === "ti_access",
  );
  expect(rotatedAccess?.value).not.toBe("expired-access-test-value");
  const identityMasks = [page.getByText(email!, { exact: true })];
  if (testInfo.project.name === "desktop") {
    await page.screenshot({
      path: path.join(visualOutput, "dashboard-desktop.png"),
      fullPage: true,
      mask: identityMasks,
    });
    await page.getByRole("button", { name: /Theme: system/ }).click();
    await page.getByRole("button", { name: /Theme: light/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.screenshot({
      path: path.join(visualOutput, "dashboard-dark.png"),
      fullPage: true,
      mask: identityMasks,
    });
  } else {
    await page.screenshot({
      path: path.join(visualOutput, "dashboard-mobile.png"),
      fullPage: true,
      mask: identityMasks,
    });
  }
  await page.reload();
  await expect(page).toHaveURL(/\/dashboard/);
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page
      .getByLabel("Mobile navigation")
      .getByRole("link", { name: "Knowledge" })
      .click();
  } else {
    await page.getByRole("link", { name: "Knowledge" }).first().click();
  }
  await expect(
    page.getByRole("heading", { name: "Knowledge Bases", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Open account menu/ }).click();
  await page.getByText("Sign out").click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
  const browserStorage = await page.evaluate(() => ({
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage),
  }));
  expect(browserStorage.session).toEqual([]);
  expect(browserStorage.local.every((key) => key === "theme")).toBeTruthy();
});
test("mobile viewport remains usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: "Sign in to Tenant Intelligence" }),
  ).toBeVisible();
});

test("real empty chat workspace is responsive and accessible", async ({
  page,
}, testInfo) => {
  const tenant = process.env.E2E_TENANT_CODE;
  const email = process.env.E2E_USER_EMAIL;
  const password = process.env.E2E_USER_PASSWORD;
  test.skip(
    !tenant || !email || !password,
    "Disposable backend identity not configured",
  );
  await page.goto("/login");
  await page.getByLabel("Tenant code").fill(tenant!);
  await page.getByLabel("Email address").fill(email!);
  await page.getByRole("textbox", { name: "Password" }).fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await page.goto("/chat");
  await expect(
    page.getByRole("heading", { name: "Chat workspace", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No active conversation" }),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Message" })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "New conversation" }).last(),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Open response details" }).click();
    await expect(
      page.getByRole("complementary", { name: "Response details" }),
    ).toBeVisible();
    await page
      .getByRole("complementary", { name: "Response details" })
      .getByRole("button", { name: "Close response details" })
      .click();
    await page.getByRole("button", { name: "Open conversations" }).click();
    await expect(
      page.getByRole("complementary", { name: "Conversations" }),
    ).toBeVisible();
    await page
      .getByRole("complementary", { name: "Conversations" })
      .getByRole("button", { name: "Close conversations" })
      .click();
    await page.getByRole("button", { name: "Open response details" }).click();
    await expect(
      page.getByRole("complementary", { name: "Response details" }),
    ).toBeVisible();
  }
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
