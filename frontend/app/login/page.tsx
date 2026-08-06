import type { Metadata } from "next";
import { BookOpenCheck, Database, ShieldCheck } from "lucide-react";
import { LoginForm } from "@/components/login-form";
import { PlatformStatus } from "@/components/platform-status";
import { ProductIdentity } from "@/components/product-identity";

export const metadata: Metadata = { title: "Sign in" };

const capabilities = [
  [Database, "Ask databases and documents in natural language"],
  [ShieldCheck, "Enforce tenant isolation and access policies"],
  [BookOpenCheck, "Verify grounded answers with SQL and citations"],
] as const;

export default function LoginPage() {
  return (
    <main className="min-h-screen lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(440px,0.95fr)]">
      <section className="relative hidden min-h-screen overflow-hidden border-r border-[var(--border)] bg-[var(--sidebar)] px-10 py-9 lg:flex lg:flex-col xl:px-16 xl:py-12">
        <ProductIdentity />
        <div className="my-auto max-w-xl py-12">
          <p className="mb-4 text-sm font-medium text-[var(--primary)]">
            Governed intelligence, one workspace
          </p>
          <h2 className="max-w-lg text-[2.2rem] font-semibold leading-[1.16] tracking-[-0.035em] xl:text-[2.55rem]">
            Work confidently across organizational data and documents.
          </h2>
          <p className="mt-5 max-w-lg text-base leading-7 text-[var(--text-secondary)]">
            Secure data and document intelligence for organizations, with
            deterministic controls between every question and answer.
          </p>
          <div className="mt-9 border-y border-[var(--border)]">
            {capabilities.map(([Icon, label]) => (
              <div
                key={label}
                className="flex items-center gap-4 border-b border-[var(--border)] py-4 last:border-0"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--surface)] text-[var(--text-secondary)] ring-1 ring-[var(--border)]">
                  <Icon aria-hidden className="h-[18px] w-[18px]" />
                </span>
                <span className="text-sm font-medium">{label}</span>
              </div>
            ))}
          </div>
          <div
            aria-label="Platform workflow"
            className="mt-9 grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-2 text-xs text-[var(--text-secondary)]"
          >
            <span className="border-t-2 border-[var(--primary)] pt-2">
              Connect sources
            </span>
            <span aria-hidden>→</span>
            <span className="border-t-2 border-[var(--border-strong)] pt-2">
              Apply governance
            </span>
            <span aria-hidden>→</span>
            <span className="border-t-2 border-[var(--border-strong)] pt-2">
              Ground answers
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between border-t border-[var(--border)] pt-5">
          <PlatformStatus compact />
          <span className="text-xs text-[var(--text-muted)]">
            Tenant-scoped by design
          </span>
        </div>
      </section>

      <section className="flex min-h-screen items-center bg-[var(--surface)] px-5 py-8 sm:px-10 lg:px-12 xl:px-20">
        <div className="mx-auto w-full max-w-[440px]">
          <div className="mb-8 lg:hidden">
            <ProductIdentity />
          </div>
          <header className="mb-7">
            <p className="mb-2 text-sm font-medium text-[var(--primary)]">
              Workspace access
            </p>
            <h1 className="text-[1.75rem] font-semibold tracking-[-0.025em]">
              Sign in to Tenant Intelligence
            </h1>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              Enter your tenant and account credentials to continue securely.
            </p>
          </header>
          <div className="border-y border-[var(--border)] py-7">
            <LoginForm />
          </div>
          <div className="mt-6 lg:hidden">
            <PlatformStatus compact />
          </div>
          <p className="mt-5 text-xs leading-5 text-[var(--text-muted)]">
            Your tenant code selects the isolated workspace used for
            authentication. Credentials are sent only through the secure session
            service.
          </p>
        </div>
      </section>
    </main>
  );
}
