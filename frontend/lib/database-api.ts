import {
  AllowedSchemaResponse,
  ConnectionTestResponse,
  DatabaseConnectionCreateInput,
  DatabaseConnectionListResponse,
  DatabaseConnectionResponse,
  DatabaseConnectionUpdateInput,
  DatabaseSchemaListResponse,
  DatabaseTableListResponse,
  SchemaSyncResponse,
} from "./database-contracts";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      "content-type": "application/json",
      ...options?.headers,
    },
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "An unexpected error occurred");
  }
  return data as T;
}

export async function listDatabaseConnections(
  page: number = 1,
  pageSize: number = 50,
): Promise<DatabaseConnectionListResponse> {
  return fetchJSON<DatabaseConnectionListResponse>(
    `/api/backend/database-connections?page=${page}&page_size=${pageSize}`,
  );
}

export async function createDatabaseConnection(
  input: DatabaseConnectionCreateInput,
): Promise<DatabaseConnectionResponse> {
  return fetchJSON<DatabaseConnectionResponse>(
    `/api/backend/database-connections`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export async function getDatabaseConnection(
  id: string,
): Promise<DatabaseConnectionResponse> {
  return fetchJSON<DatabaseConnectionResponse>(
    `/api/backend/database-connections/${id}`,
  );
}

export async function updateDatabaseConnection(
  id: string,
  input: DatabaseConnectionUpdateInput,
): Promise<DatabaseConnectionResponse> {
  return fetchJSON<DatabaseConnectionResponse>(
    `/api/backend/database-connections/${id}`,
    {
      method: "PUT",
      body: JSON.stringify(input),
    },
  );
}

export async function deleteDatabaseConnection(id: string): Promise<void> {
  const res = await fetch(`/api/backend/database-connections/${id}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) {
    const data = await res.json();
    throw new Error(data.error || "Failed to delete connection");
  }
}

export async function testDatabaseConnection(
  id: string,
): Promise<ConnectionTestResponse> {
  return fetchJSON<ConnectionTestResponse>(
    `/api/backend/database-connections/${id}/test`,
    { method: "POST" },
  );
}

export async function syncDatabaseSchema(
  id: string,
): Promise<SchemaSyncResponse> {
  return fetchJSON<SchemaSyncResponse>(
    `/api/backend/database-connections/${id}/sync-schema`,
    { method: "POST" },
  );
}

export async function listDatabaseSchemas(
  id: string,
  page: number = 1,
  pageSize: number = 50,
): Promise<DatabaseSchemaListResponse> {
  return fetchJSON<DatabaseSchemaListResponse>(
    `/api/backend/database-connections/${id}/schemas?page=${page}&page_size=${pageSize}`,
  );
}

export async function listDatabaseTables(
  id: string,
  params?: {
    page?: number;
    page_size?: number;
    schema_name?: string;
    enabled?: boolean;
    table_type?: "table" | "view";
    search?: string;
  },
): Promise<DatabaseTableListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", params.page.toString());
  if (params?.page_size)
    searchParams.set("page_size", params.page_size.toString());
  if (params?.schema_name) searchParams.set("schema_name", params.schema_name);
  if (params?.enabled !== undefined)
    searchParams.set("enabled", params.enabled.toString());
  if (params?.table_type) searchParams.set("table_type", params.table_type);
  if (params?.search) searchParams.set("search", params.search);

  const query = searchParams.toString();
  return fetchJSON<DatabaseTableListResponse>(
    `/api/backend/database-connections/${id}/tables${query ? `?${query}` : ""}`,
  );
}

export async function getAllowedSchema(
  id: string,
): Promise<AllowedSchemaResponse> {
  return fetchJSON<AllowedSchemaResponse>(
    `/api/backend/database-connections/${id}/allowed-schema`,
  );
}
