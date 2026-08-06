import { z } from "zod";

export const roleSummarySchema = z.object({
  id: z.uuid(),
  name: z.string(),
  description: z.string().nullable(),
});

export const tenantUserSchema = z.object({
  id: z.uuid(),
  email: z.email(),
  full_name: z.string().nullable(),
  status: z.enum(["active", "inactive"]),
  is_tenant_admin: z.boolean(),
  roles: z.array(roleSummarySchema),
  created_at: z.string(),
  updated_at: z.string(),
});

export const tenantUserListSchema = z.object({
  items: z.array(tenantUserSchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
});

export const roleListSchema = z.object({
  items: z.array(
    roleSummarySchema.extend({
      created_at: z.string(),
    }),
  ),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
});

export const tenantUserCreateSchema = z.object({
  full_name: z.string().trim().min(1, "Full name is required").max(255),
  email: z.email("Enter a valid email address"),
  password: z.string().min(12, "Password must be at least 12 characters").max(256),
  status: z.enum(["active", "inactive"]),
  role_ids: z.array(z.uuid()).max(100),
});

export type TenantUser = z.infer<typeof tenantUserSchema>;
export type TenantRole = z.infer<typeof roleListSchema>["items"][number];
export type TenantUserCreateInput = z.infer<typeof tenantUserCreateSchema>;
