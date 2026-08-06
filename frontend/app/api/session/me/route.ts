import { NextResponse } from "next/server";
import { currentUserSchema } from "@/lib/contracts";
import { safeBackendMessage, safeError } from "@/lib/server/responses";
import {
  authenticatedFetch,
  clearSessionCookies,
  setSessionCookies,
} from "@/lib/server/session";

export async function GET() {
  try {
    const { upstream, refreshedTokens } =
      await authenticatedFetch("/api/auth/me");
    if (!upstream) {
      const response = safeError(
        401,
        "Your session has expired. Please sign in again.",
      );
      clearSessionCookies(response);
      return response;
    }
    if (!upstream.ok)
      return safeError(
        upstream.status,
        safeBackendMessage(upstream.status),
        upstream.headers.get("x-request-id"),
      );
    const response = NextResponse.json(
      currentUserSchema.parse(await upstream.json()),
    );
    if (refreshedTokens) setSessionCookies(response, refreshedTokens);
    return response;
  } catch {
    return safeError(503, "The workspace service is temporarily unavailable.");
  }
}
