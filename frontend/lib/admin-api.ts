import {
  roleListSchema,
  tenantUserListSchema,
  tenantUserSchema,
  type TenantUserCreateInput,
} from "@/lib/admin-contracts";

export const ADMINISTRATOR_DENIED_MESSAGE =
  "Access denied. This action is restricted to Administrators. Your request was blocked and recorded.";
export const FINAL_ADMINISTRATOR_REQUIRED_MESSAGE =
  "At least one active Administrator must remain. Assign another active Administrator before removing this access.";
const ADMINISTRATIVE_ERROR_MESSAGE =
  "The administrative action could not be completed.";

export class AdministratorRequiredError extends Error {
  constructor() {
    super(ADMINISTRATOR_DENIED_MESSAGE);
    this.name = "AdministratorRequiredError";
  }
}

export class FinalAdministratorRequiredError extends Error {
  constructor() {
    super(FINAL_ADMINISTRATOR_REQUIRED_MESSAGE);
    this.name = "FinalAdministratorRequiredError";
  }
}

async function adminRequest(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, { cache: "no-store", ...init });
  const body = (await response.json().catch(() => null)) as {
    code?: unknown;
  } | null;
  if (response.status === 403 && body?.code === "ADMINISTRATOR_REQUIRED") {
    throw new AdministratorRequiredError();
  }
  if (
    response.status === 409 &&
    body?.code === "FINAL_ACTIVE_ADMINISTRATOR_REQUIRED"
  ) {
    throw new FinalAdministratorRequiredError();
  }
  if (!response.ok) {
    throw new Error(ADMINISTRATIVE_ERROR_MESSAGE);
  }
  return body;
}

export async function listTenantUsers(search = "", status = "") {
  const query = new URLSearchParams({ page: "1", page_size: "100" });
  if (search) query.set("search", search);
  if (status) query.set("status", status);
  return tenantUserListSchema.parse(
    await adminRequest(`/api/backend/users?${query.toString()}`),
  );
}

export async function listTenantRoles() {
  return roleListSchema.parse(
    await adminRequest("/api/backend/roles?page=1&page_size=100"),
  );
}

export async function createTenantUser(input: TenantUserCreateInput) {
  return tenantUserSchema.parse(
    await adminRequest("/api/backend/users", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateTenantUser(
  userId: string,
  input: {
    full_name: string | null;
    status: "active" | "inactive";
    role_ids: string[];
  },
) {
  return tenantUserSchema.parse(
    await adminRequest(`/api/backend/users/${userId}`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateTenantUserRoles(
  userId: string,
  roleIds: string[],
) {
  return tenantUserSchema.parse(
    await adminRequest(`/api/backend/users/${userId}/roles`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ role_ids: roleIds }),
    }),
  );
}
