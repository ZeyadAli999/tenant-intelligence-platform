"use client";

import { KeyRound, LogOut, ShieldCheck, ShieldOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { performClientLogout } from "@/components/ui/toast";

export function SecuritySettingsSection({
  onLogout,
}: {
  onLogout?: () => Promise<void>;
} = {}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const router = useRouter();

  async function handleLogout() {
    setSigningOut(true);
    try {
      if (onLogout) {
        await onLogout();
      } else {
        const success = await performClientLogout(router);
        if (!success) {
          setSigningOut(false);
          setConfirmOpen(false);
        }
      }
    } catch {
      setSigningOut(false);
      setConfirmOpen(false);
    }
  }

  return (
    <section aria-labelledby="security-settings-heading" className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h2
          id="security-settings-heading"
          className="flex items-center gap-2 text-lg font-semibold text-[var(--text)]"
        >
          <ShieldCheck className="h-5 w-5 text-[var(--primary)]" aria-hidden />
          Session & Security
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Active session status, tenant context boundaries, and authentication control.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Active Session Status
          </p>
          <div className="mt-2 flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--success,#10b981)]" aria-hidden />
            <span className="text-sm font-semibold text-[var(--text)]">
              Authenticated & Isolated
            </span>
          </div>
          <p className="mt-1.5 text-xs text-[var(--text-secondary)]">
            Session tokens are secured using HTTP-only cookies.
          </p>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Password Policy
          </p>
          <div className="mt-2 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-[var(--primary)]" aria-hidden />
            <span className="text-sm font-semibold text-[var(--text)]">
              Strict Password Policy
            </span>
          </div>
          <p className="mt-1.5 text-xs text-[var(--text-secondary)]">
            Minimum 12 characters with multi-tenant hash salting.
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">
              Sign Out of Current Session
            </h3>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              End your active authenticated session on this device.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-[color-mix(in_srgb,var(--danger)_10%,var(--surface))] border border-[color-mix(in_srgb,var(--danger)_30%,var(--border))] px-4 py-2 text-sm font-semibold text-[var(--danger)] hover:bg-[color-mix(in_srgb,var(--danger)_18%,var(--surface))]"
          >
            <LogOut className="h-4 w-4" aria-hidden />
            Sign Out
          </button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={confirmOpen}
        title="Confirm Session Sign Out"
        description="Are you sure you want to sign out of your Tenant Intelligence session? You will be redirected to the login page."
        confirmLabel="Yes, Sign Out"
        cancelLabel="Cancel"
        variant="danger"
        isLoading={signingOut}
        onConfirm={handleLogout}
        onClose={() => setConfirmOpen(false)}
      />

      <div className="flex items-center gap-2.5 rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3.5 py-3 text-xs text-[var(--text-secondary)]">
        <ShieldOff className="h-4 w-4 shrink-0 text-[var(--text-muted)]" aria-hidden />
        <p>
          Self-service password changes and session revocation endpoints are currently unexposed by the backend. Contact your workspace administrator for account credential support.
        </p>
      </div>
    </section>
  );
}
