import { z } from "zod";

export const uuidSchema = z.string().uuid("Invalid UUID format");

export const rowOperatorSchema = z.enum([
  "eq",
  "neq",
  "in",
  "not_in",
  "gt",
  "gte",
  "lt",
  "lte",
  "is_null",
  "is_not_null",
]);

export type RowOperator = z.infer<typeof rowOperatorSchema>;

export const maskTypeSchema = z.enum(["redact", "partial", "hash", "null"]);
export type MaskType = z.infer<typeof maskTypeSchema>;

export const rowFilterValueSchema = z.object({
  source: z.enum(["literal", "context"]),
  value: z.unknown(),
});

export type RowFilterValue = z.infer<typeof rowFilterValueSchema>;

export const rowFilterClauseSchema = z.object({
  column_id: uuidSchema,
  operator: rowOperatorSchema,
  value: rowFilterValueSchema.optional().nullable(),
});

export type RowFilterClause = z.infer<typeof rowFilterClauseSchema>;

export const rowFilterDSLSchema = z.object({
  version: z.literal(1),
  all: z.array(rowFilterClauseSchema).min(1).max(20),
});

export type RowFilterDSL = z.infer<typeof rowFilterDSLSchema>;

export const tablePermissionCreateSchema = z
  .object({
    role_id: uuidSchema.optional().nullable(),
    user_id: uuidSchema.optional().nullable(),
    connection_id: uuidSchema,
    table_id: uuidSchema,
    can_read: z.boolean().default(true),
    row_filter: rowFilterDSLSchema.optional().nullable(),
  })
  .refine(
    (data) => (data.role_id == null) !== (data.user_id == null),
    { message: "Exactly one permission subject (user_id or role_id) is required" },
  );

export type TablePermissionCreateInput = z.infer<
  typeof tablePermissionCreateSchema
>;

export const tablePermissionUpdateSchema = z.object({
  can_read: z.boolean().optional(),
  row_filter: rowFilterDSLSchema.optional().nullable(),
});

export type TablePermissionUpdateInput = z.infer<
  typeof tablePermissionUpdateSchema
>;

export const tablePermissionResponseSchema = z.object({
  id: uuidSchema,
  role_id: uuidSchema.nullable(),
  user_id: uuidSchema.nullable(),
  connection_id: uuidSchema,
  table_id: uuidSchema,
  can_read: z.boolean(),
  can_insert: z.boolean(),
  can_update: z.boolean(),
  can_delete: z.boolean(),
  row_filter: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

export type TablePermissionResponse = z.infer<
  typeof tablePermissionResponseSchema
>;

export const tablePermissionListResponseSchema = z.object({
  items: z.array(tablePermissionResponseSchema),
  total: z.number().int().min(0),
  page: z.number().int().min(1),
  page_size: z.number().int().min(1),
});

export type TablePermissionListResponse = z.infer<
  typeof tablePermissionListResponseSchema
>;

export const columnPermissionItemSchema = z.object({
  column_id: uuidSchema,
  can_read: z.boolean().default(true),
  can_filter: z.boolean().default(true),
  can_aggregate: z.boolean().default(true),
  mask_type: maskTypeSchema.optional().nullable(),
});

export type ColumnPermissionItem = z.infer<
  typeof columnPermissionItemSchema
>;

export const columnPermissionReplaceSchema = z.object({
  items: z.array(columnPermissionItemSchema).max(200),
});

export type ColumnPermissionReplaceInput = z.infer<
  typeof columnPermissionReplaceSchema
>;

export const columnPermissionResponseSchema = z.object({
  id: uuidSchema,
  column_id: uuidSchema,
  can_read: z.boolean(),
  can_filter: z.boolean(),
  can_aggregate: z.boolean(),
  mask_type: maskTypeSchema.nullable(),
});

export type ColumnPermissionResponse = z.infer<
  typeof columnPermissionResponseSchema
>;

export const columnPermissionListResponseSchema = z.object({
  items: z.array(columnPermissionResponseSchema),
});

export type ColumnPermissionListResponse = z.infer<
  typeof columnPermissionListResponseSchema
>;
