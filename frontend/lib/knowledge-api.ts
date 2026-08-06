import {
  KnowledgeBaseCreateInput,
  KnowledgeBaseListResponse,
  KnowledgeBaseResponse,
  KnowledgeBaseUpdateInput,
  StoredFileListResponse,
  StoredFileResponse,
  knowledgeBaseListResponseSchema,
  knowledgeBaseResponseSchema,
  storedFileListResponseSchema,
  storedFileResponseSchema,
} from "./knowledge-contracts";

async function handleResponse<T>(
  res: Response,
  parseFn?: (data: unknown) => T,
): Promise<T> {
  if (!res.ok) {
    let message = "An error occurred";
    try {
      const data = await res.json();
      if (data && typeof data === "object" && "message" in data) {
        message = String(data.message);
      }
    } catch {
      // Fallback
    }
    throw new Error(message);
  }

  if (res.status === 204) {
    return undefined as unknown as T;
  }

  const json = await res.json();
  if (parseFn) {
    return parseFn(json);
  }
  return json as T;
}

export async function listKnowledgeBases(
  page = 1,
  pageSize = 20,
): Promise<KnowledgeBaseListResponse> {
  const res = await fetch(
    `/api/backend/knowledge-bases?page=${page}&page_size=${pageSize}`,
    { cache: "no-store" },
  );
  return handleResponse(res, knowledgeBaseListResponseSchema.parse);
}

export async function createKnowledgeBase(
  input: KnowledgeBaseCreateInput,
): Promise<KnowledgeBaseResponse> {
  const res = await fetch("/api/backend/knowledge-bases", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
    cache: "no-store",
  });
  return handleResponse(res, knowledgeBaseResponseSchema.parse);
}

export async function getKnowledgeBase(
  id: string,
): Promise<KnowledgeBaseResponse> {
  const res = await fetch(`/api/backend/knowledge-bases/${id}`, {
    cache: "no-store",
  });
  return handleResponse(res, knowledgeBaseResponseSchema.parse);
}

export async function updateKnowledgeBase(
  id: string,
  input: KnowledgeBaseUpdateInput,
): Promise<KnowledgeBaseResponse> {
  const res = await fetch(`/api/backend/knowledge-bases/${id}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
    cache: "no-store",
  });
  return handleResponse(res, knowledgeBaseResponseSchema.parse);
}

export async function deleteKnowledgeBase(id: string): Promise<void> {
  const res = await fetch(`/api/backend/knowledge-bases/${id}`, {
    method: "DELETE",
    cache: "no-store",
  });
  return handleResponse(res);
}

export async function uploadFileToKnowledgeBase(
  kbId: string,
  file: File,
): Promise<StoredFileResponse> {
  const formData = new FormData();
  formData.append("upload", file);

  const res = await fetch(`/api/backend/knowledge-bases/${kbId}/files`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });
  return handleResponse(res, storedFileResponseSchema.parse);
}

export interface ListFilesParams {
  knowledge_base_id?: string;
  processing_status?: string;
  extension?: string;
  page?: number;
  page_size?: number;
}

export async function listFiles(
  params: ListFilesParams = {},
): Promise<StoredFileListResponse> {
  const query = new URLSearchParams();
  if (params.knowledge_base_id)
    query.set("knowledge_base_id", params.knowledge_base_id);
  if (params.processing_status)
    query.set("processing_status", params.processing_status);
  if (params.extension) query.set("extension", params.extension);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));

  const queryString = query.toString() ? `?${query.toString()}` : "";
  const res = await fetch(`/api/backend/files${queryString}`, {
    cache: "no-store",
  });
  return handleResponse(res, storedFileListResponseSchema.parse);
}

export async function getFile(id: string): Promise<StoredFileResponse> {
  const res = await fetch(`/api/backend/files/${id}`, { cache: "no-store" });
  return handleResponse(res, storedFileResponseSchema.parse);
}

export async function deleteFile(id: string): Promise<void> {
  const res = await fetch(`/api/backend/files/${id}`, {
    method: "DELETE",
    cache: "no-store",
  });
  return handleResponse(res);
}

export async function reprocessFile(id: string): Promise<StoredFileResponse> {
  const res = await fetch(`/api/backend/files/${id}/reprocess`, {
    method: "POST",
    cache: "no-store",
  });
  return handleResponse(res, storedFileResponseSchema.parse);
}
