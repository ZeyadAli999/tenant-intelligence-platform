import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/server/session";

const protectedPrefixes = [
  "/dashboard",
  "/chat",
  "/knowledge",
  "/databases",
  "/users",
  "/permissions",
  "/settings",
];

export function proxy(request: NextRequest) {
  const protectedRoute = protectedPrefixes.some((prefix) =>
    request.nextUrl.pathname.startsWith(prefix),
  );
  if (!protectedRoute) return NextResponse.next();
  if (request.cookies.has(ACCESS_COOKIE) || request.cookies.has(REFRESH_COOKIE))
    return NextResponse.next();
  const login = new URL("/login", request.url);
  login.searchParams.set("reason", "session-required");
  return NextResponse.redirect(login);
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/chat/:path*",
    "/knowledge/:path*",
    "/databases/:path*",
    "/users/:path*",
    "/permissions/:path*",
    "/settings/:path*",
  ],
};
