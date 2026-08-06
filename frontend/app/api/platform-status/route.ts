import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/server/config";

export async function GET() {
  try {
    const [live, ready] = await Promise.all([
      fetch(backendUrl("/api/health/live"), {
        cache: "no-store",
        signal: AbortSignal.timeout(5_000),
      }),
      fetch(backendUrl("/api/health/ready"), {
        cache: "no-store",
        signal: AbortSignal.timeout(5_000),
      }),
    ]);
    return NextResponse.json(
      { live: live.ok, ready: ready.ok },
      { status: live.ok && ready.ok ? 200 : 503 },
    );
  } catch {
    return NextResponse.json({ live: false, ready: false }, { status: 503 });
  }
}
