import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  knowledgeBaseCreateSchema,
  storedFileResponseSchema,
} from "@/lib/knowledge-contracts";

const cookieValues = new Map([["ti_access", "server-access"]]);
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) =>
      cookieValues.has(name) ? { value: cookieValues.get(name) } : undefined,
  })),
}));

const context = (path: string[]) => ({ params: Promise.resolve({ path }) });

const validKbUuid = "11111111-1111-4111-8111-111111111111";
const validFileUuid = "22222222-2222-4222-8222-222222222222";

describe("Phase 5C BFF Contracts & Proxy", () => {
  beforeEach(() => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend.internal:8000");
    cookieValues.set("ti_access", "server-access");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  test("resolveContract allowlists exact paths, methods, and UUIDs for Knowledge Base & Files", async () => {
    const { resolveContract } =
      await import("@/app/api/backend/[...path]/route");

    // KB routes
    expect(resolveContract("GET", ["knowledge-bases"])).not.toBeNull();
    expect(resolveContract("POST", ["knowledge-bases"])).not.toBeNull();
    expect(
      resolveContract("GET", ["knowledge-bases", validKbUuid]),
    ).not.toBeNull();
    expect(
      resolveContract("PUT", ["knowledge-bases", validKbUuid]),
    ).not.toBeNull();
    expect(
      resolveContract("DELETE", ["knowledge-bases", validKbUuid]),
    ).not.toBeNull();
    expect(
      resolveContract("POST", ["knowledge-bases", validKbUuid, "files"])
        ?.multipart,
    ).toBe(true);

    // File routes
    expect(resolveContract("GET", ["files"])).not.toBeNull();
    expect(resolveContract("POST", ["files", "upload"])?.multipart).toBe(true);
    expect(resolveContract("GET", ["files", validFileUuid])).not.toBeNull();
    expect(resolveContract("DELETE", ["files", validFileUuid])).not.toBeNull();
    expect(
      resolveContract("POST", ["files", validFileUuid, "reprocess"]),
    ).not.toBeNull();

    // Rejections
    expect(
      resolveContract("GET", ["knowledge-bases", "invalid-uuid"]),
    ).toBeNull();
    expect(resolveContract("POST", ["files", "invalid-uuid"])).toBeNull();
    expect(resolveContract("DELETE", ["knowledge-bases"])).toBeNull();
    expect(resolveContract("PUT", ["files"])).toBeNull();
  });

  test("validates query parameters for file listing", async () => {
    const { resolveContract } =
      await import("@/app/api/backend/[...path]/route");
    const contract = resolveContract("GET", ["files"]);
    expect(contract).not.toBeNull();
    expect(contract?.query.has("knowledge_base_id")).toBe(true);
    expect(contract?.query.has("processing_status")).toBe(true);
    expect(contract?.query.has("extension")).toBe(true);
    expect(contract?.query.has("page")).toBe(true);
    expect(contract?.query.has("page_size")).toBe(true);
    expect(contract?.query.has("unsupported_param")).toBe(false);
  });

  test("rejects state-changing requests without same-origin header", async () => {
    const route = await import("@/app/api/backend/[...path]/route");
    const req = new NextRequest(
      `http://frontend.local/api/backend/knowledge-bases`,
      {
        method: "POST",
        body: JSON.stringify({ name: "New KB" }),
        headers: {
          "content-type": "application/json",
          // missing origin header
        },
      },
    );
    const res = await route.POST(req, context(["knowledge-bases"]));
    expect(res.status).toBe(400);
  });

  test("rejects requests supplying tenant_id in JSON payload", async () => {
    const route = await import("@/app/api/backend/[...path]/route");
    const req = new NextRequest(
      `http://frontend.local/api/backend/knowledge-bases`,
      {
        method: "POST",
        body: JSON.stringify({ name: "New KB", tenant_id: validKbUuid }),
        headers: {
          host: "frontend.local",
          origin: "http://frontend.local",
          "content-type": "application/json",
        },
      },
    );
    const res = await route.POST(req, context(["knowledge-bases"]));
    expect(res.status).toBe(400);
  });

  test("securely proxies multipart/form-data upload forwarding with boundary header", async () => {
    const fetchSpy = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            id: validFileUuid,
            knowledge_base_id: validKbUuid,
            original_name: "test.pdf",
            mime_type: "application/pdf",
            detected_mime_type: "application/pdf",
            extension: ".pdf",
            file_size_bytes: 1024,
            checksum: "abc",
            processing_status: "pending",
            processing_error_code: null,
            processing_error_message: null,
            processing_attempts: 0,
            page_count: null,
            extracted_text_length: null,
            chunk_count: 0,
            ingestion_version: 1,
            active_ingestion_version: 0,
            created_at: new Date().toISOString(),
            processing_started_at: null,
            processed_at: null,
            updated_at: new Date().toISOString(),
          }),
          { status: 202, headers: { "content-type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", fetchSpy);

    const route = await import("@/app/api/backend/[...path]/route");
    const boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
    const multipartBody = `--${boundary}\r\nContent-Disposition: form-data; name="upload"; filename="test.pdf"\r\nContent-Type: application/pdf\r\n\r\nTest Content\r\n--${boundary}--\r\n`;

    const req = new NextRequest(
      `http://frontend.local/api/backend/knowledge-bases/${validKbUuid}/files`,
      {
        method: "POST",
        body: multipartBody,
        headers: {
          host: "frontend.local",
          origin: "http://frontend.local",
          cookie: "ti_access=server-access",
          "content-type": `multipart/form-data; boundary=${boundary}`,
        },
      },
    );

    const res = await route.POST(
      req,
      context(["knowledge-bases", validKbUuid, "files"]),
    );
    expect(res.status).toBe(202);
    expect(fetchSpy).toHaveBeenCalled();

    const fetchCall = fetchSpy.mock.calls[0] as unknown as [
      URL,
      RequestInit,
    ];
    expect(fetchCall[0].toString()).toBe(
      `http://backend.internal:8000/api/knowledge-bases/${validKbUuid}/files`,
    );
    const fetchHeaders = new Headers(fetchCall[1].headers);
    expect(fetchHeaders.get("content-type")).toBe(
      `multipart/form-data; boundary=${boundary}`,
    );
    expect(fetchHeaders.get("authorization")).toBe("Bearer server-access");
  });

  test("rejects upload request without multipart content-type", async () => {
    const route = await import("@/app/api/backend/[...path]/route");
    const req = new NextRequest(
      `http://frontend.local/api/backend/knowledge-bases/${validKbUuid}/files`,
      {
        method: "POST",
        body: JSON.stringify({ name: "not-multipart" }),
        headers: {
          host: "frontend.local",
          origin: "http://frontend.local",
          "content-type": "application/json",
        },
      },
    );

    const res = await route.POST(
      req,
      context(["knowledge-bases", validKbUuid, "files"]),
    );
    expect(res.status).toBe(400);
  });
});

describe("Phase 5C Zod Contracts", () => {
  test("knowledgeBaseCreateSchema validates input names and limits", () => {
    expect(
      knowledgeBaseCreateSchema.safeParse({ name: "Valid KB" }).success,
    ).toBe(true);
    expect(knowledgeBaseCreateSchema.safeParse({ name: "   " }).success).toBe(
      false,
    );
    expect(
      knowledgeBaseCreateSchema.safeParse({ name: "A".repeat(201) }).success,
    ).toBe(false);
  });

  test("storedFileResponseSchema parses complete stored file payload", () => {
    const validFile = {
      id: validFileUuid,
      knowledge_base_id: validKbUuid,
      original_name: "doc.docx",
      mime_type:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      detected_mime_type:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      extension: ".docx",
      file_size_bytes: 2048,
      checksum: "sha256hash",
      processing_status: "ready",
      processing_error_code: null,
      processing_error_message: null,
      processing_attempts: 1,
      page_count: 5,
      extracted_text_length: 1200,
      chunk_count: 3,
      ingestion_version: 1,
      active_ingestion_version: 1,
      created_at: new Date().toISOString(),
      processing_started_at: new Date().toISOString(),
      processed_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    expect(storedFileResponseSchema.safeParse(validFile).success).toBe(true);
  });
});
