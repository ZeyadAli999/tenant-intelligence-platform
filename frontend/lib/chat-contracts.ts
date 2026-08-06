import { z } from "zod";

const id = z.uuid();
export const conversationSchema = z.object({
  id,
  title: z.string().nullable(),
  status: z.string(),
  database_connection_ids: z.array(id),
  knowledge_base_ids: z.array(id),
  created_at: z.string(),
  updated_at: z.string(),
  last_message_at: z.string().nullable(),
});
export const messageSchema = z.object({
  id,
  parent_message_id: id.nullable(),
  role: z.string(),
  message_type: z.string(),
  content: z.string(),
  detected_intent: z.string().nullable(),
  selected_sources: z.array(z.unknown()),
  status: z.string(),
  model_name: z.string().nullable(),
  prompt_tokens: z.number().nullable(),
  completion_tokens: z.number().nullable(),
  latency_ms: z.number().nullable(),
  warnings: z.array(z.string()),
  created_at: z.string(),
});
export const conversationListSchema = z.object({
  items: z.array(conversationSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export const conversationDetailSchema = conversationSchema.extend({
  messages: z.array(messageSchema),
  message_total: z.number(),
  message_page: z.number(),
  message_page_size: z.number(),
});
export const databaseListSchema = z.object({
  items: z.array(
    z.object({
      id,
      name: z.string(),
      status: z.string(),
      is_active: z.boolean(),
      database_type: z.string(),
    }),
  ),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export const knowledgeBaseListSchema = z.object({
  items: z.array(
    z.object({
      id,
      name: z.string(),
      description: z.string().nullable(),
      status: z.string(),
    }),
  ),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export const citationSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("database"),
    table: z.string(),
    query_execution_id: id.nullable().optional(),
    columns: z.array(z.string()).default([]),
  }),
  z.object({
    type: z.literal("document"),
    file_id: id,
    chunk_id: id,
    file_name: z.string(),
    page_number: z.number().nullable().optional(),
    section_title: z.string().nullable().optional(),
    sheet_name: z.string().nullable().optional(),
    row_start: z.number().nullable().optional(),
    row_end: z.number().nullable().optional(),
    relevance_score: z.number().nullable().optional(),
  }),
]);
export const chatResponseSchema = z.object({
  conversation_id: id,
  message_id: id,
  answer: z.string(),
  intent: z.enum([
    "general",
    "database",
    "document",
    "hybrid",
    "clarification",
  ]),
  sources_used: z.array(z.string()),
  sql: z
    .object({
      query_execution_id: id,
      normalized_sql: z.string(),
      row_count: z.number(),
      truncated: z.boolean(),
    })
    .nullable(),
  citations: z.array(citationSchema),
  warnings: z.array(z.string()),
  usage: z.object({
    prompt_tokens: z.number(),
    completion_tokens: z.number(),
    provider_latency_ms: z.number(),
  }),
});
export const sqlResponseSchema = z.object({
  message_id: id,
  query_execution_id: id,
  normalized_sql: z.string(),
  execution_status: z.string().nullable(),
  row_count: z.number().nullable(),
  truncated: z.boolean(),
  referenced_tables: z.array(z.string()),
});
export const citationListSchema = z.object({ items: z.array(citationSchema) });

export type Conversation = z.infer<typeof conversationSchema>;
export type ConversationDetail = z.infer<typeof conversationDetailSchema>;
export type Message = z.infer<typeof messageSchema>;
export type DatabaseSource = z.infer<
  typeof databaseListSchema
>["items"][number];
export type KnowledgeSource = z.infer<
  typeof knowledgeBaseListSchema
>["items"][number];
export type ChatResponse = z.infer<typeof chatResponseSchema>;
export type Citation = z.infer<typeof citationSchema>;
export type SQLDetail = z.infer<typeof sqlResponseSchema>;

export function sourceMode(databaseIds: string[], knowledgeIds: string[]) {
  if (databaseIds.length && knowledgeIds.length) return "Hybrid";
  if (databaseIds.length) return "Database";
  if (knowledgeIds.length) return "Documents";
  return "General";
}

export function validateSourceSelection(
  databaseIds: string[],
  knowledgeIds: string[],
): string | null {
  if (
    new Set(databaseIds).size !== databaseIds.length ||
    new Set(knowledgeIds).size !== knowledgeIds.length
  )
    return "Each source may be selected only once.";
  if (databaseIds.length > 1) return "Select no more than one database.";
  if (knowledgeIds.length > 10)
    return "Select no more than ten knowledge bases.";
  return null;
}
