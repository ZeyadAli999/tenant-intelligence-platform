import { describe, expect, test } from "vitest";
import {
  livenessResponseSchema,
  readinessResponseSchema,
} from "@/lib/settings-contracts";

describe("Settings Contracts", () => {
  test("accepts valid liveness response", () => {
    const valid = {
      status: "ok",
      service: "Tenant Intelligence",
      version: "0.1.0",
    };
    expect(livenessResponseSchema.parse(valid)).toEqual(valid);
  });

  test("rejects malformed liveness response", () => {
    const invalid = {
      status: "bad",
      service: "Tenant Intelligence",
    };
    expect(() => livenessResponseSchema.parse(invalid)).toThrow();
  });

  test("accepts valid readiness response", () => {
    const valid = {
      status: "ready",
      checks: {
        database: "up",
      },
    };
    expect(readinessResponseSchema.parse(valid)).toEqual(valid);
  });

  test("rejects malformed readiness response", () => {
    const invalid = {
      status: "ready",
      checks: {
        database: "invalid_status",
      },
    };
    expect(() => readinessResponseSchema.parse(invalid)).toThrow();
  });
});
