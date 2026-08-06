import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { DatabaseModal } from "@/components/databases/database-modal";
import { ConnectionListTable } from "@/components/databases/connection-list-table";
import { ConnectionTestModal } from "@/components/databases/connection-test-modal";
import { SchemaSyncModal } from "@/components/databases/schema-sync-modal";
import {
  DatabaseConnectionCreateInput,
  DatabaseConnectionResponse,
  DatabaseConnectionUpdateInput,
} from "@/lib/database-contracts";

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
      status: "connected",
      last_tested_at: new Date().toISOString(),
      last_test_message: "Connection test succeeded",
      schema_sync_status: "succeeded",
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
    expect(screen.getByText("connected")).toBeInTheDocument();
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
          status: "connected",
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

  test("DatabaseModal in edit mode omits blank password and includes nonblank password", async () => {
    let capturedPayload: Record<string, unknown> | null = null;
    const onSubmit = vi.fn(async (data: Record<string, unknown>) => {
      capturedPayload = data;
    });
    const onClose = vi.fn();

    const mockConn: DatabaseConnectionResponse = {
      id: "11111111-1111-4111-8111-111111111111",
      name: "Existing DB",
      database_type: "postgresql",
      host: "db.example.com",
      port: 5432,
      database_name: "testdb",
      username: "dbuser",
      ssl_enabled: true,
      status: "connected",
      last_tested_at: null,
      last_test_message: null,
      schema_sync_status: "succeeded",
      last_schema_sync_at: null,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(
      <DatabaseModal
        isOpen={true}
        connectionToEdit={mockConn}
        onSubmit={
          onSubmit as unknown as (
            data: DatabaseConnectionCreateInput | DatabaseConnectionUpdateInput,
          ) => Promise<void>
        }
        onClose={onClose}
      />,
    );

    const passwordInput = screen.getByLabelText(
      /^Password/i,
    ) as HTMLInputElement;
    expect(passwordInput.value).toBe("");

    const submitBtn = screen.getByRole("button", { name: "Update Connection" });
    fireEvent.click(submitBtn);

    await vi.waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    expect(capturedPayload).toEqual(
      expect.objectContaining({
        name: "Existing DB",
        database_type: "postgresql",
        host: "db.example.com",
        port: 5432,
        database_name: "testdb",
        username: "dbuser",
      }),
    );
    expect(capturedPayload).not.toHaveProperty("password");

    onSubmit.mockClear();
    capturedPayload = null;

    fireEvent.change(passwordInput, { target: { value: "newsecret123" } });
    fireEvent.click(submitBtn);

    await vi.waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    expect(capturedPayload).toEqual(
      expect.objectContaining({
        name: "Existing DB",
        password: "newsecret123",
      }),
    );
  });
});
