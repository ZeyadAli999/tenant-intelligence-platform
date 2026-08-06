import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const validTokens = {
  access_token: "test-access-token",
  refresh_token: "test-refresh-token",
  token_type: "bearer",
  access_token_expires_in: 900,
};

describe("login BFF", () => {
  beforeEach(() => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend.internal:8000");
  });
  afterEach(() => vi.unstubAllEnvs());

  test("creates secure server cookies and returns no tokens", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(validTokens), {
            status: 200,
            headers: {
              "content-type": "application/json",
              "x-request-id": "safe-request-id",
            },
          }),
      ),
    );
    const { POST } = await import("@/app/api/session/login/route");
    const request = new NextRequest("http://frontend.local/api/session/login", {
      method: "POST",
      body: JSON.stringify({
        tenant_code: "demo",
        email: "user@example.com",
        password: "test-password",
      }),
      headers: { "content-type": "application/json" },
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ authenticated: true });
    const cookies = response.headers.get("set-cookie") ?? "";
    expect(cookies).toContain("ti_access=");
    expect(cookies).toContain("ti_refresh=");
    expect(cookies).toMatch(/HttpOnly/i);
    expect(cookies).toMatch(/SameSite=lax/i);
  });

  test("sanitizes failed authentication responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () => new Response("internal backend detail", { status: 401 }),
      ),
    );
    const { POST } = await import("@/app/api/session/login/route");
    const response = await POST(
      new NextRequest("http://frontend.local/api/session/login", {
        method: "POST",
        body: JSON.stringify({
          tenant_code: "demo",
          email: "user@example.com",
          password: "wrong-password",
        }),
      }),
    );
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ message: "Invalid credentials" });
  });

  test("rejects invalid input before contacting the backend", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const { POST } = await import("@/app/api/session/login/route");
    const response = await POST(
      new NextRequest("http://frontend.local/api/session/login", {
        method: "POST",
        body: JSON.stringify({ tenant_code: "", email: "bad", password: "" }),
      }),
    );
    expect(response.status).toBe(400);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

test("backend URL construction cannot be overridden by a request path", async () => {
  vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend.internal:8000");
  const { backendUrl } = await import("@/lib/server/config");
  expect(backendUrl("/api/health/live").origin).toBe(
    "http://backend.internal:8000",
  );
  vi.unstubAllEnvs();
});
