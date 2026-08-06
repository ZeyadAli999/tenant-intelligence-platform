"use client";

import { useRef, useState } from "react";
import { AlertCircle, LoaderCircle, Upload } from "lucide-react";

const MAX_FILE_BYTES = 26_214_400; // 25 MB
const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".csv", ".txt"];

interface FileUploadDropzoneProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

export function FileUploadDropzone({
  onUpload,
  disabled = false,
}: FileUploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      return `Unsupported file format. Supported formats: ${SUPPORTED_EXTENSIONS.join(", ")}`;
    }
    if (file.size > MAX_FILE_BYTES) {
      return `File size exceeds the 25 MB limit.`;
    }
    return null;
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    setError(null);

    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setIsUploading(true);
    try {
      await onUpload(file);
      setSelectedFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled && !isUploading) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled || isUploading) return;
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="w-full">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => {
          if (!disabled && !isUploading && inputRef.current) {
            inputRef.current.click();
          }
        }}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors cursor-pointer ${
          isDragOver
            ? "border-[var(--primary)] bg-[var(--nav-selected)]"
            : "border-[var(--border-strong)] bg-[var(--surface)] hover:bg-[var(--surface-subtle)]"
        } ${disabled || isUploading ? "cursor-not-allowed opacity-60" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          data-testid="file-input"
          accept={SUPPORTED_EXTENSIONS.join(",")}
          className="hidden"
          disabled={disabled || isUploading}
          onChange={(e) => handleFiles(e.target.files)}
        />

        {isUploading ? (
          <div className="flex flex-col items-center gap-2 py-2">
            <LoaderCircle
              aria-hidden
              className="h-8 w-8 animate-spin text-[var(--primary)] motion-reduce:animate-none"
            />
            <p className="text-sm font-medium text-[var(--text)]">
              Uploading {selectedFile?.name}...
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              Securing and queueing for document ingestion
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface-subtle)] text-[var(--text-secondary)]">
              <Upload aria-hidden className="h-5 w-5 text-[var(--primary)]" />
            </div>
            <div>
              <p className="text-sm font-medium text-[var(--text)]">
                Drag and drop your document here, or{" "}
                <span className="text-[var(--primary)] font-semibold underline">
                  browse
                </span>
              </p>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                Supported formats: PDF, DOCX, XLSX, CSV, TXT (Max 25 MB)
              </p>
            </div>
          </div>
        )}
      </div>

      {error ? (
        <div
          role="alert"
          className="mt-3 flex items-center gap-2 rounded-md bg-red-500/10 p-3 text-sm text-[var(--danger)]"
        >
          <AlertCircle aria-hidden className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}
    </div>
  );
}
