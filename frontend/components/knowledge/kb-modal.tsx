"use client";

import { useEffect, useState } from "react";
import { LoaderCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  KnowledgeBaseCreateInput,
  KnowledgeBaseResponse,
  KnowledgeBaseUpdateInput,
} from "@/lib/knowledge-contracts";

interface KBModalProps {
  isOpen: boolean;
  kbToEdit?: KnowledgeBaseResponse | null;
  isLoading?: boolean;
  onSubmit: (
    data: KnowledgeBaseCreateInput | KnowledgeBaseUpdateInput,
  ) => Promise<void>;
  onClose: () => void;
}

export function KBModal({
  isOpen,
  kbToEdit,
  isLoading = false,
  onSubmit,
  onClose,
}: KBModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<"active" | "inactive">("active");
  const [error, setError] = useState<string | null>(null);

  const isEditing = Boolean(kbToEdit);

  const [prevKb, setPrevKb] = useState<
    KnowledgeBaseResponse | null | undefined
  >(undefined);
  if (kbToEdit !== prevKb) {
    setPrevKb(kbToEdit);
    setName(kbToEdit?.name || "");
    setDescription(kbToEdit?.description || "");
    setStatus(kbToEdit?.status === "inactive" ? "inactive" : "active");
    setError(null);
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isLoading) {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, isLoading, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setError(null);
    try {
      if (isEditing) {
        await onSubmit({
          name: name.trim(),
          description: description.trim() || null,
          status,
        });
      } else {
        await onSubmit({
          name: name.trim(),
          description: description.trim() || null,
        });
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  };

  return (
    <div
      aria-modal="true"
      role="dialog"
      aria-labelledby="kb-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isLoading) onClose();
      }}
    >
      <div className="w-full max-w-lg rounded-lg border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-6 shadow-lg">
        <div className="flex items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
          <h3
            id="kb-modal-title"
            className="text-lg font-semibold text-[var(--text)]"
          >
            {isEditing ? "Edit Knowledge Base" : "Create Knowledge Base"}
          </h3>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            aria-label="Close modal"
            className="rounded-md p-1 text-[var(--text-muted)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text)] disabled:opacity-50"
          >
            <X aria-hidden className="h-5 w-5" />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="mt-4 flex flex-col gap-4"
        >
          {error ? (
            <div
              role="alert"
              className="rounded-md bg-red-500/10 p-3 text-sm font-medium text-[var(--danger)]"
            >
              {error}
            </div>
          ) : null}

          <div>
            <label
              htmlFor="kb-name"
              className="block text-sm font-medium text-[var(--text)] mb-1"
            >
              Knowledge Base Name{" "}
              <span className="text-[var(--danger)]">*</span>
            </label>
            <Input
              id="kb-name"
              type="text"
              required
              maxLength={200}
              placeholder="e.g. Financial Reports 2025"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div>
            <label
              htmlFor="kb-description"
              className="block text-sm font-medium text-[var(--text)] mb-1"
            >
              Description{" "}
              <span className="text-xs text-[var(--text-muted)]">
                (optional)
              </span>
            </label>
            <textarea
              id="kb-description"
              rows={3}
              maxLength={2000}
              placeholder="Describe the purpose or contents of this knowledge base..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isLoading}
              className="w-full rounded-md border border-[var(--border-strong)] bg-[var(--surface)] p-2.5 text-sm text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-hidden focus:ring-2 focus:ring-[var(--focus)] disabled:opacity-50"
            />
          </div>

          {isEditing ? (
            <div>
              <label
                htmlFor="kb-status"
                className="block text-sm font-medium text-[var(--text)] mb-1"
              >
                Status
              </label>
              <select
                id="kb-status"
                value={status}
                onChange={(e) =>
                  setStatus(e.target.value as "active" | "inactive")
                }
                disabled={isLoading}
                className="w-full rounded-md border border-[var(--border-strong)] bg-[var(--surface)] p-2.5 text-sm text-[var(--text)] focus:outline-hidden focus:ring-2 focus:ring-[var(--focus)] disabled:opacity-50"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          ) : null}

          <div className="mt-4 flex items-center justify-end gap-3 border-t border-[var(--border)] pt-4">
            <Button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="bg-transparent border border-[var(--border-strong)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? (
                <>
                  <LoaderCircle
                    aria-hidden
                    className="h-4 w-4 animate-spin motion-reduce:animate-none"
                  />
                  Saving...
                </>
              ) : isEditing ? (
                "Save Changes"
              ) : (
                "Create Knowledge Base"
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
