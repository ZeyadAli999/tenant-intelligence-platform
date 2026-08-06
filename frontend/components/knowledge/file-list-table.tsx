"use client";

import { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  FileCode,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { StoredFileResponse } from "@/lib/knowledge-contracts";

interface FileListTableProps {
  files: StoredFileResponse[];
  onDeleteFile: (fileId: string) => Promise<void>;
  onReprocessFile: (fileId: string) => Promise<void>;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

function formatDate(dateString: string | null): string {
  if (!dateString) return "—";
  try {
    return new Date(dateString).toLocaleString(undefined, {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return dateString;
  }
}

function getFileIcon(extension: string) {
  const ext = extension.toLowerCase();
  if (ext === ".pdf" || ext === ".txt" || ext === ".docx") {
    return <FileText aria-hidden className="h-4 w-4 text-[var(--primary)]" />;
  }
  if (ext === ".xlsx" || ext === ".csv") {
    return (
      <FileSpreadsheet aria-hidden className="h-4 w-4 text-[var(--success)]" />
    );
  }
  return (
    <FileCode aria-hidden className="h-4 w-4 text-[var(--text-secondary)]" />
  );
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "ready":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-2.5 py-0.5 text-xs font-medium text-[var(--success)]">
          <CheckCircle2 aria-hidden className="h-3 w-3" />
          Ready
        </span>
      );
    case "processing":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-[var(--primary)]">
          <LoaderCircle
            aria-hidden
            className="h-3 w-3 animate-spin motion-reduce:animate-none"
          />
          Processing
        </span>
      );
    case "pending":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-[var(--warning)]">
          <Clock aria-hidden className="h-3 w-3" />
          Pending
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/10 px-2.5 py-0.5 text-xs font-medium text-[var(--danger)]">
          <AlertCircle aria-hidden className="h-3 w-3" />
          Failed
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-500/10 px-2.5 py-0.5 text-xs font-medium text-[var(--text-muted)]">
          {status}
        </span>
      );
  }
}

export function FileListTable({
  files,
  onDeleteFile,
  onReprocessFile,
}: FileListTableProps) {
  const [fileToDelete, setFileToDelete] = useState<StoredFileResponse | null>(
    null,
  );
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  const handleDeleteConfirm = async () => {
    if (!fileToDelete) return;
    setActionLoadingId(fileToDelete.id);
    try {
      await onDeleteFile(fileToDelete.id);
    } finally {
      setActionLoadingId(null);
      setFileToDelete(null);
    }
  };

  const handleReprocess = async (fileId: string) => {
    setActionLoadingId(fileId);
    try {
      await onReprocessFile(fileId);
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <>
      <div className="w-full overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)]">
        <table className="w-full text-left text-sm text-[var(--text)]">
          <thead className="border-b border-[var(--border)] bg-[var(--surface-subtle)] text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            <tr>
              <th scope="col" className="px-4 py-3">
                File Name
              </th>
              <th scope="col" className="px-4 py-3">
                Status
              </th>
              <th scope="col" className="px-4 py-3">
                Size / Details
              </th>
              <th scope="col" className="px-4 py-3">
                Chunks
              </th>
              <th scope="col" className="px-4 py-3">
                Processed Date
              </th>
              <th scope="col" className="px-4 py-3 text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {files.map((file) => {
              const isLoading = actionLoadingId === file.id;
              return (
                <tr
                  key={file.id}
                  className="hover:bg-[var(--surface-subtle)]/50 transition-colors"
                >
                  <td className="px-4 py-3 font-medium">
                    <div className="flex items-center gap-2.5">
                      {getFileIcon(file.extension)}
                      <div className="flex flex-col min-w-0">
                        <span
                          className="truncate max-w-xs font-semibold"
                          title={file.original_name}
                        >
                          {file.original_name}
                        </span>
                        {file.processing_error_code ? (
                          <span
                            className="text-xs text-[var(--danger)]"
                            title={file.processing_error_message || undefined}
                          >
                            Error: {file.processing_error_code}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <StatusBadge status={file.processing_status} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-xs text-[var(--text-secondary)]">
                    <div>{formatBytes(file.file_size_bytes)}</div>
                    {file.page_count ? (
                      <div className="text-[var(--text-muted)]">
                        {file.page_count}{" "}
                        {file.page_count === 1 ? "page" : "pages"}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-xs text-[var(--text-secondary)]">
                    {file.chunk_count}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-xs text-[var(--text-secondary)]">
                    {formatDate(file.processed_at || file.created_at)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right">
                    <div className="flex items-center justify-end gap-2">
                      {file.processing_status === "failed" ? (
                        <Button
                          type="button"
                          onClick={() => handleReprocess(file.id)}
                          disabled={isLoading}
                          aria-label={`Reprocess ${file.original_name}`}
                          className="h-8 min-h-0 px-2.5 text-xs bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
                        >
                          {isLoading ? (
                            <LoaderCircle
                              aria-hidden
                              className="h-3.5 w-3.5 animate-spin"
                            />
                          ) : (
                            <RefreshCw
                              aria-hidden
                              className="h-3.5 w-3.5 mr-1"
                            />
                          )}
                          Reprocess
                        </Button>
                      ) : null}

                      <Button
                        type="button"
                        onClick={() => setFileToDelete(file)}
                        disabled={isLoading}
                        aria-label={`Delete ${file.original_name}`}
                        className="h-8 min-h-0 px-2.5 text-xs bg-transparent text-[var(--danger)] hover:bg-red-500/10 border border-red-500/20"
                      >
                        <Trash2 aria-hidden className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        isOpen={Boolean(fileToDelete)}
        title="Delete File"
        description={`Are you sure you want to delete "${fileToDelete?.original_name}"? Document chunks and storage objects will be removed.`}
        confirmLabel="Delete File"
        isLoading={actionLoadingId === fileToDelete?.id}
        onConfirm={handleDeleteConfirm}
        onClose={() => setFileToDelete(null)}
      />
    </>
  );
}
