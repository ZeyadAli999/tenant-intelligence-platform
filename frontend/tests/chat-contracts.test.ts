import { describe, expect, test } from "vitest";
import { sourceMode, validateSourceSelection } from "@/lib/chat-contracts";
import {
  initialStreamState,
  SSEParser,
  streamReducer,
  type ChatEvent,
} from "@/lib/sse";

const one = "11111111-1111-4111-8111-111111111111";
const two = "22222222-2222-4222-8222-222222222222";

describe("source selection", () => {
  test.each([
    [[], [], "General"],
    [[one], [], "Database"],
    [[], [one], "Documents"],
    [[one], [two], "Hybrid"],
  ])("derives the source mode", (databases, knowledge, expected) =>
    expect(sourceMode(databases, knowledge)).toBe(expected),
  );
  test("rejects duplicate and excessive sources", () => {
    expect(validateSourceSelection([one, one], [])).toMatch(/only once/);
    expect(validateSourceSelection([one, two], [])).toMatch(/one database/);
    expect(
      validateSourceSelection(
        [],
        Array.from(
          { length: 11 },
          (_, i) => `${String(i).padStart(8, "0")}-1111-4111-8111-111111111111`,
        ),
      ),
    ).toMatch(/ten/);
  });
  test("accepts documented source limits", () =>
    expect(validateSourceSelection([one], [two])).toBeNull());
});

describe("SSE parser", () => {
  test("parses events fragmented across arbitrary chunks", () => {
    const parser = new SSEParser();
    expect(parser.push("event: answer_del")).toEqual([]);
    expect(parser.push('ta\r\ndata: {"text":"hel')).toEqual([]);
    expect(parser.push('lo"}\r\n\r\n')).toEqual([
      { event: "answer_delta", data: { text: "hello" } },
    ]);
    parser.finish();
  });
  test("parses multiple LF events in one chunk and ignores unknown events", () => {
    const parser = new SSEParser();
    expect(
      parser.push(
        'event: classified\ndata: {"intent":"database"}\n\nevent: future\ndata: {"secret":"ignored"}\n\nevent: query_executed\ndata: {"row_count":2,"truncated":false}\n\n',
      ),
    ).toEqual([
      { event: "classified", data: { intent: "database" } },
      { event: "query_executed", data: { row_count: 2, truncated: false } },
    ]);
  });
  test("rejects malformed known events and incomplete termination", () => {
    expect(() =>
      new SSEParser().push("event: answer_delta\ndata: nope\n\n"),
    ).toThrow("STREAM_EVENT_INVALID");
    const parser = new SSEParser();
    parser.push("event: completed\ndata:");
    expect(() => parser.finish()).toThrow("STREAM_INCOMPLETE");
  });
});

describe("stream reducer", () => {
  test("preserves ordered deltas and terminal backend truth", () => {
    let state = streamReducer(initialStreamState, { event: "begin" });
    state = streamReducer(state, {
      event: "answer_delta",
      data: { text: "one " },
    });
    state = streamReducer(state, {
      event: "answer_delta",
      data: { text: "two" },
    });
    expect(state.answer).toBe("one two");
    const completed: ChatEvent = {
      event: "completed",
      data: {
        conversation_id: one,
        message_id: two,
        answer: "authoritative",
        intent: "general",
        sources_used: [],
        sql: null,
        citations: [],
        warnings: [],
        usage: {
          prompt_tokens: 2,
          completion_tokens: 1,
          provider_latency_ms: 4,
        },
      },
    };
    state = streamReducer(state, completed);
    expect(state).toMatchObject({
      phase: "completed",
      answer: "authoritative",
      status: "Completed",
    });
  });
  test("tracks truthful SQL stages and cancellation", () => {
    let state = streamReducer(initialStreamState, {
      event: "query_validated",
      data: { normalized_sql: "SELECT 1" },
    });
    expect(state.status).toBe("SQL validated");
    state = streamReducer(state, {
      event: "query_executed",
      data: { row_count: 1, truncated: false },
    });
    expect(state).toMatchObject({ status: "Query executed", rowCount: 1 });
    expect(streamReducer(state, { event: "cancel" }).phase).toBe("cancelled");
    expect(streamReducer(state, { event: "reset" })).toEqual(
      initialStreamState,
    );
  });
});
