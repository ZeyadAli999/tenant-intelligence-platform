import { NextRequest } from "next/server";
import { beforeEach, expect, test, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) =>
      name === "ti_access" ? { value: "server-access" } : undefined,
  })),
}));

beforeEach(() => {
  vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend.internal:8000");
});

test("admin proxy contracts stay allowlisted and preserve a safe 403 code", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    expect(String(input)).toBe(
      "http://backend.internal:8000/api/users?page=1&page_size=100&search=zeyad&status=active",
    );
    return new Response(
      JSON.stringify({
        detail: "Administrator access required",
        code: "ADMINISTRATOR_REQUIRED",
      }),
      { status: 403 },
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  const route = await import("@/app/api/backend/[...path]/route");

  expect(route.resolveContract("POST", ["users"])).not.toBeNull();
  expect(route.resolveContract("GET", ["roles"])).not.toBeNull();
  expect(
    route.resolveContract("PUT", [
      "users",
      "00000000-0000-4000-8000-000000000001",
    ]),
  ).not.toBeNull();
  expect(
    route.resolveContract("PUT", [
      "users",
      "00000000-0000-4000-8000-000000000001",
      "roles",
    ]),
  ).not.toBeNull();

  const request = new NextRequest(
    "http://frontend.local/api/backend/users?page=1&page_size=100&search=zeyad&status=active",
    { headers: { host: "frontend.local" } },
  );
  const response = await route.GET(request, {
    params: Promise.resolve({ path: ["users"] }),
  });

  expect(response.status).toBe(403);
  expect(await response.json()).toEqual({
    error: "You do not have permission to perform this action.",
    code: "ADMINISTRATOR_REQUIRED",
  });
});

test.each([
  [409, "FINAL_ACTIVE_ADMINISTRATOR_REQUIRED", "FINAL_ACTIVE_ADMINISTRATOR_REQUIRED"],
  [409, "UNKNOWN_CONFLICT", undefined],
  [403, "UNKNOWN_DENIAL", undefined],
] as const)(
  "sanitizes status %s and allowlists only the expected machine code",
  async (status, upstreamCode, expectedCode) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail: "sensitive backend detail must not escape",
            code: upstreamCode,
          }),
          { status },
        ),
      ),
    );
    const route = await import("@/app/api/backend/[...path]/route");
    const response = await route.PUT(
      new NextRequest(
        "http://frontend.local/api/backend/users/00000000-0000-4000-8000-000000000001",
        {
          method: "PUT",
          headers: {
            host: "frontend.local",
            origin: "http://frontend.local",
            "content-type": "application/json",
          },
          body: JSON.stringify({ status: "inactive", role_ids: [] }),
        },
      ),
      {
        params: Promise.resolve({
          path: ["users", "00000000-0000-4000-8000-000000000001"],
        }),
      },
    );
    const body = await response.json();
    expect(response.status).toBe(status);
    expect(body).toEqual({
      error:
        status === 409
          ? "This item already exists."
          : "You do not have permission to perform this action.",
      ...(expectedCode ? { code: expectedCode } : {}),
    });
    expect(JSON.stringify(body)).not.toContain("sensitive backend detail");
  },
);
