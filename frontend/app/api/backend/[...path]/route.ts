import { NextRequest, NextResponse } from "next/server";
import { safeBackendMessage, safeError } from "@/lib/server/responses";
import { authenticatedFetch, setSessionCookies } from "@/lib/server/session";

const uuid =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const listQuery = new Set(["page", "page_size"]);
const userListQuery = new Set(["page", "page_size", "search", "status"]);
const detailQuery = new Set(["message_page", "message_page_size"]);
const fileListQuery = new Set([
  "knowledge_base_id",
  "processing_status",
  "extension",
  "page",
  "page_size",
]);
const tableListQuery = new Set([
  "page",
  "page_size",
  "schema_name",
  "enabled",
  "table_type",
  "search",
]);

type Contract = {
  path: string;
  query: Set<string>;
  stream?: boolean;
  multipart?: boolean;
};

export function resolveContract(
  method: string,
  parts: string[],
): Contract | null {
  const path = parts.join("/");
  if (method === "GET" && ["health/live", "health/ready"].includes(path))
    return { path, query: new Set() };
  if (path === "users") {
    if (method === "GET") return { path, query: userListQuery };
    if (method === "POST") return { path, query: new Set() };
  }
  if (path === "roles" && method === "GET") return { path, query: listQuery };
  if (parts.length === 2 && parts[0] === "users" && uuid.test(parts[1])) {
    if (method === "PUT") return { path, query: new Set() };
  }
  if (
    parts.length === 3 &&
    parts[0] === "users" &&
    uuid.test(parts[1]) &&
    parts[2] === "roles" &&
    method === "PUT"
  )
    return { path, query: new Set() };
  if (path === "conversations") {
    if (method === "GET") return { path, query: listQuery };
    if (method === "POST") return { path, query: new Set() };
  }
  if (
    parts.length === 2 &&
    parts[0] === "conversations" &&
    uuid.test(parts[1])
  ) {
    if (method === "GET") return { path, query: detailQuery };
    if (method === "DELETE") return { path, query: new Set() };
  }
  if (method === "POST" && path === "chat") return { path, query: new Set() };
  if (method === "POST" && path === "chat/stream")
    return { path, query: new Set(), stream: true };
  if (
    method === "GET" &&
    parts.length === 3 &&
    parts[0] === "messages" &&
    uuid.test(parts[1]) &&
    ["sql", "citations"].includes(parts[2])
  )
    return { path, query: new Set() };

  // Database Connections contracts
  if (path === "database-connections") {
    if (method === "GET") return { path, query: listQuery };
    if (method === "POST") return { path, query: new Set() };
  }
  if (
    parts.length === 2 &&
    parts[0] === "database-connections" &&
    uuid.test(parts[1])
  ) {
    if (method === "GET") return { path, query: new Set() };
    if (method === "PUT") return { path, query: new Set() };
    if (method === "DELETE") return { path, query: new Set() };
  }
  if (
    parts.length === 3 &&
    parts[0] === "database-connections" &&
    uuid.test(parts[1])
  ) {
    const sub = parts[2];
    if (sub === "test" && method === "POST") return { path, query: new Set() };
    if (sub === "sync-schema" && method === "POST")
      return { path, query: new Set() };
    if (sub === "schemas" && method === "GET")
      return { path, query: listQuery };
    if (sub === "tables" && method === "GET")
      return { path, query: tableListQuery };
    if (sub === "allowed-schema" && method === "GET")
      return { path, query: new Set() };
  }

  // Knowledge Bases contracts
  if (path === "knowledge-bases") {
    if (method === "GET") return { path, query: listQuery };
    if (method === "POST") return { path, query: new Set() };
  }
  if (
    parts.length === 2 &&
    parts[0] === "knowledge-bases" &&
    uuid.test(parts[1])
  ) {
    if (method === "GET") return { path, query: new Set() };
    if (method === "PUT") return { path, query: new Set() };
    if (method === "DELETE") return { path, query: new Set() };
  }
  if (
    parts.length === 3 &&
    parts[0] === "knowledge-bases" &&
    uuid.test(parts[1]) &&
    parts[2] === "files" &&
    method === "POST"
  ) {
    return { path, query: new Set(), multipart: true };
  }

  // Files contracts
  if (path === "files") {
    if (method === "GET") return { path, query: fileListQuery };
  }
  if (path === "files/upload" && method === "POST") {
    return { path, query: new Set(), multipart: true };
  }
  if (parts.length === 2 && parts[0] === "files" && uuid.test(parts[1])) {
    if (method === "GET") return { path, query: new Set() };
    if (method === "DELETE") return { path, query: new Set() };
  }
  if (
    parts.length === 3 &&
    parts[0] === "files" &&
    uuid.test(parts[1]) &&
    parts[2] === "reprocess" &&
    method === "POST"
  ) {
    return { path, query: new Set() };
  }

  return null;
}

function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host) return false;
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

function safeRequest(
  request: NextRequest,
  parts: string[],
  contract: Contract,
): boolean {
  const raw = request.nextUrl.pathname.toLowerCase();
  if (raw.includes("%2e") || raw.includes("%2f") || raw.includes("%5c"))
    return false;
  if (
    parts.some(
      (part) => !part || part === "." || part === ".." || /[\\/?#]/.test(part),
    )
  )
    return false;

  for (const key of request.nextUrl.searchParams.keys()) {
    if (!contract.query.has(key)) return false;
  }
  return true;
}

function badRequest(message: string): NextResponse {
  return NextResponse.json({ error: message }, { status: 400 });
}

export async function handleProxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { path: parts } = await params;
  const contract = resolveContract(request.method, parts);
  if (!contract) return badRequest("Unsupported backend proxy endpoint");
  if (!safeRequest(request, parts, contract))
    return badRequest("Invalid proxy parameters");
  if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) {
    if (!sameOrigin(request))
      return badRequest("Cross-origin request rejected");
  }

  let body: BodyInit | undefined = undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    if (contract.multipart) {
      const contentType = request.headers.get("content-type") || "";
      if (!contentType.toLowerCase().includes("multipart/form-data")) {
        return badRequest("Multipart content-type required");
      }
      const rawBuffer = await request.arrayBuffer();
      if (rawBuffer.byteLength > 28 * 1024 * 1024) {
        return badRequest("Payload exceeds maximum size");
      }
      body = rawBuffer;
    } else {
      const text = await request.text();
      if (text.length > 64 * 1024)
        return badRequest("Payload exceeds maximum size");
      if (text.length > 0) {
        try {
          const parsed = JSON.parse(text);
          if (
            parsed !== null &&
            typeof parsed === "object" &&
            ("tenant_id" in parsed || "tenantId" in parsed)
          ) {
            return badRequest("Tenant ID manipulation rejected");
          }
        } catch {
          return badRequest("Invalid JSON payload");
        }
        body = text;
      }
    }
  }

  const queryStr = request.nextUrl.searchParams.toString();
  const targetPath = `${contract.path}${queryStr ? `?${queryStr}` : ""}`;

  try {
    const initHeaders: Record<string, string> = {};
    if (contract.multipart) {
      const contentType = request.headers.get("content-type");
      if (contentType) {
        initHeaders["content-type"] = contentType;
      }
    } else if (body) {
      initHeaders["content-type"] = "application/json";
    }

    const { upstream, refreshedTokens } = await authenticatedFetch(targetPath, {
      method: request.method,
      headers: initHeaders,
      body,
    });

    if (!upstream) {
      return NextResponse.json(
        { error: "Session expired or unauthorized" },
        { status: 401 },
      );
    }

    let nextResponse: NextResponse;

    if (contract.stream && upstream.ok && upstream.body) {
      const headers = new Headers();
      headers.set("content-type", "text/event-stream");
      headers.set("cache-control", "no-cache, no-transform");
      headers.set("connection", "keep-alive");
      headers.set("x-accel-buffering", "no");

      nextResponse = new NextResponse(upstream.body, {
        status: upstream.status,
        headers,
      });
    } else {
      const data = await upstream.text();
      let parsed: unknown = data;
      try {
        parsed = JSON.parse(data);
      } catch {
        // Keep raw string if non-JSON
      }

      if (!upstream.ok) {
        const message = safeBackendMessage(upstream.status);
        const upstreamCode =
          parsed !== null && typeof parsed === "object" && "code" in parsed
            ? parsed.code
            : undefined;
        const code =
          (upstream.status === 403 &&
            upstreamCode === "ADMINISTRATOR_REQUIRED") ||
          (upstream.status === 409 &&
            upstreamCode === "FINAL_ACTIVE_ADMINISTRATOR_REQUIRED")
            ? upstreamCode
            : undefined;
        nextResponse = NextResponse.json(
          { error: message, ...(code ? { code } : {}) },
          { status: upstream.status },
        );
      } else {
        nextResponse = NextResponse.json(parsed, { status: upstream.status });
      }
    }

    if (refreshedTokens) {
      setSessionCookies(nextResponse, refreshedTokens);
    }

    return nextResponse;
  } catch {
    return safeError(503, "Backend service unavailable");
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return handleProxy(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return handleProxy(request, context);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return handleProxy(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  return handleProxy(request, context);
}
