"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Edit, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { ConfirmDialog } from "@/components/knowledge/confirm-dialog";
import { KBModal } from "@/components/knowledge/kb-modal";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  updateKnowledgeBase,
} from "@/lib/knowledge-api";
import {
  KnowledgeBaseCreateInput,
  KnowledgeBaseResponse,
  KnowledgeBaseUpdateInput,
} from "@/lib/knowledge-contracts";

interface KBListViewProps {
  onSelectKB: (kbId: string) => void;
}

export function KBListView({ onSelectKB }: KBListViewProps) {
  const [kbs, setKbs] = useState<KnowledgeBaseResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pageSize = 12;

  // Modals
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [kbToEdit, setKbToEdit] = useState<KnowledgeBaseResponse | null>(null);
  const [kbToDelete, setKbToDelete] = useState<KnowledgeBaseResponse | null>(
    null,
  );
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchKBs = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await listKnowledgeBases(page, pageSize);
      setKbs(res.items);
      setTotal(res.total);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load Knowledge Bases",
      );
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    let isMounted = true;
    listKnowledgeBases(page, pageSize)
      .then((res) => {
        if (isMounted) {
          setKbs(res.items);
          setTotal(res.total);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load Knowledge Bases",
          );
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [page, pageSize]);

  const handleCreate = async (
    data: KnowledgeBaseCreateInput | KnowledgeBaseUpdateInput,
  ) => {
    setIsSaving(true);
    try {
      await createKnowledgeBase(data as KnowledgeBaseCreateInput);
      setIsCreateOpen(false);
      await fetchKBs();
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdate = async (data: KnowledgeBaseUpdateInput) => {
    if (!kbToEdit) return;
    setIsSaving(true);
    try {
      await updateKnowledgeBase(kbToEdit.id, data);
      setKbToEdit(null);
      await fetchKBs();
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!kbToDelete) return;
    setIsDeleting(true);
    try {
      await deleteKnowledgeBase(kbToDelete.id);
      setKbToDelete(null);
      await fetchKBs();
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredKbs = kbs.filter(
    (item) =>
      item.name.toLowerCase().includes(search.toLowerCase()) ||
      (item.description &&
        item.description.toLowerCase().includes(search.toLowerCase())),
  );

  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto w-full">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-[var(--border)] pb-5">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text)]">
            Knowledge Bases
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Manage tenant document collections, upload sources, and inspect RAG
            readiness.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          className="h-10 text-sm font-semibold"
        >
          <Plus aria-hidden className="h-4 w-4 mr-1.5" />
          Create Knowledge Base
        </Button>
      </div>

      {/* Toolbar: Search + Refresh */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative w-full max-w-xs">
          <Search
            aria-hidden
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]"
          />
          <Input
            type="search"
            placeholder="Search Knowledge Bases..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 text-xs h-9"
          />
        </div>
        <Button
          type="button"
          onClick={fetchKBs}
          className="bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)] text-xs h-9 px-3"
          title="Refresh List"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Main Content State */}
      {isLoading ? (
        <LoadingState label="Loading Knowledge Bases..." />
      ) : error ? (
        <ErrorState title="Failed to Load Knowledge Bases" message={error} />
      ) : filteredKbs.length === 0 ? (
        <EmptyState
          title={
            search ? "No Matching Knowledge Bases" : "No Knowledge Bases Found"
          }
          message={
            search
              ? `No Knowledge Bases found matching "${search}".`
              : "Create your first Knowledge Base to begin uploading organizational documents for grounded AI chat."
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredKbs.map((kb) => (
            <div
              key={kb.id}
              className="flex flex-col justify-between rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 transition-shadow hover:shadow-md"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--nav-selected)] text-[var(--primary)]">
                      <BookOpen aria-hidden className="h-5 w-5" />
                    </div>
                    <div>
                      <h2
                        className="font-semibold text-base text-[var(--text)] cursor-pointer hover:text-[var(--primary)] transition-colors"
                        onClick={() => onSelectKB(kb.id)}
                      >
                        {kb.name}
                      </h2>
                      <span className="text-xs text-[var(--text-muted)] font-mono">
                        {kb.embedding_dimension}D{" "}
                        {kb.embedding_model.split("/").pop()}
                      </span>
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      kb.status === "active"
                        ? "bg-green-500/10 text-[var(--success)]"
                        : "bg-gray-500/10 text-[var(--text-muted)]"
                    }`}
                  >
                    {kb.status}
                  </span>
                </div>

                <p className="mt-3 text-xs text-[var(--text-secondary)] line-clamp-3 leading-relaxed">
                  {kb.description || "No description provided."}
                </p>
              </div>

              <div className="mt-5 pt-4 border-t border-[var(--border)] flex items-center justify-between">
                <span className="text-[11px] text-[var(--text-muted)]">
                  Created {new Date(kb.created_at).toLocaleDateString()}
                </span>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setKbToEdit(kb)}
                    aria-label={`Edit ${kb.name}`}
                    className="p-1.5 rounded-md text-[var(--text-muted)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text)] transition-colors"
                  >
                    <Edit aria-hidden className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setKbToDelete(kb)}
                    aria-label={`Delete ${kb.name}`}
                    className="p-1.5 rounded-md text-[var(--danger)] hover:bg-red-500/10 transition-colors"
                  >
                    <Trash2 aria-hidden className="h-4 w-4" />
                  </button>
                  <Button
                    type="button"
                    onClick={() => onSelectKB(kb.id)}
                    className="h-8 min-h-0 text-xs px-3 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
                  >
                    View Files
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > pageSize ? (
        <div className="flex items-center justify-between border-t border-[var(--border)] pt-4 text-xs text-[var(--text-secondary)]">
          <span>
            Showing {(page - 1) * pageSize + 1} to{" "}
            {Math.min(page * pageSize, total)} of {total} Knowledge Bases
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
              disabled={page * pageSize >= total}
              onClick={() => setPage((p) => p + 1)}
              className="h-8 px-3 text-xs bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)] disabled:opacity-50"
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}

      {/* Modals */}
      <KBModal
        isOpen={isCreateOpen}
        isLoading={isSaving}
        onSubmit={handleCreate}
        onClose={() => setIsCreateOpen(false)}
      />

      <KBModal
        isOpen={Boolean(kbToEdit)}
        kbToEdit={kbToEdit}
        isLoading={isSaving}
        onSubmit={handleUpdate}
        onClose={() => setKbToEdit(null)}
      />

      <ConfirmDialog
        isOpen={Boolean(kbToDelete)}
        title="Delete Knowledge Base"
        description={`Are you sure you want to delete "${kbToDelete?.name}"? All document files and embeddings in this Knowledge Base will be permanently removed.`}
        confirmLabel="Delete Knowledge Base"
        isLoading={isDeleting}
        onConfirm={handleDeleteConfirm}
        onClose={() => setKbToDelete(null)}
      />
    </div>
  );
}
