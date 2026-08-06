import { beforeEach, expect, test, vi } from "vitest";

const cookieValues = new Map([
  ["ti_access", "expired-access"],
  ["ti_refresh", "valid-refresh"],
]);
const cookiesMock = vi.fn(async () => ({
  get: (name: string) => {
    const value = cookieValues.get(name);
    return value ? { value } : undefined;
  },
}));
vi.mock("next/headers", () => ({ cookies: cookiesMock }));

beforeEach(() => {
  vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend.internal:8000");
  cookieValues.set("ti_access", "expired-access");
  cookieValues.set("ti_refresh", "valid-refresh");
});

test("refreshes once and retries the original request once", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          access_token: "new-access",
          refresh_token: "new-refresh",
          token_type: "bearer",
          access_token_expires_in: 900,
        }),
        { status: 200 },
      ),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetchMock);
  const { authenticatedFetch } = await import("@/lib/server/session");
  const result = await authenticatedFetch("/api/auth/me");
  expect(result.upstream?.status).toBe(200);
  expect(result.refreshedTokens).not.toBeNull();
  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(
    new Headers(fetchMock.mock.calls[2]?.[1]?.headers).get("authorization"),
  ).toBe("Bearer new-access");
});

test("failed refresh ends without an infinite retry", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(new Response(null, { status: 401 }));
  vi.stubGlobal("fetch", fetchMock);
  const { authenticatedFetch } = await import("@/lib/server/session");
  const result = await authenticatedFetch("/api/auth/me");
  expect(result.upstream).toBeNull();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
