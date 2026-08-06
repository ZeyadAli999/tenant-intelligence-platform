import { z } from "zod";

export const knowledgeBaseCreateSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  description: z.string().max(2000).nullable().optional(),
});

export const knowledgeBaseUpdateSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200).optional(),
  description: z.string().max(2000).nullable().optional(),
  status: z.enum(["active", "inactive"]).optional(),
});

export const knowledgeBaseResponseSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  description: z.string().nullable(),
  embedding_model: z.string(),
  embedding_dimension: z.number().int(),
  status: z.string(),
  created_by: z.string().uuid(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const knowledgeBaseListResponseSchema = z.object({
  items: z.array(knowledgeBaseResponseSchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
});

export const processingStatusSchema = z.enum([
  "pending",
  "processing",
  "ready",
  "failed",
  "deleting",
  "deleted",
]);

export const supportedExtensionSchema = z.enum([
  ".pdf",
  ".docx",
  ".xlsx",
  ".csv",
  ".txt",
]);

export const storedFileResponseSchema = z.object({
  id: z.string().uuid(),
  knowledge_base_id: z.string().uuid(),
  original_name: z.string(),
  mime_type: z.string().nullable(),
  detected_mime_type: z.string(),
  extension: z.string(),
  file_size_bytes: z.number().int().nonnegative(),
  checksum: z.string(),
  processing_status: processingStatusSchema,
  processing_error_code: z.string().nullable(),
  processing_error_message: z.string().nullable(),
  processing_attempts: z.number().int().nonnegative(),
  page_count: z.number().int().nullable(),
  extracted_text_length: z.number().int().nullable(),
  chunk_count: z.number().int().nonnegative(),
  ingestion_version: z.number().int().positive(),
  active_ingestion_version: z.number().int().nonnegative(),
  created_at: z.string(),
  processing_started_at: z.string().nullable(),
  processed_at: z.string().nullable(),
  updated_at: z.string(),
});

export const storedFileListResponseSchema = z.object({
  items: z.array(storedFileResponseSchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
});

export type KnowledgeBaseCreateInput = z.infer<
  typeof knowledgeBaseCreateSchema
>;
export type KnowledgeBaseUpdateInput = z.infer<
  typeof knowledgeBaseUpdateSchema
>;
export type KnowledgeBaseResponse = z.infer<typeof knowledgeBaseResponseSchema>;
export type KnowledgeBaseListResponse = z.infer<
  typeof knowledgeBaseListResponseSchema
>;
export type StoredFileResponse = z.infer<typeof storedFileResponseSchema>;
export type StoredFileListResponse = z.infer<
  typeof storedFileListResponseSchema
>;
export type ProcessingStatus = z.infer<typeof processingStatusSchema>;
export type SupportedExtension = z.infer<typeof supportedExtensionSchema>;
