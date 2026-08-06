import { NextResponse } from "next/server";
import { clearSessionCookies } from "@/lib/server/session";

export async function POST() {
  const response = NextResponse.json({ authenticated: false });
  clearSessionCookies(response);
  return response;
}
