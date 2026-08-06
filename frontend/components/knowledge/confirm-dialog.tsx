"use client";

import { useEffect, useRef } from "react";
import { AlertTriangle, LoaderCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary";
  isLoading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  isLoading = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isLoading) {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, isLoading, onClose]);

  if (!isOpen) return null;

  return (
    <div
      aria-modal="true"
      role="dialog"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isLoading) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="w-full max-w-md rounded-lg border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-6 shadow-lg"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {variant === "danger" ? (
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-500/10 text-[var(--danger)]">
                <AlertTriangle aria-hidden className="h-5 w-5" />
              </div>
            ) : null}
            <h3
              id="confirm-dialog-title"
              className="text-base font-semibold text-[var(--text)]"
            >
              {title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            aria-label="Close dialog"
            className="rounded-md p-1 text-[var(--text-muted)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text)] disabled:opacity-50"
          >
            <X aria-hidden className="h-4 w-4" />
          </button>
        </div>

        <p
          id="confirm-dialog-description"
          className="mt-3 text-sm text-[var(--text-secondary)]"
        >
          {description}
        </p>

        <div className="mt-6 flex items-center justify-end gap-3">
          <Button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className={
              variant === "danger"
                ? "bg-[var(--danger)] hover:bg-red-700 text-white"
                : ""
            }
          >
            {isLoading ? (
              <>
                <LoaderCircle
                  aria-hidden
                  className="h-4 w-4 animate-spin motion-reduce:animate-none"
                />
                Processing...
              </>
            ) : (
              confirmLabel
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
