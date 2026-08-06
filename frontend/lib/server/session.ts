import "server-only";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { tokenResponseSchema } from "@/lib/contracts";
import { backendUrl } from "@/lib/server/config";

export const ACCESS_COOKIE = "ti_access";
export const REFRESH_COOKIE = "ti_refresh";

const cookieBase = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure:
    process.env.NODE_ENV === "production" &&
    process.env.COOKIE_SECURE !== "false",
  path: "/",
};

export function setSessionCookies(
  response: NextResponse,
  value: unknown,
): void {
  const tokens = tokenResponseSchema.parse(value);
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    ...cookieBase,
    maxAge: tokens.access_token_expires_in,
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    ...cookieBase,
    maxAge: 30 * 24 * 60 * 60,
  });
}

export function clearSessionCookies(response: NextResponse): void {
  response.cookies.set(ACCESS_COOKIE, "", { ...cookieBase, maxAge: 0 });
  response.cookies.set(REFRESH_COOKIE, "", { ...cookieBase, maxAge: 0 });
}

async function refreshSession(): Promise<{
  access: string;
  tokens: unknown;
} | null> {
  const store = await cookies();
  const refresh = store.get(REFRESH_COOKIE)?.value;
  if (!refresh) return null;
  const result = await fetch(backendUrl("/api/auth/refresh"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (!result.ok) return null;
  const tokens = tokenResponseSchema.parse(await result.json());
  return { access: tokens.access_token, tokens };
}

export async function authenticatedFetch(path: string, init: RequestInit = {}) {
  const store = await cookies();
  let access = store.get(ACCESS_COOKIE)?.value;
  let refreshedTokens: unknown = null;

  if (!access) {
    const refreshed = await refreshSession();
    if (!refreshed) return { upstream: null, refreshedTokens: null };
    access = refreshed.access;
    refreshedTokens = refreshed.tokens;
  }

  const send = (token: string) =>
    fetch(backendUrl(path), {
      ...init,
      headers: authorizedHeaders(init.headers, token),
      cache: "no-store",
      signal: init.signal ?? AbortSignal.timeout(10_000),
    });

  let upstream = await send(access);
  if (upstream.status === 401 && !refreshedTokens) {
    const refreshed = await refreshSession();
    if (!refreshed) return { upstream: null, refreshedTokens: null };
    upstream = await send(refreshed.access);
    refreshedTokens = refreshed.tokens;
  }

  return { upstream, refreshedTokens };
}

function authorizedHeaders(source: HeadersInit | undefined, token: string) {
  const headers = new Headers(source);
  headers.delete("authorization");
  headers.delete("cookie");
  headers.set("authorization", `Bearer ${token}`);
  return headers;
}
