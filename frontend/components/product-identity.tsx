export function ProductMonogram({ compact = false }: { compact?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`${compact ? "h-8 w-8" : "h-10 w-10"} relative inline-flex shrink-0 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--text)] text-[var(--surface)]`}
    >
      <span className="text-[11px] font-semibold tracking-[-0.08em]">TI</span>
      <span className="absolute bottom-1 right-1 h-1 w-1 bg-[var(--primary)]" />
    </span>
  );
}

export function ProductIdentity({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3" aria-label="Tenant Intelligence">
      <ProductMonogram compact={compact} />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold tracking-[-0.01em]">
          Tenant Intelligence
        </p>
        {!compact && (
          <p className="mt-0.5 truncate text-xs text-[var(--text-muted)]">
            Secure intelligence workspace
          </p>
        )}
      </div>
    </div>
  );
}
