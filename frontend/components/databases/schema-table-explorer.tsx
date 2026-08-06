"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getAllowedSchema,
  listDatabaseSchemas,
  listDatabaseTables,
} from "@/lib/database-api";
import {
  AllowedSchemaResponse,
  DatabaseSchemaResponse,
  DatabaseTableResponse,
} from "@/lib/database-contracts";

interface SchemaTableExplorerProps {
  connectionId: string;
}

export function SchemaTableExplorer({
  connectionId,
}: SchemaTableExplorerProps) {
  const [activeTab, setActiveTab] = useState<"tables" | "schemas" | "allowed">(
    "tables",
  );

  // Schemas state
  const [schemas, setSchemas] = useState<DatabaseSchemaResponse[]>([]);
  const [isSchemasLoading, setIsSchemasLoading] = useState(false);
  const [schemasError, setSchemasError] = useState<string | null>(null);

  // Tables state
  const [tables, setTables] = useState<DatabaseTableResponse[]>([]);
  const [isTablesLoading, setIsTablesLoading] = useState(false);
  const [tablesError, setTablesError] = useState<string | null>(null);
  const [selectedSchema, setSelectedSchema] = useState<string>("");
  const [selectedType, setSelectedType] = useState<"table" | "view" | "">("");
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedTableId, setExpandedTableId] = useState<string | null>(null);

  // Allowed Schema state
  const [allowedSchema, setAllowedSchema] =
    useState<AllowedSchemaResponse | null>(null);
  const [isAllowedLoading, setIsAllowedLoading] = useState(false);
  const [allowedError, setAllowedError] = useState<string | null>(null);

  const loadTables = useCallback(async () => {
    try {
      const res = await listDatabaseTables(connectionId, {
        schema_name: selectedSchema || undefined,
        table_type: selectedType || undefined,
        search: searchTerm || undefined,
      });
      setTablesError(null);
      setTables(res.items);
    } catch (err: unknown) {
      setTablesError(
        err instanceof Error ? err.message : "Failed to load tables",
      );
    } finally {
      setIsTablesLoading(false);
    }
  }, [connectionId, selectedSchema, selectedType, searchTerm]);

  useEffect(() => {
    let isMounted = true;
    if (activeTab === "schemas") {
      listDatabaseSchemas(connectionId)
        .then((res) => {
          if (isMounted) {
            setSchemas(res.items);
            setSchemasError(null);
            setIsSchemasLoading(false);
          }
        })
        .catch((err: unknown) => {
          if (isMounted) {
            setSchemasError(
              err instanceof Error ? err.message : "Failed to load schemas",
            );
            setIsSchemasLoading(false);
          }
        });
    } else if (activeTab === "tables") {
      listDatabaseTables(connectionId, {
        schema_name: selectedSchema || undefined,
        table_type: selectedType || undefined,
        search: searchTerm || undefined,
      })
        .then((res) => {
          if (isMounted) {
            setTables(res.items);
            setTablesError(null);
            setIsTablesLoading(false);
          }
        })
        .catch((err: unknown) => {
          if (isMounted) {
            setTablesError(
              err instanceof Error ? err.message : "Failed to load tables",
            );
            setIsTablesLoading(false);
          }
        });
    } else if (activeTab === "allowed") {
      getAllowedSchema(connectionId)
        .then((res) => {
          if (isMounted) {
            setAllowedSchema(res);
            setAllowedError(null);
            setIsAllowedLoading(false);
          }
        })
        .catch((err: unknown) => {
          if (isMounted) {
            setAllowedError(
              err instanceof Error
                ? err.message
                : "Failed to load allowed schema matrix",
            );
            setIsAllowedLoading(false);
          }
        });
    }
    return () => {
      isMounted = false;
    };
  }, [activeTab, connectionId, selectedSchema, selectedType, searchTerm]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (activeTab === "tables") {
      loadTables();
    }
  };

  return (
    <div className="space-y-4 rounded-xl border border-[var(--border)] bg-[var(--surf)] p-6">
      {/* Navigation Tabs */}
      <div className="flex border-b border-[var(--border)]">
        <button
          type="button"
          onClick={() => setActiveTab("tables")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "tables"
              ? "border-[var(--accent)] text-[var(--accent)] font-semibold"
              : "border-transparent text-[var(--fg-muted)] hover:text-[var(--fg)]"
          }`}
        >
          Tables & Views
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("schemas")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "schemas"
              ? "border-[var(--accent)] text-[var(--accent)] font-semibold"
              : "border-transparent text-[var(--fg-muted)] hover:text-[var(--fg)]"
          }`}
        >
          Schemas
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("allowed")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "allowed"
              ? "border-[var(--accent)] text-[var(--accent)] font-semibold"
              : "border-transparent text-[var(--fg-muted)] hover:text-[var(--fg)]"
          }`}
        >
          Allowed Schema Matrix
        </button>
      </div>

      {/* Tab: Tables & Views */}
      {activeTab === "tables" && (
        <div className="space-y-4">
          <form onSubmit={handleSearchSubmit} className="flex flex-wrap gap-3">
            <div className="flex-1 min-w-[200px]">
              <Input
                placeholder="Search tables..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <select
              value={selectedSchema}
              onChange={(e) => setSelectedSchema(e.target.value)}
              className="rounded-md border border-[var(--border)] bg-[var(--surf)] px-3 py-2 text-sm text-[var(--fg)]"
            >
              <option value="">All Schemas</option>
              {schemas.map((s) => (
                <option key={s.id} value={s.schema_name}>
                  {s.schema_name}
                </option>
              ))}
            </select>
            <select
              value={selectedType}
              onChange={(e) =>
                setSelectedType(e.target.value as "table" | "view" | "")
              }
              className="rounded-md border border-[var(--border)] bg-[var(--surf)] px-3 py-2 text-sm text-[var(--fg)]"
            >
              <option value="">All Types</option>
              <option value="table">Table</option>
              <option value="view">View</option>
            </select>
            <Button
              type="submit"
              className="!bg-[var(--surface-subtle)] !text-[var(--fg-default)] hover:!bg-[var(--border)]"
            >
              Filter
            </Button>
          </form>

          {tablesError && <Alert tone="danger">{tablesError}</Alert>}

          {isTablesLoading ? (
            <div className="py-8 text-center text-sm text-[var(--fg-muted)]">
              Loading catalog tables...
            </div>
          ) : tables.length === 0 ? (
            <div className="py-8 text-center text-sm text-[var(--fg-muted)] border border-dashed border-[var(--border)] rounded-lg">
              No catalog tables or views found. Perform a{" "}
              <strong>Sync Schema</strong> operation to discover tables.
            </div>
          ) : (
            <div className="space-y-2">
              {tables.map((table) => {
                const isExpanded = expandedTableId === table.id;
                return (
                  <div
                    key={table.id}
                    className="rounded-lg border border-[var(--border)] bg-[var(--surf-muted)] p-4 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm font-semibold text-[var(--fg)]">
                          {table.schema_name}.{table.table_name}
                        </span>
                        <span className="rounded bg-[var(--surf)] px-2 py-0.5 text-xs text-[var(--fg-muted)] uppercase border border-[var(--border)]">
                          {table.table_type}
                        </span>
                        {table.is_enabled && (
                          <span className="rounded bg-emerald-500/10 text-emerald-600 px-2 py-0.5 text-xs font-medium">
                            Enabled
                          </span>
                        )}
                        {table.is_sensitive && (
                          <span className="rounded bg-amber-500/10 text-amber-600 px-2 py-0.5 text-xs font-medium">
                            Sensitive
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-4 text-xs text-[var(--fg-muted)]">
                        {table.estimated_row_count !== null && (
                          <span>
                            ~{table.estimated_row_count.toLocaleString()} rows
                          </span>
                        )}
                        <span>{table.columns.length} columns</span>
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedTableId(isExpanded ? null : table.id)
                          }
                          className="rounded px-2 py-1 text-xs text-[var(--accent)] hover:bg-[var(--surf)]"
                        >
                          {isExpanded ? "Hide Columns ▲" : "View Columns ▼"}
                        </button>
                      </div>
                    </div>

                    {/* Columns Details */}
                    {isExpanded && (
                      <div className="mt-4 border-t border-[var(--border)] pt-3">
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="text-[var(--fg-muted)] border-b border-[var(--border)]">
                              <th className="py-2">Column Name</th>
                              <th className="py-2">Data Type</th>
                              <th className="py-2">Constraints</th>
                              <th className="py-2">Nullable</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[var(--border)]">
                            {table.columns.map((col) => (
                              <tr
                                key={col.id}
                                className="hover:bg-[var(--surf)]"
                              >
                                <td className="py-2 font-mono text-[var(--fg)] font-medium">
                                  {col.column_name}
                                </td>
                                <td className="py-2 text-[var(--fg-muted)]">
                                  {col.data_type}
                                </td>
                                <td className="py-2">
                                  <div className="flex gap-1">
                                    {col.is_primary_key && (
                                      <span className="rounded bg-blue-500/10 text-blue-600 px-1.5 py-0.5 text-[10px] font-bold">
                                        PK
                                      </span>
                                    )}
                                    {col.is_foreign_key && (
                                      <span
                                        className="rounded bg-purple-500/10 text-purple-600 px-1.5 py-0.5 text-[10px] font-bold"
                                        title={`FK -> ${col.referenced_schema}.${col.referenced_table}(${col.referenced_column})`}
                                      >
                                        FK
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td className="py-2 text-[var(--fg-muted)]">
                                  {col.is_nullable ? "YES" : "NO"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab: Schemas */}
      {activeTab === "schemas" && (
        <div className="space-y-4">
          {schemasError && <Alert tone="danger">{schemasError}</Alert>}

          {isSchemasLoading ? (
            <div className="py-8 text-center text-sm text-[var(--fg-muted)]">
              Loading database schemas...
            </div>
          ) : schemas.length === 0 ? (
            <div className="py-8 text-center text-sm text-[var(--fg-muted)] border border-dashed border-[var(--border)] rounded-lg">
              No database schemas cataloged yet.
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
              {schemas.map((schema) => (
                <div
                  key={schema.id}
                  className="flex items-center justify-between p-4 bg-[var(--surf-muted)]"
                >
                  <div>
                    <span className="font-mono text-sm font-semibold text-[var(--fg)]">
                      {schema.schema_name}
                    </span>
                    {schema.description && (
                      <p className="text-xs text-[var(--fg-muted)] mt-1">
                        {schema.description}
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-[var(--fg-muted)]">
                    Updated {new Date(schema.updated_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: Allowed Schema Matrix */}
      {activeTab === "allowed" && (
        <div className="space-y-4">
          {allowedError && <Alert tone="danger">{allowedError}</Alert>}

          {isAllowedLoading ? (
            <div className="py-8 text-center text-sm text-[var(--fg-muted)]">
              Resolving effective user schema permissions...
            </div>
          ) : !allowedSchema || allowedSchema.tables.length === 0 ? (
            <div className="py-8 text-center text-sm text-[var(--fg-muted)] border border-dashed border-[var(--border)] rounded-lg">
              No allowed tables resolved for current user context.
            </div>
          ) : (
            <div className="space-y-3">
              {allowedSchema.tables.map((t) => (
                <div
                  key={t.id}
                  className="rounded-lg border border-[var(--border)] bg-[var(--surf-muted)] p-4"
                >
                  <div className="font-mono text-sm font-semibold text-[var(--fg)] mb-2">
                    {t.schema_name}.{t.table_name} ({t.table_type})
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 text-xs">
                    {t.columns.map((c) => (
                      <div
                        key={c.id}
                        className="p-2 rounded border border-[var(--border)] bg-[var(--surf)]"
                      >
                        <div className="font-mono font-medium text-[var(--fg)]">
                          {c.name}
                        </div>
                        <div className="flex gap-2 mt-1 text-[10px] text-[var(--fg-muted)]">
                          <span
                            className={
                              c.readable ? "text-emerald-600" : "text-gray-400"
                            }
                          >
                            {c.readable ? "Read" : "No Read"}
                          </span>
                          <span
                            className={
                              c.filterable ? "text-blue-600" : "text-gray-400"
                            }
                          >
                            {c.filterable ? "Filter" : "No Filter"}
                          </span>
                          {c.mask_type && (
                            <span className="text-amber-600 font-semibold">
                              Mask: {c.mask_type}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
