"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DatabaseConnectionCreateInput,
  DatabaseConnectionResponse,
  DatabaseConnectionUpdateInput,
} from "@/lib/database-contracts";

interface DatabaseModalProps {
  isOpen: boolean;
  connectionToEdit?: DatabaseConnectionResponse | null;
  onSubmit: (
    data: DatabaseConnectionCreateInput | DatabaseConnectionUpdateInput,
  ) => Promise<void>;
  onClose: () => void;
}

export function DatabaseModal({
  isOpen,
  connectionToEdit,
  onSubmit,
  onClose,
}: DatabaseModalProps) {
  const isEditing = Boolean(connectionToEdit);

  const [name, setName] = useState("");
  const [databaseType, setDatabaseType] = useState("postgresql");
  const [host, setHost] = useState("");
  const [port, setPort] = useState(5432);
  const [databaseName, setDatabaseName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [sslEnabled, setSslEnabled] = useState(false);
  const [applicationName, setApplicationName] = useState(
    "text-to-sql-schema-discovery",
  );

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [prevConn, setPrevConn] = useState<
    DatabaseConnectionResponse | null | undefined
  >(undefined);
  const [prevIsOpen, setPrevIsOpen] = useState(false);

  if (isOpen !== prevIsOpen || connectionToEdit !== prevConn) {
    setPrevIsOpen(isOpen);
    setPrevConn(connectionToEdit);
    if (isOpen) {
      if (connectionToEdit) {
        setName(connectionToEdit.name);
        setDatabaseType(connectionToEdit.database_type);
        setHost(connectionToEdit.host);
        setPort(connectionToEdit.port);
        setDatabaseName(connectionToEdit.database_name);
        setUsername(connectionToEdit.username);
        setPassword(""); // Password is never prefilled
        setSslEnabled(connectionToEdit.ssl_enabled);
      } else {
        setName("");
        setDatabaseType("postgresql");
        setHost("");
        setPort(5432);
        setDatabaseName("");
        setUsername("");
        setPassword("");
        setSslEnabled(false);
        setApplicationName("text-to-sql-schema-discovery");
      }
      setError(null);
    }
  }

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Connection name is required");
      return;
    }
    if (databaseType.trim().toLowerCase() !== "postgresql") {
      setError("Only PostgreSQL database connections are currently supported");
      return;
    }
    if (!host.trim()) {
      setError("Host is required");
      return;
    }
    if (!databaseName.trim()) {
      setError("Database name is required");
      return;
    }
    if (!username.trim()) {
      setError("Username is required");
      return;
    }
    if (!isEditing && !password.trim()) {
      setError("Password is required for new connections");
      return;
    }

    setIsSubmitting(true);
    try {
      if (isEditing) {
        const payload: DatabaseConnectionUpdateInput = {
          name: name.trim(),
          database_type: databaseType.trim(),
          host: host.trim(),
          port: Number(port),
          database_name: databaseName.trim(),
          username: username.trim(),
          ssl_enabled: sslEnabled,
          ssl_settings: { mode: "verify-full" },
          connection_options: { application_name: applicationName.trim() },
        };

        if (password.trim().length > 0) {
          payload.password = password;
        }

        await onSubmit(payload);
      } else {
        const payload: DatabaseConnectionCreateInput = {
          name: name.trim(),
          database_type: databaseType.trim(),
          host: host.trim(),
          port: Number(port),
          database_name: databaseName.trim(),
          username: username.trim(),
          password: password, // Will be sent via HTTPS body and cleared immediately
          ssl_enabled: sslEnabled,
          ssl_settings: { mode: "verify-full" },
          connection_options: { application_name: applicationName.trim() },
        };

        await onSubmit(payload);
      }
      setPassword(""); // Clear password from memory immediately
      onClose();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to save connection",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      tabIndex={-1}
      aria-hidden="false"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--surf)] p-6 shadow-2xl transition-all"
      >
        <div className="flex items-center justify-between pb-4">
          <h2
            id="modal-title"
            className="text-xl font-semibold text-[var(--fg)]"
          >
            {isEditing ? "Edit Connection" : "Add Database Connection"}
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

        {error && (
          <div className="mb-4">
            <Alert tone="danger">{error}</Alert>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label
              htmlFor="conn-name"
              className="block text-sm font-medium text-[var(--fg)]"
            >
              Connection Name
            </label>
            <Input
              id="conn-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Analytics Postgres DB"
              disabled={isSubmitting}
              className="mt-1"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="conn-type"
                className="block text-sm font-medium text-[var(--fg)]"
              >
                Database Type
              </label>
              <select
                id="conn-type"
                value={databaseType}
                onChange={(e) => setDatabaseType(e.target.value)}
                disabled={isSubmitting}
                className="mt-1 min-h-11 w-full rounded-md border border-[var(--border)] bg-[var(--surf)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              >
                <option value="postgresql">PostgreSQL (Supported)</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="conn-port"
                className="block text-sm font-medium text-[var(--fg)]"
              >
                Port
              </label>
              <Input
                id="conn-port"
                type="number"
                value={port}
                onChange={(e) => setPort(Number(e.target.value))}
                disabled={isSubmitting}
                className="mt-1"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="conn-host"
                className="block text-sm font-medium text-[var(--fg)]"
              >
                Host
              </label>
              <Input
                id="conn-host"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="e.g. db.internal.company.com"
                disabled={isSubmitting}
                className="mt-1"
              />
            </div>

            <div>
              <label
                htmlFor="conn-dbname"
                className="block text-sm font-medium text-[var(--fg)]"
              >
                Database Name
              </label>
              <Input
                id="conn-dbname"
                value={databaseName}
                onChange={(e) => setDatabaseName(e.target.value)}
                placeholder="e.g. customer_records"
                disabled={isSubmitting}
                className="mt-1"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="conn-username"
                className="block text-sm font-medium text-[var(--fg)]"
              >
                Username
              </label>
              <Input
                id="conn-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="db_reader"
                disabled={isSubmitting}
                className="mt-1"
              />
            </div>

            <div>
              <label
                htmlFor="conn-password"
                className="block text-sm font-medium text-[var(--fg)]"
              >
                Password{" "}
                {isEditing && (
                  <span className="text-xs text-[var(--fg-muted)]">
                    (Leave blank to keep existing)
                  </span>
                )}
              </label>
              <Input
                id="conn-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isEditing ? "••••••••••••" : "Enter password"}
                disabled={isSubmitting}
                className="mt-1"
                autoComplete="new-password"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <input
              id="conn-ssl"
              type="checkbox"
              checked={sslEnabled}
              onChange={(e) => setSslEnabled(e.target.checked)}
              disabled={isSubmitting}
              className="h-4 w-4 rounded border-[var(--border)] bg-[var(--surf)] text-[var(--accent)]"
            />
            <label
              htmlFor="conn-ssl"
              className="text-sm font-medium text-[var(--fg)]"
            >
              Require SSL Connection
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border)]">
            <Button
              type="button"
              className="!bg-[var(--surface-subtle)] !text-[var(--fg-default)] border border-[var(--border)] hover:!bg-[var(--border)]"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? "Saving..."
                : isEditing
                  ? "Update Connection"
                  : "Create Connection"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
