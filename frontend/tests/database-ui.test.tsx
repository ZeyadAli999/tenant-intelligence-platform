import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { DatabaseModal } from "@/components/databases/database-modal";
import { ConnectionListTable } from "@/components/databases/connection-list-table";
import { ConnectionTestModal } from "@/components/databases/connection-test-modal";
import { SchemaSyncModal } from "@/components/databases/schema-sync-modal";
import { DatabaseConnectionResponse } from "@/lib/database-contracts";

describe("Phase 5D Database UI Components", () => {
  test("DatabaseModal validates required fields and masks password", async () => {
    const onSubmit = vi.fn(async () => {});
    const onClose = vi.fn();

    render(
      <DatabaseModal isOpen={true} onSubmit={onSubmit} onClose={onClose} />,
    );

    const submitBtn = screen.getByRole("button", { name: "Create Connection" });
    fireEvent.click(submitBtn);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Connection name is required",
    );
    expect(onSubmit).not.toHaveBeenCalled();

    // Fill in required fields
    fireEvent.change(screen.getByLabelText("Connection Name"), {
      target: { value: "Test DB" },
    });
    fireEvent.change(screen.getByLabelText("Host"), {
      target: { value: "127.0.0.1" },
    });
    fireEvent.change(screen.getByLabelText("Database Name"), {
      target: { value: "testdb" },
    });
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "postgres" },
    });
    const passwordInput = screen.getByLabelText(/^Password/i);
    expect(passwordInput).toHaveAttribute("type", "password");

    fireEvent.change(passwordInput, { target: { value: "secret123" } });
    fireEvent.click(submitBtn);

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Test DB",
        database_type: "postgresql",
        host: "127.0.0.1",
        database_name: "testdb",
        username: "postgres",
        password: "secret123",
      }),
    );
  });

  test("ConnectionListTable displays safe metadata and role-scoped buttons", () => {
    const mockConn: DatabaseConnectionResponse = {
      id: "11111111-1111-4111-8111-111111111111",
      name: "Analytics PostgreSQL",
      database_type: "postgresql",
      host: "db.company.internal",
      port: 5432,
      database_name: "analytics_db",
      username: "analytics_reader",
      ssl_enabled: true,
      status: "healthy",
      last_tested_at: new Date().toISOString(),
      last_test_message: "Connection test succeeded",
      schema_sync_status: "synced",
      last_schema_sync_at: new Date().toISOString(),
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const { rerender } = render(
      <ConnectionListTable
        connections={[mockConn]}
        isTenantAdmin={false}
        onSelectConnection={vi.fn()}
        onEditConnection={vi.fn()}
        onDeleteConnection={vi.fn()}
        onTestConnection={vi.fn()}
        onSyncSchema={vi.fn()}
      />,
    );

    expect(screen.getByText("Analytics PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("healthy")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();

    // Rerender with tenant admin rights
    rerender(
      <ConnectionListTable
        connections={[mockConn]}
        isTenantAdmin={true}
        onSelectConnection={vi.fn()}
        onEditConnection={vi.fn()}
        onDeleteConnection={vi.fn()}
        onTestConnection={vi.fn()}
        onSyncSchema={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  test("ConnectionTestModal displays test status and messages", () => {
    render(
      <ConnectionTestModal
        isOpen={true}
        isLoading={false}
        testResult={{
          success: true,
          status: "healthy",
          error_code: null,
          message: "Successfully connected to PostgreSQL 16",
          tested_at: new Date().toISOString(),
        }}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Connection Test Results")).toBeInTheDocument();
    expect(
      screen.getByText("Successfully connected to PostgreSQL 16"),
    ).toBeInTheDocument();
  });

  test("SchemaSyncModal displays explanation warning before sync", () => {
    render(
      <SchemaSyncModal
        isOpen={true}
        connectionName="Analytics DB"
        onSync={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Sync Schema Catalog")).toBeInTheDocument();
    expect(
      screen.getByText(/This operation reads metadata only and will/i),
    ).toBeInTheDocument();
  });
});
