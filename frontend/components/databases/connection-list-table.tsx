"use client";

import { Button } from "@/components/ui/button";
import { DatabaseConnectionResponse } from "@/lib/database-contracts";

interface ConnectionListTableProps {
  connections: DatabaseConnectionResponse[];
  isTenantAdmin: boolean;
  onSelectConnection: (id: string) => void;
  onEditConnection: (conn: DatabaseConnectionResponse) => void;
  onDeleteConnection: (conn: DatabaseConnectionResponse) => void;
  onTestConnection: (conn: DatabaseConnectionResponse) => void;
  onSyncSchema: (conn: DatabaseConnectionResponse) => void;
}

export function ConnectionListTable({
  connections,
  isTenantAdmin,
  onSelectConnection,
  onEditConnection,
  onDeleteConnection,
  onTestConnection,
  onSyncSchema,
}: ConnectionListTableProps) {
  if (connections.length === 0) {
    return (
      <div className="py-12 text-center border border-dashed border-[var(--border)] rounded-xl bg-[var(--surf)]">
        <h3 className="text-lg font-medium text-[var(--fg)]">
          No Database Connections
        </h3>
        <p className="mt-1 text-sm text-[var(--fg-muted)]">
          Add your first external PostgreSQL database connection to enable
          schema discovery and SQL queries.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surf)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surf-muted)] text-xs text-[var(--fg-muted)] uppercase">
            <th className="py-3 px-4">Connection</th>
            <th className="py-3 px-4">Type</th>
            <th className="py-3 px-4">Host / Database</th>
            <th className="py-3 px-4">Status</th>
            <th className="py-3 px-4">Last Sync</th>
            <th className="py-3 px-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {connections.map((conn) => {
            const isConnected = conn.status === "connected";
            const isFailed = conn.status === "failed";

            return (
              <tr
                key={conn.id}
                className="hover:bg-[var(--surf-muted)] transition-colors"
              >
                <td className="py-4 px-4 font-medium text-[var(--fg)]">
                  <button
                    type="button"
                    onClick={() => onSelectConnection(conn.id)}
                    className="hover:underline font-semibold text-[var(--accent)]"
                  >
                    {conn.name}
                  </button>
                  <span className="block text-xs text-[var(--fg-muted)] font-normal">
                    User: {conn.username}
                  </span>
                </td>
                <td className="py-4 px-4 font-mono text-xs uppercase text-[var(--fg-muted)]">
                  {conn.database_type}
                </td>
                <td className="py-4 px-4 font-mono text-xs">
                  <div className="text-[var(--fg)]">
                    {conn.host}:{conn.port}
                  </div>
                  <div className="text-[var(--fg-muted)]">
                    {conn.database_name}
                  </div>
                </td>
                <td className="py-4 px-4">
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
                    {conn.status}
                  </span>
                </td>
                <td className="py-4 px-4 text-xs text-[var(--fg-muted)]">
                  {conn.last_schema_sync_at
                    ? new Date(conn.last_schema_sync_at).toLocaleDateString()
                    : "Never"}
                </td>
                <td className="py-4 px-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      type="button"
                      className="!min-h-8 !px-2.5 !py-1 !text-xs !bg-transparent !text-[var(--accent)] hover:underline font-medium"
                      onClick={() => onSelectConnection(conn.id)}
                    >
                      Explore
                    </Button>

                    {isTenantAdmin && (
                      <>
                        <Button
                          type="button"
                          className="!min-h-8 !px-2.5 !py-1 !text-xs !bg-[var(--surface-subtle)] !text-[var(--fg-default)] hover:!bg-[var(--border)]"
                          onClick={() => onTestConnection(conn)}
                        >
                          Test
                        </Button>
                        <Button
                          type="button"
                          className="!min-h-8 !px-2.5 !py-1 !text-xs !bg-[var(--surface-subtle)] !text-[var(--fg-default)] hover:!bg-[var(--border)]"
                          onClick={() => onSyncSchema(conn)}
                        >
                          Sync
                        </Button>
                        <Button
                          type="button"
                          className="!min-h-8 !px-2.5 !py-1 !text-xs !bg-transparent !text-[var(--fg-muted)] hover:!text-[var(--fg-default)]"
                          onClick={() => onEditConnection(conn)}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          className="!min-h-8 !px-2.5 !py-1 !text-xs !bg-transparent !text-[var(--danger)] hover:!bg-[color-mix(in_srgb,var(--danger)_10%,transparent)]"
                          onClick={() => onDeleteConnection(conn)}
                        >
                          Delete
                        </Button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
