"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConnectionTestResponse } from "@/lib/database-contracts";

interface ConnectionTestModalProps {
  isOpen: boolean;
  testResult: ConnectionTestResponse | null;
  isLoading: boolean;
  onClose: () => void;
}

export function ConnectionTestModal({
  isOpen,
  testResult,
  isLoading,
  onClose,
}: ConnectionTestModalProps) {
  if (!isOpen) return null;

  return (
    <div
      tabIndex={-1}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="test-modal-title"
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surf)] p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between pb-4">
          <h2
            id="test-modal-title"
            className="text-xl font-semibold text-[var(--fg)]"
          >
            Connection Test Results
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-[var(--fg-muted)] hover:bg-[var(--surf-muted)] hover:text-[var(--fg)]"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {isLoading ? (
          <div className="py-8 text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-[var(--accent)] border-r-transparent"></div>
            <p className="mt-3 text-sm text-[var(--fg-muted)]">
              Testing database connection...
            </p>
          </div>
        ) : testResult ? (
          <div className="space-y-4">
            <Alert tone={testResult.success ? "info" : "danger"}>
              {testResult.message}
            </Alert>

            <div className="space-y-2 text-sm text-[var(--fg-muted)] bg-[var(--surf-muted)] p-3 rounded-lg">
              <div className="flex justify-between">
                <span>Status:</span>
                <span className="font-semibold text-[var(--fg)]">
                  {testResult.status}
                </span>
              </div>
              {testResult.error_code && (
                <div className="flex justify-between">
                  <span>Error Code:</span>
                  <span className="font-mono text-xs text-red-500">
                    {testResult.error_code}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Tested At:</span>
                <span>{new Date(testResult.tested_at).toLocaleString()}</span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button type="button" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
