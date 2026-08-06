export function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
      <span
        aria-hidden
        className={`h-2 w-2 rounded-full ${ok ? "bg-[var(--success)]" : "bg-[var(--danger)]"}`}
      />
      <span>{label}</span>
      <span className="sr-only">{ok ? "available" : "unavailable"}</span>
    </span>
  );
}
