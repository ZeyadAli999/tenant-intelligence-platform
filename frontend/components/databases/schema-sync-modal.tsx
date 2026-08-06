"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SchemaSyncResponse } from "@/lib/database-contracts";

import { toast } from "@/components/ui/toast";

interface SchemaSyncModalProps {
  isOpen: boolean;
  connectionName: string;
  onSync: () => Promise<SchemaSyncResponse>;
  onClose: () => void;
}

export function SchemaSyncModal({
  isOpen,
  connectionName,
  onSync,
  onClose,
}: SchemaSyncModalProps) {
  const [isSyncing, setIsSyncing] = useState(false);
  const [result, setResult] = useState<SchemaSyncResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleStartSync = async () => {
    setIsSyncing(true);
    setError(null);
    setResult(null);

    try {
      const syncResult = await onSync();
      setResult(syncResult);
      toast.success("Schema synchronization completed.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Schema synchronization failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleClose = () => {
    setResult(null);
    setError(null);
    onClose();
  };

  return (
    <div
      tabIndex={-1}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onKeyDown={(e) => e.key === "Escape" && handleClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="sync-modal-title"
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surf)] p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between pb-4">
          <h2
            id="sync-modal-title"
            className="text-xl font-semibold text-[var(--fg)]"
          >
            Sync Schema Catalog
          </h2>
          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg p-1 text-[var(--fg-muted)] hover:bg-[var(--surf-muted)] hover:text-[var(--fg)]"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mb-4">
            <Alert tone="danger">{error}</Alert>
          </div>
        )}

        {result ? (
          <div className="space-y-4">
            <Alert tone="info">{result.message}</Alert>

            <div className="grid grid-cols-3 gap-2 bg-[var(--surf-muted)] p-3 rounded-lg text-center text-sm">
              <div>
                <span className="block font-semibold text-[var(--fg)]">
                  {result.schema_count}
                </span>
                <span className="text-xs text-[var(--fg-muted)]">Schemas</span>
              </div>
              <div>
                <span className="block font-semibold text-[var(--fg)]">
                  {result.table_count}
                </span>
                <span className="text-xs text-[var(--fg-muted)]">Tables</span>
              </div>
              <div>
                <span className="block font-semibold text-[var(--fg)]">
                  {result.column_count}
                </span>
                <span className="text-xs text-[var(--fg-muted)]">Columns</span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button type="button" onClick={handleClose}>
                Done
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-[var(--fg-muted)] leading-relaxed">
              Synchronizing{" "}
              <strong className="text-[var(--fg)]">{connectionName}</strong>{" "}
              will inspect the external database metadata and update the
              platform&apos;s internal catalog schemas, tables, and columns.
            </p>

            <div className="bg-[var(--surf-muted)] p-3 rounded-lg border-l-4 border-amber-500 text-xs text-[var(--fg-muted)]">
              <strong className="block text-amber-500 font-medium mb-0.5">
                Catalog Metadata Update Only
              </strong>
              This operation reads metadata only and will{" "}
              <strong>never modify</strong> or alter data in your external
              database.
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                className="!bg-[var(--surface-subtle)] !text-[var(--fg-default)] border border-[var(--border)] hover:!bg-[var(--border)]"
                onClick={handleClose}
                disabled={isSyncing}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleStartSync}
                disabled={isSyncing}
              >
                {isSyncing ? "Synchronizing..." : "Start Sync"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
