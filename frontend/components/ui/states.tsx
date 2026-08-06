import { AlertCircle, Inbox, LoaderCircle } from "lucide-react";

export function LoadingState({
  label = "Loading workspace",
}: {
  label?: string;
}) {
  return (
    <div
      role="status"
      className="flex min-h-40 items-center justify-center gap-2 text-sm text-[var(--text-secondary)]"
    >
      <LoaderCircle
        aria-hidden
        className="h-4 w-4 animate-spin motion-reduce:animate-none"
      />
      {label}
    </div>
  );
}
export function ErrorState({
  title = "Something went wrong",
  message,
}: {
  title?: string;
  message: string;
}) {
  return (
    <div
      role="alert"
      className="flex min-h-40 flex-col items-center justify-center text-center"
    >
      <AlertCircle aria-hidden className="mb-3 h-6 w-6 text-[var(--danger)]" />
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 max-w-md text-sm text-[var(--text-secondary)]">
        {message}
      </p>
    </div>
  );
}
export function EmptyState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center border-y border-[var(--border)] py-12 text-center">
      <Inbox aria-hidden className="mb-3 h-6 w-6 text-[var(--text-muted)]" />
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
        {message}
      </p>
    </div>
  );
}
