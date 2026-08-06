import { z } from "zod";
import { chatResponseSchema, type ChatResponse } from "@/lib/chat-contracts";

const eventSchemas = {
  started: z.object({ conversation_id: z.uuid(), message_id: z.uuid() }),
  classified: z.object({ intent: z.string() }),
  query_validated: z.object({ normalized_sql: z.string() }),
  query_executed: z.object({ row_count: z.number(), truncated: z.boolean() }),
  clarification: z.object({ text: z.string() }),
  answer_delta: z.object({ text: z.string() }),
  completed: chatResponseSchema,
  error: z.object({ detail: z.string() }),
} as const;
export type SSEName = keyof typeof eventSchemas;
export type ChatEvent = {
  [K in SSEName]: { event: K; data: z.infer<(typeof eventSchemas)[K]> };
}[SSEName];

export class SSEParser {
  private buffer = "";
  push(chunk: string): ChatEvent[] {
    this.buffer += chunk.replaceAll("\r\n", "\n").replaceAll("\r", "\n");
    const blocks = this.buffer.split("\n\n");
    this.buffer = blocks.pop() ?? "";
    return blocks.flatMap((block) => this.parseBlock(block));
  }
  finish(): void {
    if (this.buffer.trim()) throw new Error("STREAM_INCOMPLETE");
  }
  private parseBlock(block: string): ChatEvent[] {
    let name = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      if (line.startsWith("event:")) name = line.slice(6).trim();
      if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (!(name in eventSchemas)) return [];
    try {
      const schema = eventSchemas[name as SSEName] as z.ZodType;
      return [
        {
          event: name,
          data: schema.parse(JSON.parse(data.join("\n"))),
        } as ChatEvent,
      ];
    } catch {
      throw new Error("STREAM_EVENT_INVALID");
    }
  }
}

export type StreamState = {
  phase:
    | "idle"
    | "preparing"
    | "streaming"
    | "completed"
    | "cancelled"
    | "error";
  status: string;
  answer: string;
  intent?: string;
  sql?: string;
  rowCount?: number;
  truncated?: boolean;
  final?: ChatResponse;
  messageId?: string;
  error?: string;
};
export const initialStreamState: StreamState = {
  phase: "idle",
  status: "Ready",
  answer: "",
};
export function streamReducer(
  state: StreamState,
  event: ChatEvent | { event: "begin" | "cancel" | "reset"; data?: never },
): StreamState {
  switch (event.event) {
    case "reset":
      return initialStreamState;
    case "begin":
      return { phase: "preparing", status: "Preparing request", answer: "" };
    case "started":
      return {
        ...state,
        phase: "streaming",
        status: "Preparing request",
        messageId: event.data.message_id,
      };
    case "classified":
      return {
        ...state,
        status: "Intent classified",
        intent: event.data.intent,
      };
    case "query_validated":
      return {
        ...state,
        status: "SQL validated",
        sql: event.data.normalized_sql,
      };
    case "query_executed":
      return {
        ...state,
        status: "Query executed",
        rowCount: event.data.row_count,
        truncated: event.data.truncated,
      };
    case "clarification":
      return { ...state, status: "Generating grounded answer" };
    case "answer_delta":
      return {
        ...state,
        status: "Generating grounded answer",
        answer: state.answer + event.data.text,
      };
    case "completed":
      return {
        ...state,
        phase: "completed",
        status: "Completed",
        answer: event.data.answer,
        final: event.data,
        intent: event.data.intent,
        sql: event.data.sql?.normalized_sql,
        rowCount: event.data.sql?.row_count,
        truncated: event.data.sql?.truncated,
      };
    case "error":
      return {
        ...state,
        phase: "error",
        status: "Failed",
        error: "The response could not be completed safely.",
      };
    case "cancel":
      return {
        ...state,
        phase: "cancelled",
        status: "Cancelled",
        error: undefined,
      };
  }
}
