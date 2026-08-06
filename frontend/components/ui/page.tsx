export function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className="mb-8">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
        {description}
      </p>
    </header>
  );
}
export function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-[var(--border)] py-6">
      <div className="mb-4">
        <h2 className="text-base font-semibold">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {description}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}
