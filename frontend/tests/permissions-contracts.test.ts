import { describe, expect, test } from "vitest";
import {
  columnPermissionReplaceSchema,
  rowFilterClauseSchema,
  rowFilterDSLSchema,
  tablePermissionCreateSchema,
} from "@/lib/permission-contracts";

describe("Permissions Zod Contracts", () => {
  const validUuid = "11111111-1111-4111-8111-111111111111";
  const validUuid2 = "22222222-2222-4222-8222-222222222222";

  test("accepts valid table permission create input with exactly one subject", () => {
    const userPayload = {
      user_id: validUuid,
      connection_id: validUuid,
      table_id: validUuid2,
      can_read: true,
    };
    expect(tablePermissionCreateSchema.parse(userPayload)).toEqual(userPayload);

    const rolePayload = {
      role_id: validUuid,
      connection_id: validUuid,
      table_id: validUuid2,
      can_read: false,
    };
    expect(tablePermissionCreateSchema.parse(rolePayload)).toEqual(rolePayload);
  });

  test("rejects table permission create input with missing or dual subjects", () => {
    expect(() =>
      tablePermissionCreateSchema.parse({
        connection_id: validUuid,
        table_id: validUuid2,
      }),
    ).toThrow("Exactly one permission subject");

    expect(() =>
      tablePermissionCreateSchema.parse({
        user_id: validUuid,
        role_id: validUuid,
        connection_id: validUuid,
        table_id: validUuid2,
      }),
    ).toThrow("Exactly one permission subject");
  });

  test("validates row filter DSL and operators", () => {
    const validDsl = {
      version: 1,
      all: [
        {
          column_id: validUuid,
          operator: "eq",
          value: { source: "context", value: "current_user_id" },
        },
        {
          column_id: validUuid2,
          operator: "is_null",
          value: null,
        },
      ],
    };
    expect(rowFilterDSLSchema.parse(validDsl)).toEqual(validDsl);
  });

  test("rejects malformed row filter operator", () => {
    expect(() =>
      rowFilterClauseSchema.parse({
        column_id: validUuid,
        operator: "invalid_operator",
      }),
    ).toThrow();
  });

  test("validates column permission replace payload", () => {
    const colPayload = {
      items: [
        {
          column_id: validUuid,
          can_read: true,
          can_filter: true,
          can_aggregate: false,
          mask_type: "hash",
        },
      ],
    };
    expect(columnPermissionReplaceSchema.parse(colPayload)).toEqual(colPayload);
  });
});
