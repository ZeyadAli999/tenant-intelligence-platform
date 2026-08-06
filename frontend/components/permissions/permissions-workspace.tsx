"use client";

import {
  AlertCircle,
  Database,
  Eye,
  Filter,
  Layers,
  Lock,
  Plus,
  RefreshCw,
  Shield,
  ShieldAlert,
  Trash2,
  User,
  Users,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { toast } from "@/components/ui/toast";
import {
  ADMINISTRATOR_DENIED_MESSAGE,
  AdministratorRequiredError,
  listTenantRoles,
  listTenantUsers,
} from "@/lib/admin-api";
import { type TenantRole, type TenantUser } from "@/lib/admin-contracts";
import {
  getAllowedSchema,
  listDatabaseConnections,
  listDatabaseTables,
} from "@/lib/database-api";
import {
  type AllowedSchemaResponse,
  type DatabaseConnectionResponse,
  type DatabaseTableResponse,
} from "@/lib/database-contracts";
import {
  createTablePermission,
  deleteTablePermission,
  getColumnPermissions,
  listTablePermissions,
  replaceColumnPermissions,
  updateTablePermission,
} from "@/lib/permission-api";
import {
  type ColumnPermissionItem,
  type MaskType,
  type RowFilterClause,
  type RowFilterDSL,
  type RowOperator,
  type TablePermissionResponse,
} from "@/lib/permission-contracts";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

const OPERATOR_LABELS: Record<RowOperator, string> = {
  eq: "Equals (=)",
  neq: "Not Equals (≠)",
  in: "In List (IN)",
  not_in: "Not In List (NOT IN)",
  gt: "Greater Than (>)",
  gte: "Greater Than or Equal (≥)",
  lt: "Less Than (<)",
  lte: "Less Than or Equal (≤)",
  is_null: "Is Null (IS NULL)",
  is_not_null: "Is Not Null (IS NOT NULL)",
};

function DialogFrame({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose(): void;
  children: React.ReactNode;
}) {
  const headingId = "permission-dialog-heading";
  const backdropRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useLayoutEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    const background = Array.from(document.body.children).filter(
      (element): element is HTMLElement =>
        element instanceof HTMLElement && element !== backdropRef.current,
    );
    background.forEach((element) => {
      element.inert = true;
    });
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();
    return () => {
      background.forEach((element) => {
        element.inert = false;
      });
      document.body.style.overflow = previousOverflow;
      trigger?.focus();
    };
  }, []);

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(
      backdropRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    ).filter((element) => !element.hidden);
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        onKeyDown={handleKeyDown}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-5 shadow-xl sm:p-6"
      >
        <div className="mb-5 flex items-center justify-between gap-4 border-b border-[var(--border)] pb-4">
          <h2 id={headingId} className="text-lg font-semibold">
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            aria-label="Close dialog"
            onClick={onClose}
            className="icon-button"
          >
            <X aria-hidden className="h-4 w-4" />
          </button>
        </div>
        {children}
      </section>
    </div>,
    document.body,
  );
}

function RevokeDialog({
  tableName,
  subjectName,
  onClose,
  onConfirm,
}: {
  tableName: string;
  subjectName: string;
  onClose(): void;
  onConfirm(): Promise<void>;
}) {
  const [revoking, setRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRevoke() {
    setRevoking(true);
    setError(null);
    try {
      await onConfirm();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Failed to revoke permission.",
      );
      setRevoking(false);
    }
  }

  return (
    <DialogFrame title="Revoke Table Permission" onClose={onClose}>
      <div className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <p className="text-sm text-[var(--text-secondary)]">
          Are you sure you want to revoke table permissions for{" "}
          <strong className="font-semibold text-[var(--text-primary)]">
            {tableName}
          </strong>{" "}
          assigned to{" "}
          <strong className="font-semibold text-[var(--text-primary)]">
            {subjectName}
          </strong>
          ?
        </p>
        <p className="text-xs text-[var(--text-muted)]">
          Revoking this permission restores default-deny behavior for this table
          unless another role or user policy applies.
        </p>
        <div className="flex justify-end gap-3 border-t border-[var(--border)] pt-4">
          <button
            type="button"
            onClick={onClose}
            className="secondary-button"
            disabled={revoking}
          >
            Cancel
          </button>
          <button
            type="button"
            className="danger-button min-h-10 px-4 text-sm font-semibold"
            onClick={handleRevoke}
            disabled={revoking}
          >
            {revoking ? "Revoking…" : "Revoke permission"}
          </button>
        </div>
      </div>
    </DialogFrame>
  );
}

export function PermissionsWorkspace() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);

  // Core collections
  const [connections, setConnections] = useState<DatabaseConnectionResponse[]>(
    [],
  );
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [roles, setRoles] = useState<TenantRole[]>([]);

  // Subject selection state
  const [subjectType, setSubjectType] = useState<"user" | "role">("user");
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [selectedRoleId, setSelectedRoleId] = useState<string>("");

  // Connection & Catalog selection state
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [tables, setTables] = useState<DatabaseTableResponse[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string>("");

  // Active permission state for selected (connection, table, subject)
  const [permissions, setPermissions] = useState<TablePermissionResponse[]>(
    [],
  );
  const [activePermission, setActivePermission] =
    useState<TablePermissionResponse | null>(null);
  const [columnPermissions, setColumnPermissions] = useState<
    ColumnPermissionItem[]
  >([]);

  // Row Filter State
  const [rowFilterClauses, setRowFilterClauses] = useState<RowFilterClause[]>(
    [],
  );

  // Allowed Schema Preview state
  const [allowedSchema, setAllowedSchema] =
    useState<AllowedSchemaResponse | null>(null);
  const [loadingAllowedSchema, setLoadingAllowedSchema] = useState(false);

  // Status & action messages
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [savingPermission, setSavingPermission] = useState(false);
  const [showRevokeDialog, setShowRevokeDialog] = useState(false);

  const handleError = useCallback((reason: unknown) => {
    if (reason instanceof AdministratorRequiredError) {
      setDenied(true);
      setError(null);
      return;
    }
    setError(
      reason instanceof Error
        ? reason.message
        : "Permissions workspace is unavailable.",
    );
  }, []);

  // Initialize main dropdown data (connections, users, roles)
  useEffect(() => {
    let active = true;
    void Promise.all([
      listDatabaseConnections(1, 100),
      listTenantUsers("", ""),
      listTenantRoles(),
    ])
      .then(([connPage, userPage, rolePage]) => {
        if (!active) return;
        setConnections(connPage.items);
        setUsers(userPage.items);
        setRoles(rolePage.items);
        if (connPage.items.length > 0) {
          setSelectedConnectionId(connPage.items[0].id);
        }
        if (userPage.items.length > 0) {
          setSelectedUserId(userPage.items[0].id);
        }
        if (rolePage.items.length > 0) {
          setSelectedRoleId(rolePage.items[0].id);
        }
      })
      .catch((reason) => {
        if (active) handleError(reason);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [handleError]);

  // Load catalog tables when selected connection changes
  useEffect(() => {
    let active = true;
    if (!selectedConnectionId) {
      Promise.resolve().then(() => {
        if (!active) return;
        setTables([]);
        setSelectedTableId("");
      });
      return () => {
        active = false;
      };
    }
    void listDatabaseTables(selectedConnectionId, { page: 1, page_size: 100 })
      .then((tablePage) => {
        if (!active) return;
        setTables(tablePage.items);
        if (tablePage.items.length > 0) {
          setSelectedTableId(tablePage.items[0].id);
        } else {
          setSelectedTableId("");
        }
      })
      .catch(() => {
        if (active) setActionError("Failed to load catalog tables.");
      });
    return () => {
      active = false;
    };
  }, [selectedConnectionId]);

  // Load allowed schema preview for selected connection
  const loadAllowedSchema = useCallback(async () => {
    if (!selectedConnectionId) return;
    setLoadingAllowedSchema(true);
    try {
      const res = await getAllowedSchema(selectedConnectionId);
      setAllowedSchema(res);
    } catch {
      setAllowedSchema(null);
    } finally {
      setLoadingAllowedSchema(false);
    }
  }, [selectedConnectionId]);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => {
      if (active) void loadAllowedSchema();
    });
    return () => {
      active = false;
    };
  }, [loadAllowedSchema]);

  // Load existing table & column permissions for the current selection
  const refreshPermissions = useCallback(async () => {
    if (!selectedConnectionId) return;
    setActionError(null);

    const activeUserId =
      subjectType === "user" && selectedUserId ? selectedUserId : undefined;
    const activeRoleId =
      subjectType === "role" && selectedRoleId ? selectedRoleId : undefined;

    try {
      const page = await listTablePermissions({
        connection_id: selectedConnectionId,
        table_id: selectedTableId || undefined,
        user_id: activeUserId,
        role_id: activeRoleId,
        page: 1,
        page_size: 100,
      });
      setPermissions(page.items);

      const matching = page.items.find(
        (item) => item.table_id === selectedTableId,
      );
      if (matching) {
        setActivePermission(matching);
        // Load column permissions for matching table permission
        const colRes = await getColumnPermissions(matching.id);
        const currentTbl = tables.find((t) => t.id === selectedTableId);
        if (currentTbl) {
          const merged = currentTbl.columns.map((col) => {
            const isSens = "is_sensitive" in col ? Boolean(col.is_sensitive) : false;
            const existing = colRes.items.find((item) => item.column_id === col.id);
            if (existing) {
              return {
                column_id: col.id,
                can_read: existing.can_read,
                can_filter: existing.can_filter,
                can_aggregate: existing.can_aggregate,
                mask_type: existing.mask_type,
              };
            }
            return {
              column_id: col.id,
              can_read: true,
              can_filter: true,
              can_aggregate: true,
              mask_type: isSens ? ("redact" as MaskType) : null,
            };
          });
          setColumnPermissions(merged);
        } else {
          setColumnPermissions(colRes.items);
        }

        // Load row filter clauses
        if (matching.row_filter && Array.isArray(matching.row_filter.all)) {
          setRowFilterClauses(matching.row_filter.all as RowFilterClause[]);
        } else {
          setRowFilterClauses([]);
        }
      } else {
        setActivePermission(null);
        // Default column permission state based on table columns
        const currentTbl = tables.find((t) => t.id === selectedTableId);
        if (currentTbl) {
          setColumnPermissions(
            currentTbl.columns.map((c) => {
              const isSens = "is_sensitive" in c ? Boolean(c.is_sensitive) : false;
              return {
                column_id: c.id,
                can_read: true,
                can_filter: true,
                can_aggregate: true,
                mask_type: isSens ? ("redact" as MaskType) : null,
              };
            }),
          );
        } else {
          setColumnPermissions([]);
        }
        setRowFilterClauses([]);
      }
    } catch (reason) {
      handleError(reason);
    }
  }, [
    selectedConnectionId,
    selectedTableId,
    subjectType,
    selectedUserId,
    selectedRoleId,
    tables,
    handleError,
  ]);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => {
      if (active) void refreshPermissions();
    });
    return () => {
      active = false;
    };
  }, [refreshPermissions]);

  useEffect(() => {
    if (actionSuccess) {
      const timer = setTimeout(() => {
        setActionSuccess(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [actionSuccess]);

  const clearFeedback = useCallback(() => {
    setActionSuccess(null);
    setActionError(null);
  }, []);

  const currentTable = tables.find((t) => t.id === selectedTableId);
  const currentSubjectName =
    subjectType === "user"
      ? users.find((u) => u.id === selectedUserId)?.full_name ||
        users.find((u) => u.id === selectedUserId)?.email ||
        "User"
      : roles.find((r) => r.id === selectedRoleId)?.name || "Role";

  // Action: Toggle or save Table Permission (`can_read`)
  async function handleSaveTablePermission(canRead: boolean) {
    if (savingPermission || !selectedConnectionId || !selectedTableId) return;
    setSavingPermission(true);
    clearFeedback();

    const validFilter: RowFilterDSL | null =
      rowFilterClauses.length > 0
        ? { version: 1, all: rowFilterClauses }
        : null;

    try {
      if (activePermission) {
        // Update permission
        await updateTablePermission(activePermission.id, {
          can_read: canRead,
          row_filter: validFilter,
        });
        const msg = "Table permission updated successfully.";
        setActionSuccess(msg);
        toast.success(msg);
      } else {
        // Create permission
        await createTablePermission({
          connection_id: selectedConnectionId,
          table_id: selectedTableId,
          user_id: subjectType === "user" ? selectedUserId : undefined,
          role_id: subjectType === "role" ? selectedRoleId : undefined,
          can_read: canRead,
          row_filter: validFilter,
        });
        const msg = "Table permission created successfully.";
        setActionSuccess(msg);
        toast.success(msg);
      }
      await refreshPermissions();
      await loadAllowedSchema();
    } catch (reason) {
      const msg =
        reason instanceof Error
          ? reason.message
          : "Failed to save table permission.";
      setActionError(msg);
      toast.error(msg);
    } finally {
      setSavingPermission(false);
    }
  }

  // Action: Save Row Filter
  async function handleSaveRowFilters() {
    if (savingPermission || !selectedConnectionId || !selectedTableId) return;
    setSavingPermission(true);
    clearFeedback();

    const canRead = activePermission ? activePermission.can_read : true;
    const validFilter: RowFilterDSL | null =
      rowFilterClauses.length > 0
        ? { version: 1, all: rowFilterClauses }
        : null;

    try {
      if (activePermission) {
        await updateTablePermission(activePermission.id, {
          can_read: canRead,
          row_filter: validFilter,
        });
      } else {
        await createTablePermission({
          connection_id: selectedConnectionId,
          table_id: selectedTableId,
          user_id: subjectType === "user" ? selectedUserId : undefined,
          role_id: subjectType === "role" ? selectedRoleId : undefined,
          can_read: canRead,
          row_filter: validFilter,
        });
      }
      const msg = "Row filter saved successfully.";
      setActionSuccess(msg);
      toast.success(msg);
      await refreshPermissions();
      await loadAllowedSchema();
    } catch (reason) {
      const msg =
        reason instanceof Error
          ? reason.message
          : "Failed to save row filter.";
      setActionError(msg);
      toast.error(msg);
    } finally {
      setSavingPermission(false);
    }
  }

  // Action: Save Column Permissions
  async function handleSaveColumnPermissions() {
    if (savingPermission || !activePermission) {
      if (!activePermission) {
        const msg = "Save or enable table read access before configuring column permissions.";
        setActionError(msg);
        toast.error(msg);
      }
      return;
    }
    setSavingPermission(true);
    clearFeedback();
    try {
      await replaceColumnPermissions(activePermission.id, columnPermissions);
      const msg = "Column rules saved successfully.";
      setActionSuccess(msg);
      toast.success(msg);
      await refreshPermissions();
      await loadAllowedSchema();
    } catch (reason) {
      const msg =
        reason instanceof Error
          ? reason.message
          : "Failed to save column permissions.";
      setActionError(msg);
      toast.error(msg);
    } finally {
      setSavingPermission(false);
    }
  }

  function updateColumnPermission(
    colId: string,
    isSens: boolean,
    patch: Partial<ColumnPermissionItem>,
  ) {
    setColumnPermissions((prev) => {
      const index = prev.findIndex((cp) => cp.column_id === colId);
      if (index >= 0) {
        const next = [...prev];
        next[index] = { ...next[index], ...patch };
        return next;
      }
      const defaultPerm: ColumnPermissionItem = {
        column_id: colId,
        can_read: true,
        can_filter: true,
        can_aggregate: true,
        mask_type: isSens ? "redact" : null,
        ...patch,
      };
      return [...prev, defaultPerm];
    });
  }

  // Action: Revoke Table Permission
  async function handleRevokePermission() {
    if (savingPermission || !activePermission) return;
    setSavingPermission(true);
    clearFeedback();
    try {
      await deleteTablePermission(activePermission.id);
      setShowRevokeDialog(false);
      const msg = "Table permission revoked successfully.";
      setActionSuccess(msg);
      toast.success(msg);
      await refreshPermissions();
      await loadAllowedSchema();
    } catch (reason) {
      const msg =
        reason instanceof Error
          ? reason.message
          : "Failed to revoke table permission.";
      setActionError(msg);
      toast.error(msg);
    } finally {
      setSavingPermission(false);
    }
  }

  if (denied) return <Alert>{ADMINISTRATOR_DENIED_MESSAGE}</Alert>;
  if (loading) return <LoadingState label="Loading Permissions Workspace…" />;
  if (error)
    return <ErrorState title="Permissions unavailable" message={error} />;

  const currentConnection = connections.find(
    (c) => c.id === selectedConnectionId,
  );
  const isConnectionUnsynced =
    currentConnection &&
    currentConnection.schema_sync_status !== "synced" &&
    currentConnection.schema_sync_status !== "completed";

  return (
    <section aria-labelledby="permissions-heading" className="space-y-6">
      <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-[var(--primary)]">
            Administration
          </p>
          <h1 className="mt-1 text-2xl font-semibold" id="permissions-heading">
            Permissions
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-[var(--text-secondary)]">
            Manage granular tenant-isolated permissions for database tables, columns, data masking, and parameterized row filters.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void refreshPermissions()}
            className="secondary-button min-h-10 px-4 text-sm font-semibold inline-flex items-center gap-2"
          >
            <RefreshCw aria-hidden className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </header>

      {/* Global Alerts */}
      {actionError && <Alert>{actionError}</Alert>}

      {/* Empty State checks */}
      {connections.length === 0 ? (
        <EmptyState
          title="No database connections available"
          message="Create and synchronize a database connection in the Databases workspace before configuring table permissions."
        />
      ) : users.length === 0 && roles.length === 0 ? (
        <EmptyState
          title="No users or roles available"
          message="Create tenant users or roles in the Users workspace to manage target permission subjects."
        />
      ) : (
        <>
          {/* Controls Bar: Connection & Subject Selection */}
          <div className="grid gap-4 rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] p-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Database Connection Picker */}
            <label className="block text-sm font-medium">
              <span className="flex items-center gap-2 text-[var(--text-secondary)] mb-1.5">
                <Database aria-hidden className="h-4 w-4 text-[var(--primary)]" />
                Database Connection
              </span>
              <select
                value={selectedConnectionId}
                onChange={(e) => {
                  clearFeedback();
                  setSelectedConnectionId(e.target.value);
                }}
                className="field w-full h-10"
              >
                {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name} ({conn.database_name})
                  </option>
                ))}
              </select>
            </label>

            {/* Subject Type Toggle & Selection */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-sm font-medium">
                <span className="flex items-center gap-2 text-[var(--text-secondary)]">
                  {subjectType === "user" ? (
                    <User aria-hidden className="h-4 w-4 text-[var(--primary)]" />
                  ) : (
                    <Users aria-hidden className="h-4 w-4 text-[var(--primary)]" />
                  )}
                  Target Subject
                </span>
                <div className="inline-flex rounded-md border border-[var(--border-strong)] p-0.5 bg-[var(--surface-subtle)]">
                  <button
                    type="button"
                    onClick={() => {
                      clearFeedback();
                      setSubjectType("user");
                    }}
                    className={`px-2 py-0.5 text-xs font-medium rounded ${
                      subjectType === "user"
                        ? "bg-[var(--surface)] shadow-xs text-[var(--text-primary)]"
                        : "text-[var(--text-muted)]"
                    }`}
                  >
                    User
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      clearFeedback();
                      setSubjectType("role");
                    }}
                    className={`px-2 py-0.5 text-xs font-medium rounded ${
                      subjectType === "role"
                        ? "bg-[var(--surface)] shadow-xs text-[var(--text-primary)]"
                        : "text-[var(--text-muted)]"
                    }`}
                  >
                    Role
                  </button>
                </div>
              </div>

              {subjectType === "user" ? (
                <select
                  value={selectedUserId}
                  onChange={(e) => {
                    clearFeedback();
                    setSelectedUserId(e.target.value);
                  }}
                  className="field w-full h-10"
                  disabled={users.length === 0}
                >
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name ? `${u.full_name} (${u.email})` : u.email}
                    </option>
                  ))}
                </select>
              ) : (
                <select
                  value={selectedRoleId}
                  onChange={(e) => {
                    clearFeedback();
                    setSelectedRoleId(e.target.value);
                  }}
                  className="field w-full h-10"
                  disabled={roles.length === 0}
                >
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Current Subject Badge & Status */}
            <div className="flex flex-col justify-between rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] p-3 sm:col-span-2 lg:col-span-1">
              <span className="text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                Selected Context
              </span>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-sm font-semibold truncate">
                  {currentSubjectName}
                </span>
                <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--primary)_12%,var(--surface))] px-2.5 py-0.5 text-xs font-medium text-[var(--primary)]">
                  {subjectType === "user" ? "Explicit User" : "Role Scope"}
                </span>
              </div>
            </div>
          </div>

          {/* Warning for Unsynced Connection */}
          {isConnectionUnsynced && (
            <div className="flex items-center gap-3 rounded-lg border border-[var(--warning)] bg-[color-mix(in_srgb,var(--warning)_10%,var(--surface))] p-4 text-sm">
              <AlertCircle className="h-5 w-5 text-[var(--warning)] shrink-0" />
              <div>
                <p className="font-semibold text-[var(--text-primary)]">
                  Connection Unsynchronized
                </p>
                <p className="text-[var(--text-secondary)] mt-0.5">
                  Schema metadata is unsynchronized. Sync this database connection in
                  the Databases workspace to ensure accurate table and column rules.
                </p>
              </div>
            </div>
          )}

          {/* Table List and Permission Rules Grid */}
          {tables.length === 0 ? (
            <EmptyState
              title="No database tables found"
              message="No catalog tables exist for this connection. Ensure the database connection has been synchronized."
            />
          ) : (
            <div className="grid gap-6 lg:grid-cols-12">
              {/* Left Column: Table Navigation List */}
              <div className="lg:col-span-4 space-y-3">
                <div className="flex items-center justify-between px-1">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-2">
                    <Layers aria-hidden className="h-4 w-4" />
                    Catalog Tables ({tables.length})
                  </h2>
                </div>

                <div className="max-h-[540px] overflow-y-auto rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] divide-y divide-[var(--border)]">
                  {tables.map((t) => {
                    const isSelected = t.id === selectedTableId;
                    const hasPerm = permissions.some((p) => p.table_id === t.id);
                    const permObj = permissions.find((p) => p.table_id === t.id);

                    return (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => {
                          clearFeedback();
                          setSelectedTableId(t.id);
                        }}
                        className={`w-full p-3 text-left transition-colors flex items-center justify-between gap-3 ${
                          isSelected
                            ? "bg-[color-mix(in_srgb,var(--primary)_10%,var(--surface))] font-medium border-l-4 border-l-[var(--primary)]"
                            : "hover:bg-[var(--surface-subtle)]"
                        }`}
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold truncate text-[var(--text-primary)]">
                            {t.table_name}
                          </p>
                          <p className="text-xs text-[var(--text-muted)] truncate">
                            {t.schema_name} • {t.columns.length} columns
                          </p>
                        </div>

                        {hasPerm ? (
                          permObj?.can_read ? (
                            <span className="shrink-0 rounded bg-[color-mix(in_srgb,var(--success)_15%,var(--surface))] px-2 py-0.5 text-xs font-semibold text-[var(--success)]">
                              Allowed
                            </span>
                          ) : (
                            <span className="shrink-0 rounded bg-[color-mix(in_srgb,var(--danger)_15%,var(--surface))] px-2 py-0.5 text-xs font-semibold text-[var(--danger)]">
                              Denied
                            </span>
                          )
                        ) : (
                          <span className="shrink-0 rounded bg-[var(--surface-subtle)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
                            Default Deny
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Permission Editor & Details */}
              <div className="lg:col-span-8 space-y-6">
                {currentTable && (
                  <>
                    {/* Table Permission Status & Read Access Header */}
                    <div className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] p-5 space-y-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-lg font-semibold">
                              {currentTable.schema_name}.{currentTable.table_name}
                            </h3>
                            <span className="rounded-full border border-[var(--border-strong)] px-2.5 py-0.5 text-xs font-medium">
                              {currentTable.table_type}
                            </span>
                          </div>
                          <p className="text-xs text-[var(--text-muted)] mt-1">
                            Subject:{" "}
                            <strong className="text-[var(--text-primary)]">
                              {currentSubjectName}
                            </strong>
                          </p>
                        </div>

                        {activePermission && (
                          <button
                            type="button"
                            className="danger-button min-h-9 px-3 py-1.5 text-xs inline-flex items-center gap-1.5"
                            onClick={() => setShowRevokeDialog(true)}
                          >
                            <Trash2 aria-hidden className="h-3.5 w-3.5" />
                            Revoke Table Permission
                          </button>
                        )}
                      </div>

                      {/* Read Permission Controls */}
                      <div className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] p-4">
                        <div className="space-y-0.5">
                          <label
                            htmlFor="can-read-toggle"
                            className="text-sm font-semibold flex items-center gap-2 cursor-pointer"
                          >
                            <Eye className="h-4 w-4 text-[var(--primary)]" />
                            Table Read Access (`can_read`)
                          </label>
                          <p className="text-xs text-[var(--text-muted)]">
                            Enable or disable read/query authorization for this table.
                          </p>
                        </div>

                        <div className="flex items-center gap-3">
                          <input
                            id="can-read-toggle"
                            type="checkbox"
                            checked={
                              activePermission
                                ? activePermission.can_read
                                : false
                            }
                            onChange={(e) =>
                              void handleSaveTablePermission(e.target.checked)
                            }
                            disabled={savingPermission}
                            className="h-5 w-5 rounded border-[var(--border-strong)] text-[var(--primary)] focus:ring-[var(--primary)]"
                          />
                          <span className="text-sm font-medium">
                            {activePermission?.can_read ? "Enabled" : "Disabled"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Column Permission Editor */}
                    <div className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] p-5 space-y-4">
                      <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
                        <div>
                          <h3 className="text-sm font-semibold flex items-center gap-2">
                            <Shield className="h-4 w-4 text-[var(--primary)]" />
                            Column Access & Masking Controls
                          </h3>
                          <p className="text-xs text-[var(--text-muted)] mt-0.5">
                            Configure readable, filterable, aggregatable flags and masking policies per column.
                          </p>
                        </div>
                        <Button
                          type="button"
                          onClick={() => void handleSaveColumnPermissions()}
                          disabled={savingPermission || !activePermission}
                          className="min-h-9 text-xs"
                        >
                          {savingPermission ? "Saving..." : "Save Column Rules"}
                        </Button>
                      </div>

                      {!activePermission ? (
                        <p className="text-xs text-[var(--text-muted)] italic py-2">
                          Enable read access or save table permission to configure column capabilities.
                        </p>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-xs">
                            <thead className="border-b border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--text-secondary)] font-semibold uppercase tracking-wider">
                              <tr>
                                <th scope="col" className="px-3 py-2">Column</th>
                                <th scope="col" className="px-3 py-2">Type</th>
                                <th scope="col" className="px-3 py-2 text-center">Read</th>
                                <th scope="col" className="px-3 py-2 text-center">Filter</th>
                                <th scope="col" className="px-3 py-2 text-center">Aggregate</th>
                                <th scope="col" className="px-3 py-2">Masking Policy</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--border)]">
                              {currentTable.columns.map((col) => {
                                const isSens = "is_sensitive" in col ? Boolean(col.is_sensitive) : false;
                                const currentPerm = columnPermissions.find(
                                  (cp) => cp.column_id === col.id,
                                ) || {
                                  column_id: col.id,
                                  can_read: true,
                                  can_filter: true,
                                  can_aggregate: true,
                                  mask_type: isSens ? "redact" : null,
                                };

                                return (
                                  <tr key={col.id} className="hover:bg-[var(--surface-subtle)]">
                                    <td className="px-3 py-2.5 font-medium">
                                      <div className="flex items-center gap-1.5">
                                        <span>{col.column_name}</span>
                                        {isSens && (
                                          <span className="rounded bg-[color-mix(in_srgb,var(--warning)_20%,var(--surface))] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--warning)]">
                                            Sensitive
                                          </span>
                                        )}
                                      </div>
                                    </td>
                                    <td className="px-3 py-2.5 text-[var(--text-muted)]">
                                      {col.data_type}
                                    </td>
                                    <td className="px-3 py-2.5 text-center">
                                      <input
                                        type="checkbox"
                                        aria-label={`Read access for ${col.column_name}`}
                                        checked={currentPerm.can_read}
                                        onChange={(e) => {
                                          updateColumnPermission(col.id, isSens, {
                                            can_read: e.target.checked,
                                          });
                                        }}
                                      />
                                    </td>
                                    <td className="px-3 py-2.5 text-center">
                                      <input
                                        type="checkbox"
                                        aria-label={`Filter capability for ${col.column_name}`}
                                        checked={currentPerm.can_filter}
                                        onChange={(e) => {
                                          updateColumnPermission(col.id, isSens, {
                                            can_filter: e.target.checked,
                                          });
                                        }}
                                      />
                                    </td>
                                    <td className="px-3 py-2.5 text-center">
                                      <input
                                        type="checkbox"
                                        aria-label={`Aggregate capability for ${col.column_name}`}
                                        checked={currentPerm.can_aggregate}
                                        onChange={(e) => {
                                          updateColumnPermission(col.id, isSens, {
                                            can_aggregate: e.target.checked,
                                          });
                                        }}
                                      />
                                    </td>
                                    <td className="px-3 py-2.5">
                                      <select
                                        aria-label={`Masking policy for ${col.column_name}`}
                                        value={currentPerm.mask_type || ""}
                                        onChange={(e) => {
                                          const val = e.target.value
                                            ? (e.target.value as MaskType)
                                            : null;
                                          updateColumnPermission(col.id, isSens, {
                                            mask_type: val,
                                          });
                                        }}
                                        className="field text-xs py-1 px-2 h-8 w-full"
                                      >
                                        <option value="">None (Unmasked)</option>
                                        <option value="redact">Redact</option>
                                        <option value="partial">Partial</option>
                                        <option value="hash">Hash</option>
                                        <option value="null">Null</option>
                                      </select>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>

                    {/* Structured Row Filter Builder */}
                    <div className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] p-5 space-y-4">
                      <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
                        <div>
                          <h3 className="text-sm font-semibold flex items-center gap-2">
                            <Filter className="h-4 w-4 text-[var(--primary)]" />
                            Structured Parameterized Row Filters
                          </h3>
                          <p className="text-xs text-[var(--text-muted)] mt-0.5">
                            Define backend-enforced row filtering conditions using column specifications and context/literal values.
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            className="secondary-button min-h-9 px-3 text-xs inline-flex items-center gap-1.5"
                            onClick={() => {
                              if (currentTable.columns.length > 0) {
                                setRowFilterClauses([
                                  ...rowFilterClauses,
                                  {
                                    column_id: currentTable.columns[0].id,
                                    operator: "eq",
                                    value: {
                                      source: "context",
                                      value: "current_user_id",
                                    },
                                  },
                                ]);
                              }
                            }}
                            disabled={
                              rowFilterClauses.length >= 20 ||
                              currentTable.columns.length === 0
                            }
                          >
                            <Plus aria-hidden className="h-3.5 w-3.5" />
                            Add Rule
                          </button>
                          <Button
                            type="button"
                            onClick={() => void handleSaveRowFilters()}
                            disabled={savingPermission || !activePermission}
                            className="min-h-9 text-xs"
                          >
                            {savingPermission ? "Saving..." : "Save Row Filter"}
                          </Button>
                        </div>
                      </div>

                      {rowFilterClauses.length === 0 ? (
                        <p className="text-xs text-[var(--text-muted)] italic py-2">
                          No row filter rules configured. All rows will be accessible if table read permission is enabled.
                        </p>
                      ) : (
                        <div className="space-y-3">
                          {rowFilterClauses.map((clause, idx) => {
                            const isNullOp =
                              clause.operator === "is_null" ||
                              clause.operator === "is_not_null";
                            const isSetOp =
                              clause.operator === "in" ||
                              clause.operator === "not_in";
                            const valSource = clause.value?.source || "literal";

                            return (
                              <div
                                key={idx}
                                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[auto_minmax(130px,1.2fr)_minmax(130px,1fr)_minmax(100px,auto)_minmax(140px,1.5fr)_40px] items-center gap-3 rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] p-3"
                              >
                                {/* 1. Rule Label */}
                                <span className="text-xs font-semibold text-[var(--text-muted)] whitespace-nowrap shrink-0 self-center">
                                  Rule #{idx + 1}
                                </span>

                                {/* 2. Column Selector */}
                                <select
                                  aria-label={`Column for rule ${idx + 1}`}
                                  value={clause.column_id}
                                  onChange={(e) => {
                                    const updated = [...rowFilterClauses];
                                    updated[idx] = {
                                      ...updated[idx],
                                      column_id: e.target.value,
                                    };
                                    setRowFilterClauses(updated);
                                  }}
                                  className="field text-xs h-9 w-full min-w-[130px]"
                                >
                                  {currentTable.columns.map((col) => (
                                    <option key={col.id} value={col.id}>
                                      {col.column_name} ({col.data_type})
                                    </option>
                                  ))}
                                </select>

                                {/* 3. Operator Selector */}
                                <select
                                  aria-label={`Operator for rule ${idx + 1}`}
                                  value={clause.operator}
                                  onChange={(e) => {
                                    const newOp = e.target.value as RowOperator;
                                    const updated = [...rowFilterClauses];
                                    const nullOp =
                                      newOp === "is_null" ||
                                      newOp === "is_not_null";

                                    updated[idx] = {
                                      ...updated[idx],
                                      operator: newOp,
                                      value: nullOp
                                        ? null
                                        : updated[idx].value || {
                                            source: "literal",
                                            value: "",
                                          },
                                    };
                                    setRowFilterClauses(updated);
                                  }}
                                  className="field text-xs h-9 w-full min-w-[130px]"
                                >
                                  {(
                                    Object.keys(OPERATOR_LABELS) as RowOperator[]
                                  ).map((op) => (
                                    <option key={op} value={op}>
                                      {OPERATOR_LABELS[op]}
                                    </option>
                                  ))}
                                </select>

                                {/* 4. Value Source & 5. Value Control */}
                                {!isNullOp ? (
                                  <>
                                    <select
                                      aria-label={`Value source for rule ${idx + 1}`}
                                      value={valSource}
                                      onChange={(e) => {
                                        const src = e.target.value as
                                          | "literal"
                                          | "context";
                                        const updated = [...rowFilterClauses];
                                        updated[idx] = {
                                          ...updated[idx],
                                          value: {
                                            source: src,
                                            value:
                                              src === "context"
                                                ? "current_user_id"
                                                : isSetOp
                                                ? []
                                                : "",
                                          },
                                        };
                                        setRowFilterClauses(updated);
                                      }}
                                      className="field text-xs h-9 w-full min-w-[100px]"
                                    >
                                      <option value="literal">Literal</option>
                                      <option value="context">Context</option>
                                    </select>

                                    {valSource === "context" ? (
                                      <select
                                        aria-label={`Context value for rule ${idx + 1}`}
                                        value={
                                          (clause.value?.value as string) ||
                                          "current_user_id"
                                        }
                                        onChange={(e) => {
                                          const updated = [...rowFilterClauses];
                                          updated[idx] = {
                                            ...updated[idx],
                                            value: {
                                              source: "context",
                                              value: e.target.value,
                                            },
                                          };
                                          setRowFilterClauses(updated);
                                        }}
                                        className="field text-xs h-9 w-full min-w-[140px]"
                                      >
                                        <option value="current_user_id">
                                          current_user_id
                                        </option>
                                        <option value="current_tenant_id">
                                          current_tenant_id
                                        </option>
                                      </select>
                                    ) : isSetOp ? (
                                      <Input
                                        aria-label={`Literal value list for rule ${idx + 1}`}
                                        type="text"
                                        placeholder="Comma-separated values, e.g. val1, val2"
                                        value={
                                          Array.isArray(clause.value?.value)
                                            ? (
                                                clause.value?.value as string[]
                                              ).join(", ")
                                            : (clause.value?.value as string) ||
                                              ""
                                        }
                                        onChange={(e) => {
                                          const items = e.target.value
                                            .split(",")
                                            .map((s) => s.trim())
                                            .filter(Boolean);
                                          const updated = [...rowFilterClauses];
                                          updated[idx] = {
                                            ...updated[idx],
                                            value: {
                                              source: "literal",
                                              value: items,
                                            },
                                          };
                                          setRowFilterClauses(updated);
                                        }}
                                        className="h-9 text-xs w-full min-w-[140px]"
                                      />
                                    ) : (
                                      <Input
                                        aria-label={`Literal value for rule ${idx + 1}`}
                                        type="text"
                                        placeholder="Value"
                                        value={
                                          (clause.value?.value as string) || ""
                                        }
                                        onChange={(e) => {
                                          const updated = [...rowFilterClauses];
                                          updated[idx] = {
                                            ...updated[idx],
                                            value: {
                                              source: "literal",
                                              value: e.target.value,
                                            },
                                          };
                                          setRowFilterClauses(updated);
                                        }}
                                        className="h-9 text-xs w-full min-w-[140px]"
                                      />
                                    )}
                                  </>
                                ) : (
                                  <div className="lg:col-span-2 text-xs text-[var(--text-muted)] italic self-center px-1">
                                    No value required
                                  </div>
                                )}

                                {/* 6. Remove Rule Button */}
                                <button
                                  type="button"
                                  onClick={() => {
                                    setRowFilterClauses(
                                      rowFilterClauses.filter(
                                        (_, i) => i !== idx,
                                      ),
                                    );
                                  }}
                                  className="h-10 w-10 min-h-[40px] min-w-[40px] shrink-0 flex items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)] hover:text-[var(--danger)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:ring-offset-2 transition-colors justify-self-end sm:justify-self-center lg:justify-self-end"
                                  aria-label={`Remove rule ${idx + 1}`}
                                  title="Remove rule"
                                >
                                  <X aria-hidden className="h-4 w-4" />
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </>
                )}

                {/* Effective Access Preview Section */}
                <div className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
                    <div>
                      <h3 className="text-sm font-semibold flex items-center gap-2">
                        <Lock className="h-4 w-4 text-[var(--primary)]" />
                        Effective Allowed Schema Preview
                      </h3>
                      <p className="text-xs text-[var(--text-muted)] mt-0.5">
                        Live resolution derived from union of user and role grants for the active session.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="secondary-button min-h-8 text-xs px-2.5 inline-flex items-center gap-1.5"
                      onClick={() => void loadAllowedSchema()}
                      disabled={loadingAllowedSchema}
                    >
                      <RefreshCw
                        aria-hidden
                        className={`h-3.5 w-3.5 ${
                          loadingAllowedSchema ? "animate-spin" : ""
                        }`}
                      />
                      Refresh Preview
                    </button>
                  </div>

                  {loadingAllowedSchema ? (
                    <LoadingState label="Resolving effective allowed schema…" />
                  ) : !allowedSchema || allowedSchema.tables.length === 0 ? (
                    <EmptyState
                      title="No effective allowed tables"
                      message="No catalog tables are currently queryable by the current user session under existing permissions."
                    />
                  ) : (
                    <div className="space-y-3">
                      {allowedSchema.tables.map((tbl) => (
                        <details
                          key={tbl.id}
                          className="rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] p-3 group"
                        >
                          <summary className="cursor-pointer font-semibold text-xs flex items-center justify-between">
                            <span className="flex items-center gap-2">
                              <ShieldAlert className="h-3.5 w-3.5 text-[var(--success)]" />
                              {tbl.schema_name}.{tbl.table_name} ({tbl.table_type})
                            </span>
                            <span className="text-[var(--text-muted)] font-normal">
                              {tbl.columns.length} queryable columns
                            </span>
                          </summary>
                          <div className="mt-3 border-t border-[var(--border)] pt-2 overflow-x-auto">
                            <table className="w-full text-left text-[11px]">
                              <thead className="text-[var(--text-muted)] border-b border-[var(--border)]">
                                <tr>
                                  <th className="py-1 px-2">Column</th>
                                  <th className="py-1 px-2">Data Type</th>
                                  <th className="py-1 px-2 text-center">Read</th>
                                  <th className="py-1 px-2 text-center">Filter</th>
                                  <th className="py-1 px-2 text-center">Aggregate</th>
                                  <th className="py-1 px-2">Masking</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-[var(--border)]">
                                {tbl.columns.map((col) => (
                                  <tr key={col.id}>
                                    <td className="py-1 px-2 font-medium">
                                      {col.name}
                                    </td>
                                    <td className="py-1 px-2 text-[var(--text-muted)]">
                                      {col.data_type}
                                    </td>
                                    <td className="py-1 px-2 text-center">
                                      {col.readable ? "✓" : "✗"}
                                    </td>
                                    <td className="py-1 px-2 text-center">
                                      {col.filterable ? "✓" : "✗"}
                                    </td>
                                    <td className="py-1 px-2 text-center">
                                      {col.aggregatable ? "✓" : "✗"}
                                    </td>
                                    <td className="py-1 px-2 text-[var(--text-muted)]">
                                      {col.mask_type || "None"}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </details>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Revoke Confirmation Dialog */}
      {showRevokeDialog && currentTable && (
        <RevokeDialog
          tableName={`${currentTable.schema_name}.${currentTable.table_name}`}
          subjectName={currentSubjectName}
          onClose={() => setShowRevokeDialog(false)}
          onConfirm={handleRevokePermission}
        />
      )}
    </section>
  );
}
