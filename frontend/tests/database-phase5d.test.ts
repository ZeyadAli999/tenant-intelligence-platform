import { describe, expect, test } from "vitest";
import { resolveContract } from "@/app/api/backend/[...path]/route";
import {
  databaseConnectionCreateSchema,
  databaseConnectionResponseSchema,
} from "@/lib/database-contracts";

describe("Phase 5D Database BFF Contracts & Validation", () => {
  test("resolveContract allows database-connections endpoints with correct methods", () => {
    expect(resolveContract("GET", ["database-connections"])).toEqual({
      path: "database-connections",
      query: new Set(["page", "page_size"]),
    });

    expect(resolveContract("POST", ["database-connections"])).toEqual({
      path: "database-connections",
      query: new Set(),
    });

    const connId = "11111111-1111-4111-8111-111111111111";

    expect(resolveContract("GET", ["database-connections", connId])).toEqual({
      path: `database-connections/${connId}`,
      query: new Set(),
    });

    expect(resolveContract("PUT", ["database-connections", connId])).toEqual({
      path: `database-connections/${connId}`,
      query: new Set(),
    });

    expect(resolveContract("DELETE", ["database-connections", connId])).toEqual(
      {
        path: `database-connections/${connId}`,
        query: new Set(),
      },
    );

    expect(
      resolveContract("POST", ["database-connections", connId, "test"]),
    ).toEqual({
      path: `database-connections/${connId}/test`,
      query: new Set(),
    });

    expect(
      resolveContract("POST", ["database-connections", connId, "sync-schema"]),
    ).toEqual({
      path: `database-connections/${connId}/sync-schema`,
      query: new Set(),
    });

    expect(
      resolveContract("GET", ["database-connections", connId, "schemas"]),
    ).toEqual({
      path: `database-connections/${connId}/schemas`,
      query: new Set(["page", "page_size"]),
    });

    expect(
      resolveContract("GET", ["database-connections", connId, "tables"]),
    ).toEqual({
      path: `database-connections/${connId}/tables`,
      query: new Set([
        "page",
        "page_size",
        "schema_name",
        "enabled",
        "table_type",
        "search",
      ]),
    });

    expect(
      resolveContract("GET", [
        "database-connections",
        connId,
        "allowed-schema",
      ]),
    ).toEqual({
      path: `database-connections/${connId}/allowed-schema`,
      query: new Set(),
    });
  });

  test("rejects malformed UUIDs and unsupported methods", () => {
    expect(
      resolveContract("GET", ["database-connections", "invalid-uuid"]),
    ).toBeNull();

    expect(
      resolveContract("PATCH", [
        "database-connections",
        "11111111-1111-4111-8111-111111111111",
      ]),
    ).toBeNull();
  });

  test("databaseConnectionCreateSchema validates required fields", () => {
    const invalid = databaseConnectionCreateSchema.safeParse({
      name: "",
      database_type: "postgresql",
      host: "localhost",
      port: 5432,
      database_name: "test",
      username: "user",
      password: "password123",
    });
    expect(invalid.success).toBe(false);

    const valid = databaseConnectionCreateSchema.safeParse({
      name: "Production DB",
      database_type: "postgresql",
      host: "db.example.com",
      port: 5432,
      database_name: "prod_db",
      username: "db_user",
      password: "secretpassword123",
    });
    expect(valid.success).toBe(true);
  });

  test("databaseConnectionResponseSchema parses valid backend contract", () => {
    const raw = {
      id: "11111111-1111-4111-8111-111111111111",
      name: "Analytics DB",
      database_type: "postgresql",
      host: "db.internal",
      port: 5432,
      database_name: "analytics",
      username: "reader",
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

    const parsed = databaseConnectionResponseSchema.safeParse(raw);
    expect(parsed.success).toBe(true);
  });
});
