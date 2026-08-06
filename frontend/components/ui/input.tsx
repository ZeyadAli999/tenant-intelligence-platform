import { forwardRef, type InputHTMLAttributes } from "react";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className = "", ...props }, ref) {
  return (
    <input
      ref={ref}
      className={`min-h-11 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-[15px] text-[var(--text)] placeholder:text-[var(--text-muted)] hover:border-[var(--text-muted)] disabled:opacity-60 ${className}`}
      {...props}
    />
  );
});
