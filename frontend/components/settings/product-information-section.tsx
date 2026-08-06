"use client";

import { Activity, Database, Info, ShieldAlert, Server } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchLivenessInfo, fetchReadinessInfo } from "@/lib/settings-api";
import type { LivenessInfo, ReadinessInfo } from "@/lib/settings-contracts";

export function ProductInformationSection() {
  const [liveness, setLiveness] = useState<LivenessInfo | null>(null);
  const [readiness, setReadiness] = useState<ReadinessInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    Promise.all([fetchLivenessInfo(), fetchReadinessInfo()])
      .then(([liveData, readyData]) => {
        if (mounted) {
          setLiveness(liveData);
          setReadiness(readyData);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section aria-labelledby="product-info-heading" className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h2
          id="product-info-heading"
          className="flex items-center gap-2 text-lg font-semibold text-[var(--text)]"
        >
          <Info className="h-5 w-5 text-[var(--primary)]" aria-hidden />
          Product & System Information
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Application service identity, health status, and build parameters.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <Server className="h-4 w-4 text-[var(--primary)]" aria-hidden />
            Application Service
          </div>
          <p className="mt-2 text-sm font-semibold text-[var(--text)]">
            {liveness?.service ?? "Tenant Intelligence"}
          </p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Multi-Tenant Enterprise Copilot Workspace
          </p>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <Activity className="h-4 w-4 text-[var(--primary)]" aria-hidden />
            Version & Release
          </div>
          <p className="mt-2 text-sm font-semibold text-[var(--text)]">
            v{liveness?.version ?? "0.1.0"}
          </p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Production Build Release
          </p>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <Activity className="h-4 w-4 text-[var(--primary)]" aria-hidden />
            API Service Liveness
          </div>
          <div className="mt-2 flex items-center gap-2">
            {loading ? (
              <span className="text-xs text-[var(--text-muted)]">Checking...</span>
            ) : liveness?.status === "ok" ? (
              <>
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--success,#10b981)]" aria-hidden />
                <span className="text-sm font-medium text-[var(--text)]">Operational</span>
              </>
            ) : (
              <>
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--danger)]" aria-hidden />
                <span className="text-sm font-medium text-[var(--danger)]">Degraded</span>
              </>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <Database className="h-4 w-4 text-[var(--primary)]" aria-hidden />
            Database Readiness
          </div>
          <div className="mt-2 flex items-center gap-2">
            {loading ? (
              <span className="text-xs text-[var(--text-muted)]">Checking...</span>
            ) : readiness?.checks.database === "up" ? (
              <>
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--success,#10b981)]" aria-hidden />
                <span className="text-sm font-medium text-[var(--text)]">Connected</span>
              </>
            ) : (
              <>
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--danger)]" aria-hidden />
                <span className="text-sm font-medium text-[var(--danger)]">Unavailable</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5 rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3.5 py-3 text-xs text-[var(--text-secondary)]">
        <ShieldAlert className="h-4 w-4 shrink-0 text-[var(--text-muted)]" aria-hidden />
        <p>
          Infrastructure connection strings, internal IP addresses, database schemas, and provider keys are protected and withheld from product telemetry.
        </p>
      </div>
    </section>
  );
}
