import { NextRequest, NextResponse } from "next/server";
import { loginSchema, tokenResponseSchema } from "@/lib/contracts";
import { backendUrl } from "@/lib/server/config";
import { safeBackendMessage, safeError } from "@/lib/server/responses";
import { setSessionCookies } from "@/lib/server/session";

export async function POST(request: NextRequest) {
  const parsed = loginSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success)
    return safeError(400, "Check the highlighted fields and try again.");
  try {
    const upstream = await fetch(backendUrl("/api/auth/login"), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-request-id": crypto.randomUUID(),
      },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    const requestId = upstream.headers.get("x-request-id");
    if (!upstream.ok)
      return safeError(
        upstream.status,
        safeBackendMessage(upstream.status),
        requestId,
      );
    const tokens = tokenResponseSchema.parse(await upstream.json());
    const response = NextResponse.json({ authenticated: true });
    setSessionCookies(response, tokens);
    return response;
  } catch {
    return safeError(503, "The sign-in service is temporarily unavailable.");
  }
}
