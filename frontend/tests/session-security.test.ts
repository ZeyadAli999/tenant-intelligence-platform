import { NextResponse } from "next/server";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  clearSessionCookies,
  setSessionCookies,
} from "@/lib/server/session";

const tokens = {
  access_token: "access-test-value",
  refresh_token: "refresh-test-value",
  token_type: "bearer",
  access_token_expires_in: 900,
};
test("sets separate HttpOnly session cookies without token response fields", () => {
  const response = NextResponse.json({ authenticated: true });
  setSessionCookies(response, tokens);
  const header = response.headers.get("set-cookie")!;
  expect(header).toContain(ACCESS_COOKIE);
  expect(header).toContain(REFRESH_COOKIE);
  expect(header).toMatch(/HttpOnly/i);
  expect(header).toMatch(/SameSite=lax/i);
  expect(response.body).toBeTruthy();
});
test("logout expires both cookies", () => {
  const response = NextResponse.json({ authenticated: false });
  clearSessionCookies(response);
  const header = response.headers.get("set-cookie")!;
  expect(header).toContain(ACCESS_COOKIE);
  expect(header).toContain(REFRESH_COOKIE);
  expect(header).toMatch(/Max-Age=0/i);
});
