import { beforeEach, expect, test, vi } from "vitest";
import {
  ADMINISTRATOR_DENIED_MESSAGE,
  FINAL_ADMINISTRATOR_REQUIRED_MESSAGE,
  listTenantRoles,
} from "@/lib/admin-api";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

test("maps only the allowlisted administrator denial to the recorded warning", async () => {
  vi.mocked(fetch).mockResolvedValue(
    new Response(JSON.stringify({ code: "ADMINISTRATOR_REQUIRED" }), {
      status: 403,
    }),
  );
  await expect(listTenantRoles()).rejects.toThrow(ADMINISTRATOR_DENIED_MESSAGE);
});

test("maps only the allowlisted final-administrator conflict", async () => {
  vi.mocked(fetch).mockResolvedValue(
    new Response(
      JSON.stringify({ code: "FINAL_ACTIVE_ADMINISTRATOR_REQUIRED" }),
      { status: 409 },
    ),
  );
  await expect(listTenantRoles()).rejects.toThrow(
    FINAL_ADMINISTRATOR_REQUIRED_MESSAGE,
  );
});

test.each([403, 409])(
  "uses a generic safe error for an unrecognized %s response",
  async (status) => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "UNKNOWN_CODE",
          detail: "sensitive backend detail",
          error: "unsafe upstream text",
        }),
        { status },
      ),
    );
    await expect(listTenantRoles()).rejects.toThrow(
      "The administrative action could not be completed.",
    );
    await expect(listTenantRoles()).rejects.not.toThrow(
      /recorded|sensitive|unsafe/i,
    );
  },
);
