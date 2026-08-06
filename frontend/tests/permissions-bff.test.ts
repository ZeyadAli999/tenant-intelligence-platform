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

test("permissions proxy contracts stay allowlisted and reject invalid parameters", async () => {
  const permId = "11111111-1111-4111-8111-111111111111";
  const route = await import("@/app/api/backend/[...path]/route");

  expect(route.resolveContract("GET", ["permissions", "tables"])).toEqual({
    path: "permissions/tables",
    query: new Set([
      "page",
      "page_size",
      "connection_id",
      "table_id",
      "user_id",
      "role_id",
    ]),
  });

  expect(route.resolveContract("POST", ["permissions", "tables"])).toEqual({
    path: "permissions/tables",
    query: new Set(),
  });

  expect(route.resolveContract("GET", ["permissions", "tables", permId])).toEqual({
    path: `permissions/tables/${permId}`,
    query: new Set(),
  });

  expect(route.resolveContract("PUT", ["permissions", "tables", permId])).toEqual({
    path: `permissions/tables/${permId}`,
    query: new Set(),
  });

  expect(
    route.resolveContract("DELETE", ["permissions", "tables", permId]),
  ).toEqual({
    path: `permissions/tables/${permId}`,
    query: new Set(),
  });

  expect(
    route.resolveContract("GET", ["permissions", "tables", permId, "columns"]),
  ).toEqual({
    path: `permissions/tables/${permId}/columns`,
    query: new Set(),
  });

  expect(
    route.resolveContract("PUT", ["permissions", "tables", permId, "columns"]),
  ).toEqual({
    path: `permissions/tables/${permId}/columns`,
    query: new Set(),
  });

  // Rejects invalid UUID in path
  expect(
    route.resolveContract("GET", ["permissions", "tables", "invalid-uuid"]),
  ).toBeNull();

  // Rejects invalid HTTP method
  expect(
    route.resolveContract("PATCH", ["permissions", "tables", permId]),
  ).toBeNull();
});

test("permissions proxy rejects unknown query parameters", async () => {
  const route = await import("@/app/api/backend/[...path]/route");
  const request = new NextRequest(
    "http://frontend.local/api/backend/permissions/tables?page=1&unsupported_param=1",
    { headers: { host: "frontend.local" } },
  );

  const response = await route.GET(request, {
    params: Promise.resolve({ path: ["permissions", "tables"] }),
  });

  expect(response.status).toBe(400);
  expect(await response.json()).toEqual({
    error: "Invalid proxy parameters",
  });
});
