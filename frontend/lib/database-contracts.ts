import { z } from "zod";

export const uuidSchema = z.string().uuid("Invalid UUID format");

export const databaseConnectionCreateSchema = z.object({
  name: z.string().min(1, "Connection name is required").max(200),
  database_type: z.string().min(1, "Database type is required").max(50),
  host: z.string().min(1, "Host is required").max(255),
  port: z.number().int().min(1).max(65535),
  database_name: z.string().min(1, "Database name is required").max(255),
  username: z.string().min(1, "Username is required").max(255),
  password: z.string().min(1, "Password is required").max(1024),
  ssl_enabled: z.boolean().default(false),
  ssl_settings: z
    .object({
      mode: z
        .enum(["require", "verify-ca", "verify-full"])
        .default("verify-full"),
    })
    .default({ mode: "verify-full" }),
  connection_options: z
    .object({
      application_name: z
        .string()
        .min(1)
        .max(64)
        .regex(/^[A-Za-z0-9_. -]+$/, "Invalid application name format")
        .default("text-to-sql-schema-discovery"),
    })
    .default({ application_name: "text-to-sql-schema-discovery" }),
});

export type DatabaseConnectionCreateInput = z.infer<
  typeof databaseConnectionCreateSchema
>;

export const databaseConnectionUpdateSchema = z.object({
  name: z.string().min(1).max(200).optional(),
  database_type: z.string().min(1).max(50).optional(),
  host: z.string().min(1).max(255).optional(),
  port: z.number().int().min(1).max(65535).optional(),
  database_name: z.string().min(1).max(255).optional(),
  username: z.string().min(1).max(255).optional(),
  password: z.string().min(1).max(1024).optional(),
  ssl_enabled: z.boolean().optional(),
  ssl_settings: z
    .object({
      mode: z.enum(["require", "verify-ca", "verify-full"]),
    })
    .optional(),
  connection_options: z
    .object({
      application_name: z.string().min(1).max(64),
    })
    .optional(),
});

export type DatabaseConnectionUpdateInput = z.infer<
  typeof databaseConnectionUpdateSchema
>;

export const databaseConnectionResponseSchema = z.object({
  id: uuidSchema,
  name: z.string(),
  database_type: z.string(),
  host: z.string(),
  port: z.number(),
  database_name: z.string(),
  username: z.string(),
  ssl_enabled: z.boolean(),
  status: z.string(),
  last_tested_at: z.string().nullable(),
  last_test_message: z.string().nullable(),
  schema_sync_status: z.string(),
  last_schema_sync_at: z.string().nullable(),
  is_active: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type DatabaseConnectionResponse = z.infer<
  typeof databaseConnectionResponseSchema
>;

export const databaseConnectionListResponseSchema = z.object({
  items: z.array(databaseConnectionResponseSchema),
  total: z.number().int().min(0),
  page: z.number().int().min(1),
  page_size: z.number().int().min(1),
});

export type DatabaseConnectionListResponse = z.infer<
  typeof databaseConnectionListResponseSchema
>;

export const connectionTestResponseSchema = z.object({
  success: z.boolean(),
  status: z.string(),
  error_code: z.string().nullable(),
  message: z.string(),
  tested_at: z.string(),
});

export type ConnectionTestResponse = z.infer<
  typeof connectionTestResponseSchema
>;

export const schemaSyncResponseSchema = z.object({
  success: z.boolean(),
  status: z.string(),
  message: z.string(),
  schema_count: z.number().int(),
  table_count: z.number().int(),
  column_count: z.number().int(),
  synced_at: z.string().nullable(),
});

export type SchemaSyncResponse = z.infer<typeof schemaSyncResponseSchema>;

export const databaseSchemaResponseSchema = z.object({
  id: uuidSchema,
  schema_name: z.string(),
  description: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type DatabaseSchemaResponse = z.infer<
  typeof databaseSchemaResponseSchema
>;

export const databaseSchemaListResponseSchema = z.object({
  items: z.array(databaseSchemaResponseSchema),
  total: z.number().int().min(0),
  page: z.number().int().min(1),
  page_size: z.number().int().min(1),
});

export type DatabaseSchemaListResponse = z.infer<
  typeof databaseSchemaListResponseSchema
>;

export const databaseColumnResponseSchema = z.object({
  id: uuidSchema,
  column_name: z.string(),
  data_type: z.string(),
  ordinal_position: z.number().int().nullable(),
  is_nullable: z.boolean().nullable(),
  is_primary_key: z.boolean(),
  is_foreign_key: z.boolean(),
  referenced_schema: z.string().nullable(),
  referenced_table: z.string().nullable(),
  referenced_column: z.string().nullable(),
  description: z.string().nullable(),
});

export type DatabaseColumnResponse = z.infer<
  typeof databaseColumnResponseSchema
>;

export const databaseTableResponseSchema = z.object({
  id: uuidSchema,
  schema_name: z.string(),
  table_name: z.string(),
  table_type: z.string(),
  description: z.string().nullable(),
  estimated_row_count: z.number().int().nullable(),
  primary_key_columns: z.array(z.string()),
  is_enabled: z.boolean(),
  is_sensitive: z.boolean(),
  columns: z.array(databaseColumnResponseSchema),
  created_at: z.string(),
  updated_at: z.string(),
});

export type DatabaseTableResponse = z.infer<typeof databaseTableResponseSchema>;

export const databaseTableListResponseSchema = z.object({
  items: z.array(databaseTableResponseSchema),
  total: z.number().int().min(0),
  page: z.number().int().min(1),
  page_size: z.number().int().min(1),
});

export type DatabaseTableListResponse = z.infer<
  typeof databaseTableListResponseSchema
>;

export const allowedColumnResponseSchema = z.object({
  id: uuidSchema,
  name: z.string(),
  data_type: z.string(),
  readable: z.boolean(),
  filterable: z.boolean(),
  aggregatable: z.boolean(),
  mask_type: z.enum(["redact", "partial", "hash", "null"]).nullable(),
  is_primary_key: z.boolean(),
  is_foreign_key: z.boolean(),
  referenced_schema: z.string().nullable(),
  referenced_table: z.string().nullable(),
  referenced_column: z.string().nullable(),
});

export type AllowedColumnResponse = z.infer<typeof allowedColumnResponseSchema>;

export const allowedTableResponseSchema = z.object({
  id: uuidSchema,
  schema_name: z.string(),
  table_name: z.string(),
  table_type: z.string(),
  columns: z.array(allowedColumnResponseSchema),
});

export type AllowedTableResponse = z.infer<typeof allowedTableResponseSchema>;

export const allowedSchemaResponseSchema = z.object({
  connection_id: uuidSchema,
  tables: z.array(allowedTableResponseSchema),
});

export type AllowedSchemaResponse = z.infer<typeof allowedSchemaResponseSchema>;
