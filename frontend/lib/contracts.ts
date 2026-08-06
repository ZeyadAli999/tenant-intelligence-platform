import { z } from "zod";

export * from "./chat-contracts";
export * from "./knowledge-contracts";
export * from "./database-contracts";

export const loginSchema = z.object({
  tenant_code: z.string().trim().min(1, "Tenant code is required").max(100),
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Password is required").max(1024),
});

export const tokenResponseSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(1),
  token_type: z.literal("bearer"),
  access_token_expires_in: z.number().int().positive(),
});

export const currentUserSchema = z.object({
  id: z.uuid(),
  email: z.email(),
  full_name: z.string().nullable(),
  status: z.string(),
  is_tenant_admin: z.boolean(),
  tenant: z.object({
    id: z.uuid(),
    name: z.string(),
    code: z.string(),
    status: z.string(),
  }),
  roles: z.array(
    z.object({
      id: z.uuid(),
      name: z.string(),
      description: z.string().nullable(),
    }),
  ),
  created_at: z.string(),
});

export type LoginInput = z.infer<typeof loginSchema>;
export type CurrentUser = z.infer<typeof currentUserSchema>;
