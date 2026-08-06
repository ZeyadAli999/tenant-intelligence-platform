import { Slot } from "@radix-ui/react-slot";
import type { ButtonHTMLAttributes } from "react";

export function Button({
  className = "",
  asChild = false,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-[var(--on-primary)] hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-[var(--disabled-opacity)] ${className}`}
      {...props}
    />
  );
}
