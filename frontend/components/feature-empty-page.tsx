import { CheckCircle2, Clock3, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/ui/page";

export function FeatureEmptyPage({
  title,
  description,
  capabilities,
  securityNote,
  preview = "workspace",
}: {
  title: string;
  description: string;
  capabilities: string[];
  securityNote: string;
  preview?: "workspace" | "list" | "settings";
}) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <div className="grid gap-7 lg:grid-cols-[1.15fr_0.85fr]">
        <section
          aria-labelledby="upcoming-heading"
          className="border-y border-[var(--border)] py-6"
        >
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 id="upcoming-heading" className="text-base font-semibold">
                Upcoming {title.toLowerCase()} workspace
              </h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Interface work continues in the next frontend phase.
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--warning)]">
              <Clock3 aria-hidden className="h-3.5 w-3.5" />
              Planned
            </span>
          </div>
          <div
            aria-label={`${title} interface preview`}
            className="rounded-md border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-4"
          >
            <div className="mb-4 flex items-center gap-2 border-b border-[var(--border)] pb-3">
              <span className="h-2 w-2 rounded-full bg-[var(--text-muted)]" />
              <span className="h-2 w-16 rounded bg-[var(--border-strong)]" />
              <span className="ml-auto h-6 w-16 rounded border border-[var(--border)]" />
            </div>
            {preview === "workspace" ? (
              <div className="grid min-h-36 grid-cols-[0.38fr_1fr] gap-3">
                <div className="border-r border-[var(--border)] pr-3">
                  <span className="block h-2 w-4/5 rounded bg-[var(--border)]" />
                  <span className="mt-3 block h-2 w-3/5 rounded bg-[var(--border)]" />
                </div>
                <div className="flex items-end">
                  <span className="block h-9 w-full rounded border border-[var(--border)] bg-[var(--surface)]" />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {[1, 2, 3].map((item) => (
                  <div
                    key={item}
                    className="flex items-center gap-3 border-b border-[var(--border)] pb-3"
                  >
                    <span className="h-8 w-8 rounded bg-[var(--surface-subtle)]" />
                    <span className="h-2 w-2/5 rounded bg-[var(--border-strong)]" />
                    <span className="ml-auto h-2 w-16 rounded bg-[var(--border)]" />
                  </div>
                ))}
              </div>
            )}
          </div>
          <p className="mt-3 text-xs leading-5 text-[var(--text-muted)]">
            Structural preview only — no sample records or business data.
          </p>
        </section>
        <aside>
          <h2 className="text-sm font-semibold">What this area will support</h2>
          <ul className="mt-4 space-y-3">
            {capabilities.map((capability) => (
              <li
                key={capability}
                className="flex gap-2 text-sm leading-6 text-[var(--text-secondary)]"
              >
                <CheckCircle2
                  aria-hidden
                  className="mt-1 h-4 w-4 shrink-0 text-[var(--primary)]"
                />
                {capability}
              </li>
            ))}
          </ul>
          <div className="mt-7 border-l-2 border-[var(--success)] bg-[var(--surface-subtle)] p-4">
            <p className="flex items-center gap-2 text-xs font-semibold">
              <ShieldCheck
                aria-hidden
                className="h-4 w-4 text-[var(--success)]"
              />
              Verified security boundary
            </p>
            <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">
              {securityNote}
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
