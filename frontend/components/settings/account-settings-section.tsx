"use client";

import { Info, ShieldCheck, User } from "lucide-react";
import type { CurrentUser } from "@/lib/contracts";

export function AccountSettingsSection({ user }: { user: CurrentUser | null }) {
  const formattedDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "Unknown date";

  return (
    <section aria-labelledby="account-settings-heading" className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h2
          id="account-settings-heading"
          className="flex items-center gap-2 text-lg font-semibold text-[var(--text)]"
        >
          <User className="h-5 w-5 text-[var(--primary)]" aria-hidden />
          Account Profile
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Authenticated identity and security roles assigned to your account.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <label
              htmlFor="account-fullname-input"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]"
            >
              Full Name
            </label>
            <span className="rounded bg-[var(--surface-subtle)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
              Read-only
            </span>
          </div>
          <input
            id="account-fullname-input"
            type="text"
            readOnly
            value={user?.full_name ?? "Not specified"}
            className="mt-2 w-full rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-2 text-sm font-medium text-[var(--text)] outline-none"
          />
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <label
              htmlFor="account-email-input"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]"
            >
              Email Address
            </label>
            <span className="rounded bg-[var(--surface-subtle)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
              Read-only
            </span>
          </div>
          <input
            id="account-email-input"
            type="email"
            readOnly
            value={user?.email ?? "loading@example.com"}
            className="mt-2 w-full rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-2 text-sm font-medium text-[var(--text)] outline-none"
          />
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Account Status
          </p>
          <div className="mt-2 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[var(--success,#10b981)]" aria-hidden />
            <span className="text-sm font-medium capitalize text-[var(--text)]">
              {user?.status ?? "active"}
            </span>
          </div>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Member Since
          </p>
          <p className="mt-2 text-sm font-medium text-[var(--text)]">
            {formattedDate}
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          <ShieldCheck className="h-4 w-4 text-[var(--primary)]" aria-hidden />
          Assigned Roles & Authorizations
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {user?.roles && user.roles.length > 0 ? (
            user.roles.map((role) => (
              <span
                key={role.id}
                className="inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-1 text-xs font-medium text-[var(--text)]"
              >
                {role.name}
              </span>
            ))
          ) : (
            <span className="text-xs italic text-[var(--text-muted)]">
              No custom roles assigned (Standard Member)
            </span>
          )}
          {user?.is_tenant_admin && (
            <span className="inline-flex items-center rounded-md border border-[color-mix(in_srgb,var(--primary)_35%,var(--border))] bg-[color-mix(in_srgb,var(--primary)_8%,var(--surface))] px-3 py-1 text-xs font-semibold text-[var(--primary)]">
              Tenant Administrator
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2.5 rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3.5 py-3 text-xs text-[var(--text-secondary)]">
        <Info className="h-4 w-4 shrink-0 text-[var(--text-muted)]" aria-hidden />
        <p>
          Account profile information and role assignments are managed by Tenant Administrators in the Users administration workspace.
        </p>
      </div>
    </section>
  );
}
