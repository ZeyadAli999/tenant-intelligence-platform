"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Edit,
  Filter,
  LoaderCircle,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { FileListTable } from "@/components/knowledge/file-list-table";
import { FileUploadDropzone } from "@/components/knowledge/file-upload-dropzone";
import { KBModal } from "@/components/knowledge/kb-modal";
import {
  deleteFile,
  deleteKnowledgeBase,
  getKnowledgeBase,
  listFiles,
  reprocessFile,
  updateKnowledgeBase,
  uploadFileToKnowledgeBase,
} from "@/lib/knowledge-api";
import {
  KnowledgeBaseResponse,
  KnowledgeBaseUpdateInput,
  StoredFileResponse,
} from "@/lib/knowledge-contracts";

interface KBDetailViewProps {
  kbId: string;
  onBack: () => void;
}

export function KBDetailView({ kbId, onBack }: KBDetailViewProps) {
  const [kb, setKb] = useState<KnowledgeBaseResponse | null>(null);
  const [files, setFiles] = useState<StoredFileResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [extFilter, setExtFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [totalFiles, setTotalFiles] = useState(0);
  const pageSize = 20;

  // Modals
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteKBConfirmOpen, setIsDeleteKBConfirmOpen] = useState(false);
  const [isDeletingKB, setIsDeletingKB] = useState(false);
  const [isSavingKB, setIsSavingKB] = useState(false);

  // Polling ref to track active interval
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchKB = useCallback(async () => {
    try {
      const data = await getKnowledgeBase(kbId);
      setKb(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load Knowledge Base",
      );
    }
  }, [kbId]);

  const fetchFiles = useCallback(
    async (showLoading = false) => {
      if (showLoading) setIsLoading(true);
      try {
        const res = await listFiles({
          knowledge_base_id: kbId,
          processing_status: statusFilter === "all" ? undefined : statusFilter,
          extension: extFilter === "all" ? undefined : extFilter,
          page,
          page_size: pageSize,
        });
        setFiles(res.items);
        setTotalFiles(res.total);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load files");
      } finally {
        if (showLoading) setIsLoading(false);
      }
    },
    [kbId, statusFilter, extFilter, page, pageSize],
  );

  // Initial load
  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      setIsLoading(true);
      await Promise.all([fetchKB(), fetchFiles(false)]);
      if (isMounted) setIsLoading(false);
    };
    loadData();
    return () => {
      isMounted = false;
    };
  }, [fetchKB, fetchFiles]);

  // Controlled Polling: Check if any file is pending or processing
  const hasProcessingFiles = files.some(
    (f) =>
      f.processing_status === "pending" || f.processing_status === "processing",
  );

  useEffect(() => {
    if (hasProcessingFiles) {
      pollIntervalRef.current = setInterval(() => {
        fetchFiles(false);
      }, 2000);
    } else if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [hasProcessingFiles, fetchFiles]);

  const handleUploadFile = async (file: File) => {
    await uploadFileToKnowledgeBase(kbId, file);
    await fetchFiles(false);
  };

  const handleDeleteFile = async (fileId: string) => {
    await deleteFile(fileId);
    await fetchFiles(false);
  };

  const handleReprocessFile = async (fileId: string) => {
    await reprocessFile(fileId);
    await fetchFiles(false);
  };

  const handleUpdateKB = async (data: KnowledgeBaseUpdateInput) => {
    setIsSavingKB(true);
    try {
      const updated = await updateKnowledgeBase(kbId, data);
      setKb(updated);
      setIsEditModalOpen(false);
    } finally {
      setIsSavingKB(false);
    }
  };

  const handleDeleteKB = async () => {
    setIsDeletingKB(true);
    try {
      await deleteKnowledgeBase(kbId);
      onBack();
    } finally {
      setIsDeletingKB(false);
    }
  };

  if (isLoading && !kb) {
    return <LoadingState label="Loading Knowledge Base..." />;
  }

  if (error && !kb) {
    return (
      <div className="p-6">
        <Button
          type="button"
          onClick={onBack}
          className="mb-4 bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
        >
          <ArrowLeft aria-hidden className="h-4 w-4 mr-2" />
          Back to Knowledge Bases
        </Button>
        <ErrorState title="Knowledge Base Not Found" message={error} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto w-full">
      {/* Navigation & Actions Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-[var(--border)] pb-5">
        <div className="flex items-center gap-3">
          <Button
            type="button"
            onClick={onBack}
            aria-label="Back to Knowledge Bases"
            className="bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)] px-3"
          >
            <ArrowLeft aria-hidden className="h-4 w-4 mr-1" />
            Back
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-[var(--text)]">
                {kb?.name}
              </h1>
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  kb?.status === "active"
                    ? "bg-green-500/10 text-[var(--success)]"
                    : "bg-gray-500/10 text-[var(--text-muted)]"
                }`}
              >
                {kb?.status}
              </span>
            </div>
            <p className="mt-1 text-sm text-[var(--text-secondary)] max-w-2xl">
              {kb?.description || "No description provided."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            onClick={() => setIsEditModalOpen(true)}
            className="bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)] text-xs h-9"
          >
            <Edit aria-hidden className="h-3.5 w-3.5 mr-1.5" />
            Edit KB
          </Button>
          <Button
            type="button"
            onClick={() => setIsDeleteKBConfirmOpen(true)}
            className="bg-transparent border border-red-500/20 text-[var(--danger)] hover:bg-red-500/10 text-xs h-9"
          >
            <Trash2 aria-hidden className="h-3.5 w-3.5 mr-1.5" />
            Delete KB
          </Button>
        </div>
      </div>

      {/* Metadata Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 text-xs text-[var(--text-secondary)]">
        <div>
          <span className="block font-semibold text-[var(--text-muted)]">
            Embedding Model
          </span>
          <span className="font-mono text-[var(--text)]">
            {kb?.embedding_model}
          </span>
        </div>
        <div>
          <span className="block font-semibold text-[var(--text-muted)]">
            Vector Dimension
          </span>
          <span className="font-mono text-[var(--text)]">
            {kb?.embedding_dimension} dims
          </span>
        </div>
        <div>
          <span className="block font-semibold text-[var(--text-muted)]">
            Total Documents
          </span>
          <span className="font-semibold text-[var(--text)]">
            {totalFiles} files
          </span>
        </div>
        <div>
          <span className="block font-semibold text-[var(--text-muted)]">
            Created Date
          </span>
          <span className="text-[var(--text)]">
            {kb?.created_at
              ? new Date(kb.created_at).toLocaleDateString()
              : "—"}
          </span>
        </div>
      </div>

      {/* Upload Section */}
      <div className="flex flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <h2 className="text-sm font-semibold text-[var(--text)]">
          Upload Documents
        </h2>
        <FileUploadDropzone onUpload={handleUploadFile} />
      </div>

      {/* File List Section */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-[var(--text)]">
              Document Files ({totalFiles})
            </h2>
            {hasProcessingFiles ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--primary)] font-medium">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                Processing active...
              </span>
            ) : null}
          </div>

          {/* Filter Bar */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
              <Filter className="h-3.5 w-3.5" />
              Filter:
            </div>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-md border border-[var(--border-strong)] bg-[var(--surface)] px-2.5 py-1 text-xs text-[var(--text)]"
            >
              <option value="all">All Statuses</option>
              <option value="ready">Ready</option>
              <option value="processing">Processing</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
            </select>
            <select
              value={extFilter}
              onChange={(e) => {
                setExtFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-md border border-[var(--border-strong)] bg-[var(--surface)] px-2.5 py-1 text-xs text-[var(--text)]"
            >
              <option value="all">All Types</option>
              <option value=".pdf">PDF</option>
              <option value=".docx">DOCX</option>
              <option value=".xlsx">XLSX</option>
              <option value=".csv">CSV</option>
              <option value=".txt">TXT</option>
            </select>
            <Button
              type="button"
              onClick={() => fetchFiles(true)}
              className="bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)] text-xs h-7 px-2"
              title="Refresh file list"
            >
              <RefreshCw className="h-3 w-3" />
            </Button>
          </div>
        </div>

        {/* Files Content */}
        {isLoading ? (
          <LoadingState label="Loading file list..." />
        ) : files.length === 0 ? (
          <EmptyState
            title="No Documents Uploaded"
            message={
              statusFilter !== "all" || extFilter !== "all"
                ? "No files match the selected filter criteria."
                : "Upload documents above to begin grounded document search and hybrid retrieval."
            }
          />
        ) : (
          <FileListTable
            files={files}
            onDeleteFile={handleDeleteFile}
            onReprocessFile={handleReprocessFile}
          />
        )}

        {/* Pagination */}
        {totalFiles > pageSize ? (
          <div className="flex items-center justify-between border-t border-[var(--border)] pt-4 text-xs text-[var(--text-secondary)]">
            <span>
              Showing {(page - 1) * pageSize + 1} to{" "}
              {Math.min(page * pageSize, totalFiles)} of {totalFiles} files
            </span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="h-8 px-3 text-xs bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)] disabled:opacity-50"
              >
                Previous
              </Button>
              <Button
                type="button"
                disabled={page * pageSize >= totalFiles}
                onClick={() => setPage((p) => p + 1)}
                className="h-8 px-3 text-xs bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)] disabled:opacity-50"
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      {/* Modals */}
      <KBModal
        isOpen={isEditModalOpen}
        kbToEdit={kb}
        isLoading={isSavingKB}
        onSubmit={handleUpdateKB}
        onClose={() => setIsEditModalOpen(false)}
      />

      <ConfirmDialog
        isOpen={isDeleteKBConfirmOpen}
        title="Delete Knowledge Base"
        description={`Are you sure you want to delete "${kb?.name}"? All associated files, vector embeddings, and citations will be permanently removed.`}
        confirmLabel="Delete Knowledge Base"
        isLoading={isDeletingKB}
        onConfirm={handleDeleteKB}
        onClose={() => setIsDeleteKBConfirmOpen(false)}
      />
    </div>
  );
}
