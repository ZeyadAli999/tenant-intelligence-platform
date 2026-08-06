import { z } from "zod";

export const livenessResponseSchema = z.object({
  status: z.literal("ok"),
  service: z.string(),
  version: z.string(),
});

export const readinessResponseSchema = z.object({
  status: z.enum(["ready", "not_ready"]),
  checks: z.object({
    database: z.enum(["up", "down"]),
  }),
});

export type LivenessInfo = z.infer<typeof livenessResponseSchema>;
export type ReadinessInfo = z.infer<typeof readinessResponseSchema>;
