import { AdministratorRequiredError } from "@/lib/admin-api";
import {
  columnPermissionListResponseSchema,
  columnPermissionReplaceSchema,
  tablePermissionListResponseSchema,
  tablePermissionResponseSchema,
  type ColumnPermissionItem,
  type TablePermissionCreateInput,
  type TablePermissionResponse,
  type TablePermissionUpdateInput,
} from "@/lib/permission-contracts";

async function permissionRequest(
  path: string,
  init?: RequestInit,
): Promise<unknown> {
  const response = await fetch(path, { cache: "no-store", ...init });
  const body = (await response.json().catch(() => null)) as {
    code?: unknown;
    error?: unknown;
  } | null;

  if (response.status === 403 && body?.code === "ADMINISTRATOR_REQUIRED") {
    throw new AdministratorRequiredError();
  }
  if (!response.ok) {
    const message =
      typeof body?.error === "string"
        ? body.error
        : "The permissions action could not be completed.";
    throw new Error(message);
  }
  return body;
}

export async function listTablePermissions(params?: {
  page?: number;
  page_size?: number;
  connection_id?: string;
  table_id?: string;
  user_id?: string;
  role_id?: string;
}) {
  const query = new URLSearchParams();
  query.set("page", (params?.page ?? 1).toString());
  query.set("page_size", (params?.page_size ?? 100).toString());
  if (params?.connection_id) query.set("connection_id", params.connection_id);
  if (params?.table_id) query.set("table_id", params.table_id);
  if (params?.user_id) query.set("user_id", params.user_id);
  if (params?.role_id) query.set("role_id", params.role_id);

  const data = await permissionRequest(
    `/api/backend/permissions/tables?${query.toString()}`,
  );
  return tablePermissionListResponseSchema.parse(data);
}

export async function getTablePermission(permissionId: string) {
  const data = await permissionRequest(
    `/api/backend/permissions/tables/${permissionId}`,
  );
  return tablePermissionResponseSchema.parse(data);
}

export async function createTablePermission(
  input: TablePermissionCreateInput,
): Promise<TablePermissionResponse> {
  const data = await permissionRequest(`/api/backend/permissions/tables`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
  return tablePermissionResponseSchema.parse(data);
}

export async function updateTablePermission(
  permissionId: string,
  input: TablePermissionUpdateInput,
): Promise<TablePermissionResponse> {
  const data = await permissionRequest(
    `/api/backend/permissions/tables/${permissionId}`,
    {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    },
  );
  return tablePermissionResponseSchema.parse(data);
}

export async function deleteTablePermission(
  permissionId: string,
): Promise<void> {
  const response = await fetch(
    `/api/backend/permissions/tables/${permissionId}`,
    {
      method: "DELETE",
    },
  );
  if (response.status === 403) {
    const body = (await response.json().catch(() => null)) as {
      code?: unknown;
    } | null;
    if (body?.code === "ADMINISTRATOR_REQUIRED") {
      throw new AdministratorRequiredError();
    }
  }
  if (!response.ok && response.status !== 204) {
    const body = (await response.json().catch(() => null)) as {
      error?: unknown;
    } | null;
    const message =
      typeof body?.error === "string"
        ? body.error
        : "Failed to revoke table permission";
    throw new Error(message);
  }
}

export async function getColumnPermissions(permissionId: string) {
  const data = await permissionRequest(
    `/api/backend/permissions/tables/${permissionId}/columns`,
  );
  return columnPermissionListResponseSchema.parse(data);
}

export async function replaceColumnPermissions(
  permissionId: string,
  items: ColumnPermissionItem[],
) {
  const payload = columnPermissionReplaceSchema.parse({ items });
  const data = await permissionRequest(
    `/api/backend/permissions/tables/${permissionId}/columns`,
    {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return columnPermissionListResponseSchema.parse(data);
}
