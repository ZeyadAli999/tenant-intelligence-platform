import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, expect, test, vi, beforeEach } from "vitest";
import { PermissionsWorkspace } from "@/components/permissions/permissions-workspace";
import { ToastProvider } from "@/components/ui/toast";
import * as adminApi from "@/lib/admin-api";
import * as dbApi from "@/lib/database-api";
import * as permApi from "@/lib/permission-api";

vi.mock("@/lib/admin-api");
vi.mock("@/lib/database-api");
vi.mock("@/lib/permission-api");

describe("PermissionsWorkspace UI Component", () => {
  const mockConnId = "11111111-1111-4111-8111-111111111111";
  const mockUserId = "22222222-2222-4222-8222-222222222222";
  const mockRoleId = "33333333-3333-4333-8333-333333333333";
  const mockTableId = "44444444-4444-4444-8444-444444444444";
  const mockColTaxId = "55555555-5555-4555-8555-555555555555";
  const mockColNameId = "55555555-5555-4555-8555-555555555556";
  const mockPermId = "66666666-6666-4666-8666-666666666666";

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(dbApi.listDatabaseConnections).mockResolvedValue({
      items: [
        {
          id: mockConnId,
          name: "Analytics Production DB",
          database_type: "postgresql",
          host: "db.local",
          port: 5432,
          database_name: "analytics_db",
          username: "reader",
          ssl_enabled: true,
          status: "connected",
          last_tested_at: "2026-08-01T00:00:00Z",
          last_test_message: null,
          schema_sync_status: "synced",
          last_schema_sync_at: "2026-08-01T00:00:00Z",
          is_active: true,
          created_at: "2026-08-01T00:00:00Z",
          updated_at: "2026-08-01T00:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });

    vi.mocked(adminApi.listTenantUsers).mockResolvedValue({
      items: [
        {
          id: mockUserId,
          email: "alice@tenant.org",
          full_name: "Alice Analyst",
          status: "active",
          is_tenant_admin: false,
          roles: [],
          created_at: "2026-08-01T00:00:00Z",
          updated_at: "2026-08-01T00:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });

    vi.mocked(adminApi.listTenantRoles).mockResolvedValue({
      items: [
        {
          id: mockRoleId,
          name: "Data Analyst",
          description: "Analyst role",
          created_at: "2026-08-01T00:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });

    vi.mocked(dbApi.listDatabaseTables).mockResolvedValue({
      items: [
        {
          id: mockTableId,
          schema_name: "business",
          table_name: "customers",
          table_type: "table",
          description: null,
          estimated_row_count: 100,
          primary_key_columns: ["id"],
          is_enabled: true,
          is_sensitive: false,
          columns: [
            {
              id: mockColTaxId,
              column_name: "tax_identifier",
              data_type: "varchar",
              ordinal_position: 1,
              is_nullable: true,
              is_primary_key: false,
              is_foreign_key: false,
              referenced_schema: null,
              referenced_table: null,
              referenced_column: null,
              description: null,
            },
            {
              id: mockColNameId,
              column_name: "customer_name",
              data_type: "varchar",
              ordinal_position: 2,
              is_nullable: false,
              is_primary_key: false,
              is_foreign_key: false,
              referenced_schema: null,
              referenced_table: null,
              referenced_column: null,
              description: null,
            },
          ],
          created_at: "2026-08-01T00:00:00Z",
          updated_at: "2026-08-01T00:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });

    vi.mocked(permApi.listTablePermissions).mockResolvedValue({
      items: [
        {
          id: mockPermId,
          role_id: null,
          user_id: mockUserId,
          connection_id: mockConnId,
          table_id: mockTableId,
          can_read: true,
          can_insert: false,
          can_update: false,
          can_delete: false,
          row_filter: {},
          created_at: "2026-08-01T00:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });

    vi.mocked(permApi.getColumnPermissions).mockResolvedValue({
      items: [
        {
          id: "77777777-7777-4777-8777-777777777777",
          column_id: mockColTaxId,
          can_read: true,
          can_filter: true,
          can_aggregate: true,
          mask_type: null,
        },
        {
          id: "77777777-7777-4777-8777-777777777778",
          column_id: mockColNameId,
          can_read: true,
          can_filter: true,
          can_aggregate: true,
          mask_type: null,
        },
      ],
    });

    vi.mocked(dbApi.getAllowedSchema).mockResolvedValue({
      connection_id: mockConnId,
      tables: [
        {
          id: mockTableId,
          schema_name: "business",
          table_name: "customers",
          table_type: "table",
          columns: [
            {
              id: mockColTaxId,
              name: "tax_identifier",
              data_type: "varchar",
              readable: true,
              filterable: true,
              aggregatable: true,
              mask_type: null,
              is_primary_key: false,
              is_foreign_key: false,
              referenced_schema: null,
              referenced_table: null,
              referenced_column: null,
            },
          ],
        },
      ],
    });
  });

  test("renders permissions workspace header and subject selection", async () => {
    render(
      <ToastProvider>
        <PermissionsWorkspace />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Permissions" })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /customers/ })).toBeInTheDocument();
    });

    expect(screen.getByRole("option", { name: /Analytics Production DB/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Alice Analyst/ })).toBeInTheDocument();
  });

  test("supports subject switching between user and role", async () => {
    render(
      <ToastProvider>
        <PermissionsWorkspace />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Permissions" })).toBeInTheDocument();
    });

    const roleTab = screen.getByRole("button", { name: "Role" });
    fireEvent.click(roleTab);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Data Analyst" })).toBeInTheDocument();
    });
  });

  test("displays non-administrator denial state when blocked by backend", async () => {
    vi.mocked(adminApi.listTenantUsers).mockRejectedValue(
      new adminApi.AdministratorRequiredError(),
    );

    render(
      <ToastProvider>
        <PermissionsWorkspace />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Access denied. This action is restricted to Administrators/),
      ).toBeInTheDocument();
    });
  });

  test("column permission checkboxes and masking policy update state immediately and save payload correctly", async () => {
    vi.mocked(permApi.replaceColumnPermissions).mockResolvedValue({
      items: [
        {
          id: "77777777-7777-4777-8777-777777777777",
          column_id: mockColTaxId,
          can_read: true,
          can_filter: false,
          can_aggregate: false,
          mask_type: "redact",
        },
        {
          id: "77777777-7777-4777-8777-777777777778",
          column_id: mockColNameId,
          can_read: true,
          can_filter: true,
          can_aggregate: true,
          mask_type: null,
        },
      ],
    });

    render(
      <ToastProvider>
        <PermissionsWorkspace />
      </ToastProvider>,
    );

    const tableBtn = await screen.findByRole("button", { name: /customers/ });
    fireEvent.click(tableBtn);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Save Column Rules" }),
      ).toBeInTheDocument();
    });

    const filterCheckbox = screen.getByRole("checkbox", {
      name: "Filter capability for tax_identifier",
    });
    const aggregateCheckbox = screen.getByRole("checkbox", {
      name: "Aggregate capability for tax_identifier",
    });
    const maskingSelect = screen.getByRole("combobox", {
      name: "Masking policy for tax_identifier",
    });

    // Initial state check
    expect(filterCheckbox).toBeChecked();
    expect(aggregateCheckbox).toBeChecked();
    expect(maskingSelect).toHaveValue("");

    // Interact with tax_identifier controls
    fireEvent.click(filterCheckbox);
    fireEvent.click(aggregateCheckbox);
    fireEvent.change(maskingSelect, { target: { value: "redact" } });

    // Immediate visual update check before saving
    expect(filterCheckbox).not.toBeChecked();
    expect(aggregateCheckbox).not.toBeChecked();
    expect(maskingSelect).toHaveValue("redact");

    // Other column customer_name remains unchanged
    const nameFilterCheckbox = screen.getByRole("checkbox", {
      name: "Filter capability for customer_name",
    });
    expect(nameFilterCheckbox).toBeChecked();

    // Click Save Column Rules
    const saveButton = screen.getByRole("button", { name: "Save Column Rules" });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(permApi.replaceColumnPermissions).toHaveBeenCalledWith(
        mockPermId,
        expect.arrayContaining([
          expect.objectContaining({
            column_id: mockColTaxId,
            can_read: true,
            can_filter: false,
            can_aggregate: false,
            mask_type: "redact",
          }),
          expect.objectContaining({
            column_id: mockColNameId,
            can_read: true,
            can_filter: true,
            can_aggregate: true,
            mask_type: null,
          }),
        ]),
      );
    });

    // Verify no tenant ID in outgoing payload call
    const calledPayload = vi.mocked(permApi.replaceColumnPermissions).mock.calls[0][1];
    expect(JSON.stringify(calledPayload)).not.toContain("tenant_id");
  });

  test("shows success message, handles saving button state, prevents duplicate requests, announces via aria-live, and clears on table switch", async () => {
    let resolveSave!: (value: unknown) => void;
    const savePromise = new Promise((resolve) => {
      resolveSave = resolve;
    });

    vi.mocked(permApi.replaceColumnPermissions).mockImplementation(() => savePromise as never);

    render(
      <ToastProvider>
        <PermissionsWorkspace />
      </ToastProvider>,
    );

    const tableBtn = await screen.findByRole("button", { name: /customers/ });
    fireEvent.click(tableBtn);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Save Column Rules" }),
      ).toBeInTheDocument();
    });

    const saveButton = screen.getByRole("button", { name: "Save Column Rules" });

    // 1. Verify success is NOT shown before Promise resolves
    expect(screen.queryByText("Column rules saved successfully.")).not.toBeInTheDocument();

    // Trigger save
    fireEvent.click(saveButton);

    // 2. Button is disabled and says "Saving..." during request
    expect(saveButton).toBeDisabled();
    expect(saveButton).toHaveTextContent("Saving...");

    // 3. Double-click does not send duplicate requests
    fireEvent.click(saveButton);
    expect(permApi.replaceColumnPermissions).toHaveBeenCalledTimes(1);

    // Resolve backend request
    await act(async () => {
      resolveSave({
        items: [
          {
            id: "77777777-7777-4777-8777-777777777777",
            column_id: mockColTaxId,
            can_read: true,
            can_filter: true,
            can_aggregate: true,
            mask_type: null,
          },
        ],
      });
      await new Promise((r) => setTimeout(r, 50));
    });

    // 4. Successful save shows success message and announces via aria-live
    const successMsg = await screen.findByText("Column rules saved successfully.");
    expect(successMsg).toBeInTheDocument();
    const statusCard = successMsg.closest('[role="status"]');
    expect(statusCard).toBeInTheDocument();
    expect(statusCard).toHaveAttribute("aria-live", "polite");

    // 5. Dismiss notification removes toast
    const dismissBtn = screen.getByRole("button", { name: "Dismiss notification" });
    fireEvent.click(dismissBtn);
    expect(screen.queryByText("Column rules saved successfully.")).not.toBeInTheDocument();
  });

  test("preserves local edits and displays safe error when backend save fails", async () => {
    vi.mocked(permApi.replaceColumnPermissions).mockRejectedValue(
      new Error("Database connection error"),
    );

    render(
      <ToastProvider>
        <PermissionsWorkspace />
      </ToastProvider>,
    );

    const tableBtn = await screen.findByRole("button", { name: /customers/ });
    fireEvent.click(tableBtn);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Save Column Rules" }),
      ).toBeInTheDocument();
    });

    const filterCheckbox = screen.getByRole("checkbox", {
      name: "Filter capability for tax_identifier",
    });
    fireEvent.click(filterCheckbox);
    expect(filterCheckbox).not.toBeChecked();

    const saveButton = screen.getByRole("button", { name: "Save Column Rules" });
    await act(async () => {
      fireEvent.click(saveButton);
    });

    await waitFor(() => {
      expect(screen.getAllByText("Database connection error").length).toBeGreaterThan(0);
    });

    // Verify user edits remain visible after error and button is re-enabled
    expect(filterCheckbox).not.toBeChecked();
    expect(saveButton).not.toBeDisabled();
  });

  test("row filter controls render with independent accessible controls and non-collapsing grid layout", async () => {
    render(
      <ToastProvider>
        <PermissionsWorkspace />
      </ToastProvider>,
    );

    const tableBtn = await screen.findByRole("button", { name: /customers/ });
    fireEvent.click(tableBtn);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Add Rule" })).toBeInTheDocument();
    });

    const addRuleBtn = screen.getByRole("button", { name: "Add Rule" });

    // Header action area contains Add Rule and Save Row Filter
    const headerActionArea = addRuleBtn.parentElement!;
    expect(headerActionArea).toHaveTextContent("Add Rule");
    expect(headerActionArea).toHaveTextContent("Save Row Filter");

    // Add two rules
    fireEvent.click(addRuleBtn);
    fireEvent.click(addRuleBtn);

    await waitFor(() => {
      expect(screen.getByText("Rule #1")).toBeInTheDocument();
      expect(screen.getByText("Rule #2")).toBeInTheDocument();
    });

    // 1. Value Source renders as an independent accessible control
    const valSourceRule1 = screen.getByRole("combobox", { name: "Value source for rule 1" });
    expect(valSourceRule1).toBeInTheDocument();
    expect(valSourceRule1.className).toContain("min-w-[100px]");

    // Default value source is context -> renders context select
    const contextValRule1 = screen.getByRole("combobox", { name: "Context value for rule 1" });
    expect(contextValRule1).toBeInTheDocument();
    expect(contextValRule1.className).toContain("min-w-[140px]");

    // Switch value source to literal -> renders literal textbox
    fireEvent.change(valSourceRule1, { target: { value: "literal" } });
    const literalValInput1 = screen.getByRole("textbox", { name: "Literal value for rule 1" });
    expect(literalValInput1).toBeInTheDocument();
    expect(literalValInput1.className).toContain("min-w-[140px]");

    // 3. Remove Rule button renders as separate button in rule row with fixed 40px sizing
    const removeRule1 = screen.getByRole("button", { name: "Remove rule 1" });
    const removeRule2 = screen.getByRole("button", { name: "Remove rule 2" });

    expect(removeRule1).toBeInTheDocument();
    expect(removeRule1).toHaveAttribute("title", "Remove rule");
    expect(removeRule1.className).toContain("min-h-[40px]");
    expect(removeRule1.className).toContain("min-w-[40px]");

    // 4. Header action container does NOT contain Remove Rule button
    expect(headerActionArea).not.toContainElement(removeRule1);
    expect(headerActionArea).not.toContainElement(removeRule2);

    // 5. Click Remove Rule 1 removes only rule 1, rule 2 remains intact
    fireEvent.click(removeRule1);

    await waitFor(() => {
      expect(screen.getByText("Rule #1")).toBeInTheDocument();
      expect(screen.queryByText("Rule #2")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Remove rule 1" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Remove rule 2" })).not.toBeInTheDocument();
    });
  });
});
