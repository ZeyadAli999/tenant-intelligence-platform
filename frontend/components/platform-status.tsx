"use client";
import { CheckCircle2, CircleAlert, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

type Status = "loading" | "ready" | "unavailable";
export function PlatformStatus({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<Status>("loading");
  useEffect(() => {
    fetch("/api/platform-status", { cache: "no-store" })
      .then((response) => setStatus(response.ok ? "ready" : "unavailable"))
      .catch(() => setStatus("unavailable"));
  }, []);
  const Icon =
    status === "loading"
      ? LoaderCircle
      : status === "ready"
        ? CheckCircle2
        : CircleAlert;
  const label =
    status === "loading"
      ? "Checking platform readiness"
      : status === "ready"
        ? "Platform ready"
        : "Platform temporarily unavailable";
  return (
    <div
      role="status"
      className={`inline-flex items-center gap-2 ${compact ? "text-xs" : "text-sm"} text-[var(--text-secondary)]`}
    >
      <Icon
        aria-hidden
        className={`h-4 w-4 ${status === "ready" ? "text-[var(--success)]" : status === "unavailable" ? "text-[var(--danger)]" : "animate-spin text-[var(--text-muted)] motion-reduce:animate-none"}`}
      />
      <span>{label}</span>
    </div>
  );
}
