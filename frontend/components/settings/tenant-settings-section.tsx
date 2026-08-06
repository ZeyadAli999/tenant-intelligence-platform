"use client";

import { Building2, CheckCircle2, Lock, ShieldAlert } from "lucide-react";
import type { CurrentUser } from "@/lib/contracts";

export function TenantSettingsSection({ user }: { user: CurrentUser | null }) {
  const tenant = user?.tenant;
  const isTenantAdmin = user?.is_tenant_admin ?? false;

  return (
    <section aria-labelledby="tenant-settings-heading" className="space-y-6">
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
        <div>
          <h2
            id="tenant-settings-heading"
            className="flex items-center gap-2 text-lg font-semibold text-[var(--text)]"
          >
            <Building2 className="h-5 w-5 text-[var(--primary)]" aria-hidden />
            Tenant Profile
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Organization identity and workspace isolation context.
          </p>
        </div>
        {isTenantAdmin ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[color-mix(in_srgb,var(--primary)_35%,var(--border))] bg-[color-mix(in_srgb,var(--primary)_8%,var(--surface))] px-3 py-1 text-xs font-medium text-[var(--primary)]">
            <Lock className="h-3 w-3" aria-hidden />
            Administrator Access
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
            <Lock className="h-3 w-3" aria-hidden />
            Read-only Member
          </span>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <label
              htmlFor="tenant-name-input"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]"
            >
              Organization Name
            </label>
            <span className="rounded bg-[var(--surface-subtle)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
              Read-only
            </span>
          </div>
          <input
            id="tenant-name-input"
            type="text"
            readOnly
            value={tenant?.name ?? "Loading tenant..."}
            className="mt-2 w-full rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-2 text-sm font-medium text-[var(--text)] outline-none"
          />
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <label
              htmlFor="tenant-code-input"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]"
            >
              Tenant Code
            </label>
            <span className="rounded bg-[var(--surface-subtle)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
              Read-only
            </span>
          </div>
          <input
            id="tenant-code-input"
            type="text"
            readOnly
            value={tenant?.code ?? "loading-code"}
            className="mt-2 w-full font-mono text-sm font-medium text-[var(--text)] rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-2 outline-none"
          />
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Workspace Status
          </p>
          <div className="mt-2 flex items-center gap-2">
            <CheckCircle2
              className="h-4 w-4 text-[var(--success,#10b981)]"
              aria-hidden
            />
            <span className="text-sm font-medium capitalize text-[var(--text)]">
              {tenant?.status ?? "active"}
            </span>
          </div>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Tenant Unique Identifier
          </p>
          <p className="mt-2 truncate font-mono text-xs text-[var(--text-secondary)]">
            {tenant?.id ?? "00000000-0000-0000-0000-000000000000"}
          </p>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] p-3.5 text-xs text-[var(--text-secondary)]">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-[var(--primary)]" aria-hidden />
        <div>
          <p className="font-semibold text-[var(--text)]">
            Multi-Tenancy Scope Notice
          </p>
          <p className="mt-0.5 leading-relaxed">
            Tenant identity is provisioned and read-only in this release. Tenant UUID and
            tenant code are canonical isolation identifiers derived from trusted backend
            context. Creating or changing organizations requires a separate audited
            Platform Administrator workflow and is intentionally outside the current
            Tenant Administrator scope.
          </p>
        </div>
      </div>
    </section>
  );
}
