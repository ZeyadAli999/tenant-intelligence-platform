import { NextRequest } from "next/server";
import { beforeEach, describe, expect, test, vi } from "vitest";

const cookieValues = new Map([["ti_access", "server-access"]]);
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) =>
      cookieValues.has(name) ? { value: cookieValues.get(name) } : undefined,
  })),
}));
const context = (path: string[]) => ({ params: Promise.resolve({ path }) });
const request = (
  path: string,
  method = "GET",
  body?: object,
  headers: Record<string, string> = {},
) =>
  new NextRequest(`http://frontend.local/api/backend/${path}`, {
    method,
    body: body ? JSON.stringify(body) : undefined,
    headers: {
      host: "frontend.local",
      cookie: "ti_access=server-access",
      ...(body
        ? {
            "content-type": "application/json",
            origin: "http://frontend.local",
          }
        : {}),
      ...headers,
    },
  });

describe("chat BFF contracts", () => {
  beforeEach(() => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend.internal:8000");
    cookieValues.set("ti_access", "server-access");
  });
  test("allowlists exact methods and validates UUID paths", async () => {
    const { resolveContract } =
      await import("@/app/api/backend/[...path]/route");
    expect(resolveContract("GET", ["conversations"])).not.toBeNull();
    expect(resolveContract("POST", ["chat", "stream"])?.stream).toBe(true);
    expect(resolveContract("PUT", ["conversations"])).toBeNull();
    expect(resolveContract("GET", ["conversations", "not-a-uuid"])).toBeNull();
    expect(
      resolveContract("GET", [
        "messages",
        "11111111-1111-4111-8111-111111111111",
        "sql",
      ]),
    ).not.toBeNull();
    expect(resolveContract("GET", ["users"])).toBeNull();
  });
  test("rejects unsupported queries, traversal, and cross-origin mutations", async () => {
    const route = await import("@/app/api/backend/[...path]/route");
    expect(
      (
        await route.GET(
          request("conversations?tenant_id=x"),
          context(["conversations"]),
        )
      ).status,
    ).toBe(400);
    expect(
      (await route.GET(request("users"), context(["..", "users"]))).status,
    ).toBe(400);
    expect(
      (
        await route.POST(
          request(
            "chat",
            "POST",
            { conversation_id: "x", message: "x" },
            { origin: "https://evil.test" },
          ),
          context(["chat"]),
        )
      ).status,
    ).toBe(400);
  });
  test("injects cookie authorization and never forwards browser authorization", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        expect(String(input)).toBe(
          "http://backend.internal:8000/api/conversations?page=1&page_size=100",
        );
        const headers = new Headers(init?.headers);
        expect(headers.get("authorization")).toBe("Bearer server-access");
        expect(headers.get("authorization")).not.toContain("browser-token");
        return new Response(
          JSON.stringify({ items: [], total: 0, page: 1, page_size: 100 }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("@/app/api/backend/[...path]/route");
    const response = await GET(
      request("conversations?page=1&page_size=100", "GET", undefined, {
        authorization: "Bearer browser-token",
      }),
      context(["conversations"]),
    );
    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
  });
  test("forwards SSE body progressively with safe headers", async () => {
    let pushed = false;
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(
            'event: started\ndata: {"conversation_id":"11111111-1111-4111-8111-111111111111","message_id":"22222222-2222-4222-8222-222222222222"}\n\n',
          ),
        );
        setTimeout(() => {
          pushed = true;
          try {
            controller.enqueue(
              new TextEncoder().encode(
                'event: answer_delta\ndata: {"text":"safe"}\n\n',
              ),
            );
            controller.close();
          } catch {
            // Stream was closed by consumer
          }
        }, 10);
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(body, {
            status: 200,
            headers: {
              "content-type": "text/event-stream",
              "x-request-id": "request-safe",
            },
          }),
      ),
    );
    const { POST } = await import("@/app/api/backend/[...path]/route");
    const response = await POST(
      request("chat/stream", "POST", {
        conversation_id: "11111111-1111-4111-8111-111111111111",
        message: "safe",
        database_connection_ids: [],
        knowledge_base_ids: [],
        stream: true,
      }),
      context(["chat", "stream"]),
    );
    expect(response.headers.get("x-accel-buffering")).toBe("no");
    const reader = response.body!.getReader();
    const first = await reader.read();
    expect(new TextDecoder().decode(first.value)).toContain("started");
    expect(pushed).toBe(false);
    await reader.cancel();
  });
  test("sanitizes upstream error bodies and blocks tenant override", async () => {
    const fetchMock = vi.fn(
      async () => new Response("database secret trace", { status: 500 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/api/backend/[...path]/route");
    const blocked = await POST(
      request("chat", "POST", { tenant_id: "bad" }),
      context(["chat"]),
    );
    expect(blocked.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
    const failed = await POST(
      request("chat", "POST", {
        conversation_id: "11111111-1111-4111-8111-111111111111",
        message: "safe",
      }),
      context(["chat"]),
    );
    expect(await failed.text()).not.toContain("database secret trace");
  });
});
