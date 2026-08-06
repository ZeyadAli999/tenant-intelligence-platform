import {
  livenessResponseSchema,
  readinessResponseSchema,
  type LivenessInfo,
  type ReadinessInfo,
} from "@/lib/settings-contracts";
import { currentUserSchema, type CurrentUser } from "@/lib/contracts";

export async function fetchCurrentIdentity(): Promise<CurrentUser | null> {
  const res = await fetch("/api/session/me", { cache: "no-store" });
  if (!res.ok) return null;
  const data = await res.json().catch(() => null);
  const parsed = currentUserSchema.safeParse(data);
  return parsed.success ? parsed.data : null;
}

export async function fetchLivenessInfo(): Promise<LivenessInfo | null> {
  const res = await fetch("/api/backend/health/live", { cache: "no-store" });
  if (!res.ok) return null;
  const data = await res.json().catch(() => null);
  const parsed = livenessResponseSchema.safeParse(data);
  return parsed.success ? parsed.data : null;
}

export async function fetchReadinessInfo(): Promise<ReadinessInfo | null> {
  const res = await fetch("/api/backend/health/ready", { cache: "no-store" });
  if (!res.ok) return null;
  const data = await res.json().catch(() => null);
  const parsed = readinessResponseSchema.safeParse(data);
  return parsed.success ? parsed.data : null;
}
