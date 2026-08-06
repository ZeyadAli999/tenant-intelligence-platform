import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { ChatWorkspace } from "@/components/chat-workspace";

const cid = "11111111-1111-4111-8111-111111111111";
const mid = "22222222-2222-4222-8222-222222222222";
const now = "2026-08-04T12:00:00Z";
const conversation = {
  id: cid,
  title: "Customer review",
  status: "active",
  database_connection_ids: [],
  knowledge_base_ids: [],
  created_at: now,
  updated_at: now,
  last_message_at: null,
};
const list = (items = [conversation]) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 100,
});
const detail = (messages: object[] = []) => ({
  ...conversation,
  messages,
  message_total: messages.length,
  message_page: 1,
  message_page_size: 100,
});
const dbs = {
  items: [
    {
      id: mid,
      name: "Customer warehouse",
      status: "connected",
      is_active: true,
      database_type: "postgresql",
    },
  ],
  total: 1,
  page: 1,
  page_size: 100,
};
const kbs = {
  items: [
    { id: mid, name: "Policy library", description: null, status: "active" },
  ],
  total: 1,
  page: 1,
  page_size: 100,
};
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

beforeEach(() => {
  history.replaceState(null, "", "/chat");
});

test("renders honest empty state and source-aware conversation dialog", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.includes("database-connections")
        ? json(dbs)
        : url.includes("knowledge-bases")
          ? json(kbs)
          : json(list([])),
    ),
  );
  render(<ChatWorkspace />);
  expect(
    await screen.findByRole("heading", { name: "No active conversation" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Chat workspace" }),
  ).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
  expect(
    screen.getByText("No conversations").closest('[role="list"]'),
  ).toBeNull();
  await userEvent.click(
    screen.getAllByRole("button", { name: "New conversation" })[0],
  );
  expect(
    screen.getByRole("dialog", { name: "New conversation" }),
  ).toBeVisible();
  expect(screen.getByText("Customer warehouse")).toBeVisible();
  expect(screen.getByText("Policy library")).toBeVisible();
  expect(screen.getByText(/General/)).toBeVisible();
});

test("loads conversation history and treats model HTML as text", async () => {
  const message = {
    id: mid,
    parent_message_id: null,
    role: "assistant",
    message_type: "general",
    content: '<img src=x onerror="alert(1)">Safe',
    detected_intent: "general",
    selected_sources: [],
    status: "completed",
    model_name: "safe-model",
    prompt_tokens: 4,
    completion_tokens: 2,
    latency_ms: 10,
    warnings: [],
    created_at: now,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.includes(`conversations/${cid}`)
        ? json(detail([message]))
        : url.includes("database-connections")
          ? json({ ...dbs, items: [] })
          : url.includes("knowledge-bases")
            ? json({ ...kbs, items: [] })
            : json(list()),
    ),
  );
  const { container } = render(<ChatWorkspace />);
  expect(await screen.findByText(/<img src=x onerror/)).toBeVisible();
  expect(container.querySelector("img")).toBeNull();
  expect(
    screen.getByRole("button", { name: "Inspect response details" }),
  ).toBeVisible();
});

test("composer supports Shift+Enter, Enter send, and duplicate prevention", async () => {
  let resolveStream!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => {
    resolveStream = resolve;
  });
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("chat/stream")) return pending;
    if (url.includes(`conversations/${cid}`)) return json(detail());
    if (url.includes("database-connections"))
      return json({ ...dbs, items: [] });
    if (url.includes("knowledge-bases")) return json({ ...kbs, items: [] });
    return json(list());
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ChatWorkspace />);
  const composer = await screen.findByLabelText("Message");
  await waitFor(() => expect(composer).toBeEnabled());
  await userEvent.type(
    composer,
    "First line{shift>}{enter}{/shift}Second line",
  );
  expect(composer).toHaveValue("First line\nSecond line");
  fireEvent.keyDown(composer, { key: "Enter" });
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).endsWith("chat/stream"),
      ),
    ).toHaveLength(1),
  );
  expect(screen.getByRole("button", { name: "Cancel response" })).toBeVisible();
  fireEvent.keyDown(composer, { key: "Enter" });
  expect(
    fetchMock.mock.calls.filter(([url]) => String(url).endsWith("chat/stream")),
  ).toHaveLength(1);
  resolveStream(new Response(null, { status: 500 }));
});

test("composer enforces 4000 characters and deletion requires confirmation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.includes(`conversations/${cid}`)
        ? json(detail())
        : url.includes("database-connections")
          ? json({ ...dbs, items: [] })
          : url.includes("knowledge-bases")
            ? json({ ...kbs, items: [] })
            : json(list()),
    ),
  );
  render(<ChatWorkspace />);
  const composer = await screen.findByLabelText("Message");
  await waitFor(() => expect(composer).toBeEnabled());
  fireEvent.change(composer, { target: { value: "x".repeat(4000) } });
  expect(screen.getByText("0 characters remaining")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Delete Customer review" }),
  );
  expect(
    screen.getByRole("alertdialog", { name: "Delete conversation?" }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});

test("persisted assistant response exposes safe usage, SQL, and both citation types", async () => {
  const message = {
    id: mid,
    parent_message_id: null,
    role: "assistant",
    message_type: "hybrid",
    content: "Grounded answer",
    detected_intent: "hybrid",
    selected_sources: ["database", "documents"],
    status: "completed",
    model_name: "safe-model",
    prompt_tokens: 14,
    completion_tokens: 7,
    latency_ms: 25,
    warnings: ["Result limited"],
    created_at: now,
  };
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith(`/messages/${mid}/sql`))
      return json({
        message_id: mid,
        query_execution_id: cid,
        normalized_sql: "SELECT name FROM business.customers",
        execution_status: "succeeded",
        row_count: 2,
        truncated: false,
        referenced_tables: ["business.customers"],
      });
    if (url.endsWith(`/messages/${mid}/citations`))
      return json({
        items: [
          {
            type: "database",
            table: "business.customers",
            query_execution_id: cid,
            columns: ["name"],
          },
          {
            type: "document",
            file_id: cid,
            chunk_id: mid,
            file_name: "policy.pdf",
            page_number: 3,
            section_title: "Eligibility",
            sheet_name: null,
            row_start: null,
            row_end: null,
            relevance_score: 0.91,
          },
        ],
      });
    if (url.includes(`conversations/${cid}`)) return json(detail([message]));
    if (url.includes("database-connections"))
      return json({ ...dbs, items: [] });
    if (url.includes("knowledge-bases")) return json({ ...kbs, items: [] });
    return json(list());
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ChatWorkspace />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Inspect response details" }),
  );
  expect((await screen.findAllByText("14"))[0]).toBeVisible();
  await userEvent.click(screen.getAllByRole("tab", { name: "sql" })[0]);
  expect(
    (await screen.findAllByLabelText("Validated SQL"))[0],
  ).toHaveTextContent("business.customers");
  await userEvent.click(screen.getAllByRole("tab", { name: "citations" })[0]);
  expect((await screen.findAllByText("policy.pdf"))[0]).toBeVisible();
  expect(screen.getAllByText("business.customers")[0]).toBeVisible();
});
