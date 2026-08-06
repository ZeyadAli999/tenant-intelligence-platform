"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { SchemaTableExplorer } from "./schema-table-explorer";
import { DatabaseModal } from "./database-modal";
import { ConnectionTestModal } from "./connection-test-modal";
import { SchemaSyncModal } from "./schema-sync-modal";
import {
  deleteDatabaseConnection,
  getDatabaseConnection,
  syncDatabaseSchema,
  testDatabaseConnection,
  updateDatabaseConnection,
} from "@/lib/database-api";
import {
  ConnectionTestResponse,
  DatabaseConnectionCreateInput,
  DatabaseConnectionResponse,
  DatabaseConnectionUpdateInput,
  SchemaSyncResponse,
} from "@/lib/database-contracts";

interface DatabaseDetailViewProps {
  connectionId: string;
  isTenantAdmin: boolean;
  onBack: () => void;
}

export function DatabaseDetailView({
  connectionId,
  isTenantAdmin,
  onBack,
}: DatabaseDetailViewProps) {
  const [connection, setConnection] =
    useState<DatabaseConnectionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Action Modals State
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const [isTestOpen, setIsTestOpen] = useState(false);
  const [isTestLoading, setIsTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(
    null,
  );

  const [isSyncOpen, setIsSyncOpen] = useState(false);

  const loadConnection = useCallback(async () => {
    try {
      const data = await getDatabaseConnection(connectionId);
      setError(null);
      setConnection(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load database connection details",
      );
    } finally {
      setIsLoading(false);
    }
  }, [connectionId]);

  useEffect(() => {
    let isMounted = true;
    getDatabaseConnection(connectionId)
      .then((data) => {
        if (isMounted) {
          setConnection(data);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load database connection details",
          );
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [connectionId]);

  const handleUpdate = async (
    input: DatabaseConnectionCreateInput | DatabaseConnectionUpdateInput,
  ) => {
    if (!connection) return;
    await updateDatabaseConnection(connection.id, input);
    await loadConnection();
  };

  const handleDelete = async () => {
    if (!connection) return;
    await deleteDatabaseConnection(connection.id);
    onBack();
  };

  const handleTestConnection = async () => {
    if (!connection) return;
    setIsTestOpen(true);
    setIsTestLoading(true);
    setTestResult(null);
    try {
      const res = await testDatabaseConnection(connection.id);
      setTestResult(res);
      await loadConnection();
    } catch (err: unknown) {
      setTestResult({
        success: false,
        status: "failed",
        error_code: "TEST_FAILED",
        message: err instanceof Error ? err.message : "Connection test failed",
        tested_at: new Date().toISOString(),
      });
    } finally {
      setIsTestLoading(false);
    }
  };

  const handleSyncSchema = async (): Promise<SchemaSyncResponse> => {
    if (!connection) throw new Error("Connection not found");
    const result = await syncDatabaseSchema(connection.id);
    await loadConnection();
    return result;
  };

  if (isLoading) {
    return (
      <div className="py-12 text-center text-sm text-[var(--fg-muted)]">
        Loading connection details...
      </div>
    );
  }

  if (error || !connection) {
    return (
      <div className="space-y-4">
        <Alert tone="danger">{error || "Database connection not found"}</Alert>
        <Button
          type="button"
          className="!bg-[var(--surface-subtle)] !text-[var(--fg-default)] border border-[var(--border)] hover:!bg-[var(--border)]"
          onClick={onBack}
        >
          ← Back to Connections
        </Button>
      </div>
    );
  }

  const isConnected = connection.status === "connected";
  const isFailed = connection.status === "failed";

  return (
    <div className="space-y-6">
      {/* Header & Metadata Card */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surf)] p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4 pb-6 border-b border-[var(--border)]">
          <div>
            <button
              type="button"
              onClick={onBack}
              className="text-xs text-[var(--accent)] hover:underline mb-2 block font-medium"
            >
              ← Back to Connections
            </button>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--fg)]">
                {connection.name}
              </h1>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  isConnected
                    ? "bg-emerald-500/10 text-emerald-600"
                    : isFailed
                      ? "bg-red-500/10 text-red-600"
                      : "bg-gray-500/10 text-gray-500"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    isConnected
                      ? "bg-emerald-500"
                      : isFailed
                        ? "bg-red-500"
                        : "bg-gray-400"
                  }`}
                />
                {connection.status}
              </span>
            </div>
            <p className="mt-1 text-sm text-[var(--fg-muted)] font-mono">
              {connection.username}@{connection.host}:{connection.port}/
              {connection.database_name} (
              {connection.database_type.toUpperCase()})
            </p>
          </div>

          {/* Actions */}
          {isTenantAdmin && (
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                className="!bg-[var(--surface-subtle)] !text-[var(--fg-default)] hover:!bg-[var(--border)]"
                onClick={handleTestConnection}
              >
                Test Connection
              </Button>
              <Button
                type="button"
                className="!bg-[var(--surface-subtle)] !text-[var(--fg-default)] hover:!bg-[var(--border)]"
                onClick={() => setIsSyncOpen(true)}
              >
                Sync Schema
              </Button>
              <Button
                type="button"
                className="!bg-transparent !text-[var(--fg-muted)] hover:!text-[var(--fg-default)] border border-[var(--border)]"
                onClick={() => setIsEditOpen(true)}
              >
                Edit
              </Button>
              <Button
                type="button"
                className="!bg-transparent !text-[var(--danger)] hover:!bg-[color-mix(in_srgb,var(--danger)_10%,transparent)]"
                onClick={() => setIsDeleteOpen(true)}
              >
                Delete
              </Button>
            </div>
          )}
        </div>

        {/* Status & Timing Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-6 text-sm">
          <div>
            <span className="block text-xs text-[var(--fg-muted)]">
              SSL Requirement
            </span>
            <span className="font-semibold text-[var(--fg)]">
              {connection.ssl_enabled ? "Enabled (Required)" : "Disabled"}
            </span>
          </div>
          <div>
            <span className="block text-xs text-[var(--fg-muted)]">
              Last Tested
            </span>
            <span className="font-semibold text-[var(--fg)]">
              {connection.last_tested_at
                ? new Date(connection.last_tested_at).toLocaleString()
                : "Never"}
            </span>
          </div>
          <div>
            <span className="block text-xs text-[var(--fg-muted)]">
              Schema Sync Status
            </span>
            <span className="font-semibold text-[var(--fg)] uppercase">
              {connection.schema_sync_status}
            </span>
          </div>
          <div>
            <span className="block text-xs text-[var(--fg-muted)]">
              Last Schema Sync
            </span>
            <span className="font-semibold text-[var(--fg)]">
              {connection.last_schema_sync_at
                ? new Date(connection.last_schema_sync_at).toLocaleString()
                : "Never"}
            </span>
          </div>
        </div>
      </div>

      {/* Schema & Table Explorer */}
      <SchemaTableExplorer connectionId={connection.id} />

      {/* Edit Modal */}
      {isEditOpen && (
        <DatabaseModal
          isOpen={isEditOpen}
          connectionToEdit={connection}
          onSubmit={handleUpdate}
          onClose={() => setIsEditOpen(false)}
        />
      )}

      {/* Delete Confirmation Modal */}
      {isDeleteOpen && (
        <ConfirmDialog
          isOpen={isDeleteOpen}
          title={`Delete ${connection.name}?`}
          description="Are you sure you want to delete this database connection? Internal catalog schemas and saved credentials will be removed. The external database will not be affected."
          onConfirm={handleDelete}
          onClose={() => setIsDeleteOpen(false)}
        />
      )}

      {/* Test Connection Modal */}
      {isTestOpen && (
        <ConnectionTestModal
          isOpen={isTestOpen}
          testResult={testResult}
          isLoading={isTestLoading}
          onClose={() => setIsTestOpen(false)}
        />
      )}

      {/* Sync Schema Modal */}
      {isSyncOpen && (
        <SchemaSyncModal
          isOpen={isSyncOpen}
          connectionName={connection.name}
          onSync={handleSyncSchema}
          onClose={() => setIsSyncOpen(false)}
        />
      )}
    </div>
  );
}
