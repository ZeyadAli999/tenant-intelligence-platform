export function ProductMonogram({ compact = false }: { compact?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`${compact ? "h-8 w-8" : "h-10 w-10"} inline-flex shrink-0`}
    >
      <svg viewBox="0 0 40 40" className="h-full w-full" focusable="false">
        <rect width="40" height="40" rx="8" fill="var(--text)" />
        <path
          d="M8 10h19v5h-7v16h-5V15H8z"
          fill="var(--surface)"
        />
        <path d="M27 10h5v21h-5z" fill="var(--primary)" />
      </svg>
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
