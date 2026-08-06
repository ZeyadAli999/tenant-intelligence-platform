import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { FileUploadDropzone } from "@/components/knowledge/file-upload-dropzone";
import { FileListTable } from "@/components/knowledge/file-list-table";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { KBModal } from "@/components/knowledge/kb-modal";
import { StoredFileResponse } from "@/lib/knowledge-contracts";

describe("Phase 5C UI Components", () => {
  test("FileUploadDropzone validates file size and extension client-side", async () => {
    const onUpload = vi.fn(async () => {});
    render(<FileUploadDropzone onUpload={onUpload} />);

    const input = screen.getByTestId("file-input");

    // Invalid extension file
    const invalidFile = new File(["dummy content"], "test.exe", {
      type: "application/x-msdownload",
    });
    fireEvent.change(input, { target: { files: [invalidFile] } });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unsupported file format",
    );
    expect(onUpload).not.toHaveBeenCalled();
  });

  test("FileListTable displays status badges, details, and action buttons", () => {
    const files: StoredFileResponse[] = [
      {
        id: "11111111-1111-4111-8111-111111111111",
        knowledge_base_id: "22222222-2222-4222-8222-222222222222",
        original_name: "failed-document.pdf",
        mime_type: "application/pdf",
        detected_mime_type: "application/pdf",
        extension: ".pdf",
        file_size_bytes: 1048576,
        checksum: "abc",
        processing_status: "failed",
        processing_error_code: "CONTENT_LIMIT_EXCEEDED",
        processing_error_message: "Document exceeded max character limit",
        processing_attempts: 1,
        page_count: 10,
        extracted_text_length: null,
        chunk_count: 0,
        ingestion_version: 1,
        active_ingestion_version: 0,
        created_at: new Date().toISOString(),
        processing_started_at: null,
        processed_at: null,
        updated_at: new Date().toISOString(),
      },
    ];

    const onDelete = vi.fn(async () => {});
    const onReprocess = vi.fn(async () => {});

    render(
      <FileListTable
        files={files}
        onDeleteFile={onDelete}
        onReprocessFile={onReprocess}
      />,
    );

    expect(screen.getByText("failed-document.pdf")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(
      screen.getByText("Error: CONTENT_LIMIT_EXCEEDED"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /reprocess/i }),
    ).toBeInTheDocument();
  });

  test("ConfirmDialog renders accessibility attributes and triggers action", () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();

    render(
      <ConfirmDialog
        isOpen={true}
        title="Delete Knowledge Base"
        description="Are you sure you want to delete this knowledge base?"
        onConfirm={onConfirm}
        onClose={onClose}
      />,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("Delete Knowledge Base")).toBeInTheDocument();

    const confirmButton = screen.getByRole("button", { name: "Confirm" });
    fireEvent.click(confirmButton);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  test("KBModal validates name field before submitting", async () => {
    const onSubmit = vi.fn(async () => {});
    const onClose = vi.fn();

    render(<KBModal isOpen={true} onSubmit={onSubmit} onClose={onClose} />);

    const submitBtn = screen.getByRole("button", {
      name: "Create Knowledge Base",
    });
    fireEvent.click(submitBtn);

    expect(screen.getByRole("alert")).toHaveTextContent("Name is required");
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
