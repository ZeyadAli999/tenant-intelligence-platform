export function Alert({
  children,
  tone = "danger",
}: {
  children: React.ReactNode;
  tone?: "danger" | "info";
}) {
  return (
    <div
      role="alert"
      className={`rounded-md border px-3 py-2.5 text-sm ${tone === "danger" ? "border-[color-mix(in_srgb,var(--danger)_30%,var(--border))] bg-[color-mix(in_srgb,var(--danger)_8%,var(--surface))] text-[var(--danger)]" : "border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--text-secondary)]"}`}
    >
      {children}
    </div>
  );
}
