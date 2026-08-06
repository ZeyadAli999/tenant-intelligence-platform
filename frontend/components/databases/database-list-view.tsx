"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { ConnectionListTable } from "./connection-list-table";
import { DatabaseModal } from "./database-modal";
import { ConnectionTestModal } from "./connection-test-modal";
import { SchemaSyncModal } from "./schema-sync-modal";
import {
  createDatabaseConnection,
  deleteDatabaseConnection,
  listDatabaseConnections,
  syncDatabaseSchema,
  testDatabaseConnection,
  updateDatabaseConnection,
} from "@/lib/database-api";
import {
  ConnectionTestResponse,
  DatabaseConnectionCreateInput,
  DatabaseConnectionResponse,
  SchemaSyncResponse,
} from "@/lib/database-contracts";

interface DatabaseListViewProps {
  isTenantAdmin: boolean;
  onSelectConnection: (id: string) => void;
}

export function DatabaseListView({
  isTenantAdmin,
  onSelectConnection,
}: DatabaseListViewProps) {
  const [connections, setConnections] = useState<DatabaseConnectionResponse[]>(
    [],
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [connToEdit, setConnToEdit] =
    useState<DatabaseConnectionResponse | null>(null);
  const [connToDelete, setConnToDelete] =
    useState<DatabaseConnectionResponse | null>(null);

  const [testConn, setTestConn] = useState<DatabaseConnectionResponse | null>(
    null,
  );
  const [isTestLoading, setIsTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(
    null,
  );

  const [syncConn, setSyncConn] = useState<DatabaseConnectionResponse | null>(
    null,
  );

  const loadConnections = useCallback(async () => {
    try {
      const res = await listDatabaseConnections();
      setError(null);
      setConnections(res.items);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load database connections",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    listDatabaseConnections()
      .then((res) => {
        if (isMounted) {
          setConnections(res.items);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load database connections",
          );
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleCreate = async (input: DatabaseConnectionCreateInput) => {
    await createDatabaseConnection(input);
    await loadConnections();
  };

  const handleUpdate = async (input: DatabaseConnectionCreateInput) => {
    if (!connToEdit) return;
    await updateDatabaseConnection(connToEdit.id, input);
    setConnToEdit(null);
    await loadConnections();
  };

  const handleDelete = async () => {
    if (!connToDelete) return;
    await deleteDatabaseConnection(connToDelete.id);
    setConnToDelete(null);
    await loadConnections();
  };

  const handleTestConnection = async (conn: DatabaseConnectionResponse) => {
    setTestConn(conn);
    setIsTestLoading(true);
    setTestResult(null);
    try {
      const res = await testDatabaseConnection(conn.id);
      setTestResult(res);
      await loadConnections();
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
    if (!syncConn) throw new Error("No connection selected for sync");
    const result = await syncDatabaseSchema(syncConn.id);
    await loadConnections();
    return result;
  };

  const filteredConnections = connections.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.host.toLowerCase().includes(search.toLowerCase()) ||
      c.database_name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--fg)]">
            Database Connections
          </h1>
          <p className="text-sm text-[var(--fg-muted)]">
            Manage external PostgreSQL database connections, test connectivity,
            and synchronize catalog metadata.
          </p>
        </div>

        {isTenantAdmin && (
          <Button type="button" onClick={() => setIsCreateOpen(true)}>
            + Add Connection
          </Button>
        )}
      </div>

      {/* Filter / Search Bar */}
      <div className="flex items-center gap-3">
        <div className="max-w-xs flex-1">
          <Input
            placeholder="Search connections..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {error && <Alert tone="danger">{error}</Alert>}

      {/* Connection Table / Cards */}
      {isLoading ? (
        <div className="py-12 text-center text-sm text-[var(--fg-muted)]">
          Loading database connections...
        </div>
      ) : (
        <ConnectionListTable
          connections={filteredConnections}
          isTenantAdmin={isTenantAdmin}
          onSelectConnection={onSelectConnection}
          onEditConnection={(conn) => setConnToEdit(conn)}
          onDeleteConnection={(conn) => setConnToDelete(conn)}
          onTestConnection={handleTestConnection}
          onSyncSchema={(conn) => setSyncConn(conn)}
        />
      )}

      {/* Create Modal */}
      {isCreateOpen && (
        <DatabaseModal
          isOpen={isCreateOpen}
          onSubmit={handleCreate}
          onClose={() => setIsCreateOpen(false)}
        />
      )}

      {/* Edit Modal */}
      {connToEdit && (
        <DatabaseModal
          isOpen={Boolean(connToEdit)}
          connectionToEdit={connToEdit}
          onSubmit={handleUpdate}
          onClose={() => setConnToEdit(null)}
        />
      )}

      {/* Delete Dialog */}
      {connToDelete && (
        <ConfirmDialog
          isOpen={Boolean(connToDelete)}
          title={`Delete ${connToDelete.name}?`}
          description="Are you sure you want to delete this database connection? Platform catalog metadata and saved credentials will be removed. The external database will not be affected."
          onConfirm={handleDelete}
          onClose={() => setConnToDelete(null)}
        />
      )}

      {/* Test Modal */}
      {testConn && (
        <ConnectionTestModal
          isOpen={Boolean(testConn)}
          testResult={testResult}
          isLoading={isTestLoading}
          onClose={() => setTestConn(null)}
        />
      )}

      {/* Sync Modal */}
      {syncConn && (
        <SchemaSyncModal
          isOpen={Boolean(syncConn)}
          connectionName={syncConn.name}
          onSync={handleSyncSchema}
          onClose={() => setSyncConn(null)}
        />
      )}
    </div>
  );
}
