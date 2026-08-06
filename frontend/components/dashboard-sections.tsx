import {
  ArrowRight,
  BookOpen,
  Check,
  Database,
  MessageSquare,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import type { CurrentUser } from "@/lib/contracts";

export function WorkspaceHeader({
  user,
  ready,
}: {
  user: CurrentUser;
  ready: boolean;
}) {
  return (
    <header className="grid gap-6 border-b border-[var(--border)] pb-7 md:grid-cols-[1fr_auto] md:items-end">
      <div>
        <p className="mb-2 text-sm font-medium text-[var(--primary)]">
          {user.tenant.name}
        </p>
        <h1 className="text-[1.75rem] font-semibold tracking-[-0.025em]">
          Welcome back
          {user.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
          Move from approved sources to grounded answers within your governed
          tenant workspace.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex min-h-9 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-xs font-medium">
          <span
            className={`h-2 w-2 rounded-full ${ready ? "bg-[var(--success)]" : "bg-[var(--danger)]"}`}
            aria-hidden
          />
          {ready ? "Workspace ready" : "Service attention needed"}
        </span>
        <Link
          href="/chat"
          className="inline-flex min-h-9 items-center rounded-md bg-[var(--primary)] px-3 text-xs font-semibold text-white hover:bg-[var(--primary-hover)]"
        >
          Open chat
        </Link>
      </div>
    </header>
  );
}

export function SystemStatusStrip({
  live,
  ready,
}: {
  live: boolean;
  ready: boolean;
}) {
  const statuses = [
    ["Frontend", true, "Interface available"],
    ["API live", live, live ? "Backend responding" : "Backend unavailable"],
    [
      "Platform ready",
      ready,
      ready ? "Dependencies ready" : "Dependencies unavailable",
    ],
  ] as const;
  return (
    <section
      aria-labelledby="system-status-heading"
      className="border-b border-[var(--border)] py-5"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 id="system-status-heading" className="text-sm font-semibold">
          System status
        </h2>
        <span className="text-xs text-[var(--text-muted)]">
          Live service checks
        </span>
      </div>
      <div className="grid overflow-hidden rounded-md border border-[var(--border)] bg-[var(--border)] sm:grid-cols-3 sm:gap-px">
        {statuses.map(([label, ok, description]) => (
          <div
            key={label}
            className="flex items-center gap-3 bg-[var(--surface)] px-4 py-3"
          >
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full ${ok ? "bg-[color-mix(in_srgb,var(--success)_12%,transparent)] text-[var(--success)]" : "bg-[color-mix(in_srgb,var(--danger)_12%,transparent)] text-[var(--danger)]"}`}
            >
              <Check aria-hidden className="h-3.5 w-3.5" />
            </span>
            <span>
              <span className="block text-xs font-semibold">{label}</span>
              <span className="block text-xs text-[var(--text-muted)]">
                {description}
              </span>
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

const steps = [
  "Connect sources",
  "Ask a question",
  "Validate access",
  "Generate grounded answer",
];
export function WorkflowSteps() {
  return (
    <section aria-labelledby="workflow-heading" className="py-7">
      <div className="mb-5">
        <h2 id="workflow-heading" className="text-base font-semibold">
          How Tenant Intelligence works
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Every request moves through the same governed workflow.
        </p>
      </div>
      <ol className="grid gap-3 md:grid-cols-4">
        {steps.map((step, index) => (
          <li
            key={step}
            className="relative border-t-2 border-[var(--border-strong)] pt-4 md:pr-6"
          >
            <span className="mb-2 block text-xs font-semibold text-[var(--primary)]">
              0{index + 1}
            </span>
            <span className="text-sm font-medium">{step}</span>
            {index < steps.length - 1 && (
              <ArrowRight
                aria-hidden
                className="absolute right-1 top-4 hidden h-4 w-4 text-[var(--text-muted)] md:block"
              />
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

const capabilities = [
  [
    MessageSquare,
    "Conversational intelligence",
    "Ask governed questions across database, document, or hybrid sources.",
    "/chat",
    "Workspace coming next",
  ],
  [
    BookOpen,
    "Knowledge sources",
    "Organize approved files into traceable, citation-ready knowledge.",
    "/knowledge",
    "Management UI upcoming",
  ],
  [
    Database,
    "Database access",
    "Connect PostgreSQL sources and discover metadata without copying business rows.",
    "/databases",
    "Management UI upcoming",
  ],
  [
    ShieldCheck,
    "Security and governance",
    "Control tables, columns, row filters, masking, and tenant boundaries.",
    "/permissions",
    "Administration UI upcoming",
  ],
] as const;
export function CapabilitySections() {
  return (
    <section
      aria-labelledby="capabilities-heading"
      className="border-y border-[var(--border)] py-7"
    >
      <div className="mb-5">
        <h2 id="capabilities-heading" className="text-base font-semibold">
          Capability areas
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          One workspace, separated by clear security responsibilities.
        </p>
      </div>
      <div className="grid border-y border-[var(--border)] md:grid-cols-2">
        {capabilities.map(
          ([Icon, title, description, href, availability], index) => (
            <article
              key={title}
              className={`group py-5 md:px-5 ${index % 2 === 0 ? "md:border-r md:border-[var(--border)] md:pl-0" : "md:pr-0"} ${index < 2 ? "border-b border-[var(--border)]" : ""}`}
            >
              <div className="flex items-start gap-4">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--surface-subtle)] text-[var(--text-secondary)]">
                  <Icon aria-hidden className="h-[18px] w-[18px]" />
                </span>
                <div>
                  <h3 className="text-sm font-semibold">{title}</h3>
                  <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                    {description}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <Link
                      href={href}
                      className="text-xs font-semibold text-[var(--primary)] hover:underline"
                    >
                      View area
                    </Link>
                    <span className="text-xs text-[var(--text-muted)]">
                      {availability}
                    </span>
                  </div>
                </div>
              </div>
            </article>
          ),
        )}
      </div>
    </section>
  );
}

const controls = [
  "Tenant isolation",
  "Read-only SQL validation",
  "Row-level filtering",
  "Sensitive-column masking",
  "Citation validation",
];
export function SecurityControlList() {
  return (
    <section
      aria-labelledby="security-heading"
      className="grid gap-6 py-7 lg:grid-cols-[0.8fr_1.2fr]"
    >
      <div>
        <h2 id="security-heading" className="text-base font-semibold">
          Verified security posture
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          Platform capabilities enforced by deterministic backend boundaries.
          Availability here does not imply a control is configured on every
          source.
        </p>
      </div>
      <ul className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {controls.map((control) => (
          <li
            key={control}
            className="flex items-center gap-2 border-b border-[var(--border)] pb-3 text-sm font-medium"
          >
            <ShieldCheck
              aria-hidden
              className="h-4 w-4 shrink-0 text-[var(--success)]"
            />
            {control}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function GettingStarted() {
  return (
    <section
      aria-labelledby="getting-started-heading"
      className="rounded-md border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-5 sm:p-6"
    >
      <div className="grid gap-6 md:grid-cols-[0.65fr_1.35fr]">
        <div>
          <h2 id="getting-started-heading" className="text-base font-semibold">
            Getting started
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            A concise path from source setup to a reviewable answer.
          </p>
        </div>
        <ol className="grid gap-3 text-sm sm:grid-cols-2">
          {[
            "Add a database or knowledge source",
            "Create a conversation",
            "Select authorized sources",
            "Ask a grounded question",
            "Review SQL and citations",
          ].map((step, index) => (
            <li key={step} className="flex gap-3">
              <span className="text-xs font-semibold text-[var(--primary)]">
                {index + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
