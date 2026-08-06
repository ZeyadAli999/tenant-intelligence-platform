"use client";

import {
  BookOpen,
  Copy,
  Database,
  Menu,
  MessageSquarePlus,
  PanelRight,
  Search,
  Send,
  Square,
  Trash2,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import {
  citationListSchema,
  conversationDetailSchema,
  conversationListSchema,
  databaseListSchema,
  knowledgeBaseListSchema,
  sourceMode,
  sqlResponseSchema,
  validateSourceSelection,
  type ChatResponse,
  type Citation,
  type Conversation,
  type ConversationDetail,
  type DatabaseSource,
  type KnowledgeSource,
  type Message,
  type SQLDetail,
} from "@/lib/chat-contracts";
import {
  initialStreamState,
  SSEParser,
  streamReducer,
  type ChatEvent,
} from "@/lib/sse";

const API = "/api/backend";
async function api<T>(
  path: string,
  schema: { parse(value: unknown): T },
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: init?.body ? { "content-type": "application/json" } : undefined,
  });
  if (response.status === 401) {
    window.dispatchEvent(new Event("session-expired"));
    throw new Error("SESSION_EXPIRED");
  }
  if (!response.ok) {
    const value = (await response.json().catch(() => ({}))) as {
      message?: string;
    };
    throw new Error(value.message || "The request could not be completed.");
  }
  return schema.parse(await response.json());
}

function timeLabel(value: string | null) {
  if (!value) return "No messages yet";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function sourceNames(
  conversation: Conversation,
  databases: DatabaseSource[],
  knowledge: KnowledgeSource[],
) {
  const map = new Map(
    [...databases, ...knowledge].map((item) => [item.id, item.name]),
  );
  return [
    ...conversation.database_connection_ids,
    ...conversation.knowledge_base_ids,
  ].map((id) => map.get(id) ?? "Unavailable source");
}

function ConversationRail({
  items,
  active,
  loading,
  onSelect,
  onNew,
  onDelete,
  close,
}: {
  items: Conversation[];
  active: string | null;
  loading: boolean;
  onSelect(id: string): void;
  onNew(): void;
  onDelete(item: Conversation): void;
  close?(): void;
}) {
  const [query, setQuery] = useState("");
  const shown = items.filter((item) =>
    (item.title || "Untitled conversation")
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <aside
      aria-label="Conversations"
      className="flex h-full min-h-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar)]"
    >
      <div className="border-b border-[var(--border)] p-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Conversations</h2>
          {close && (
            <button
              aria-label="Close conversations"
              onClick={close}
              className="icon-button"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <button onClick={onNew} className="primary-button w-full">
          <MessageSquarePlus className="h-4 w-4" />
          New conversation
        </button>
        <label className="mt-3 flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 focus-within:border-[var(--primary)]">
          <Search aria-hidden className="h-4 w-4 text-[var(--text-muted)]" />
          <span className="sr-only">Filter conversations</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter loaded conversations"
            className="h-9 min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
        </label>
      </div>
      <div
        className="min-h-0 flex-1 overflow-y-auto p-2"
        role={shown.length ? "list" : undefined}
      >
        {loading && (
          <p className="p-4 text-sm text-[var(--text-muted)]">
            Loading conversations…
          </p>
        )}
        {!loading && !shown.length && (
          <div className="p-4 text-sm text-[var(--text-muted)]">
            <p className="font-medium text-[var(--text-secondary)]">
              No conversations
            </p>
            <p className="mt-1">Create one to begin a governed question.</p>
          </div>
        )}
        {shown.map((item) => (
          <div
            key={item.id}
            role="listitem"
            className={`group mb-1 flex rounded-md ${active === item.id ? "bg-[var(--nav-selected)]" : "hover:bg-[var(--surface-subtle)]"}`}
          >
            <button
              onClick={() => onSelect(item.id)}
              className="min-w-0 flex-1 px-3 py-2.5 text-left"
            >
              <span className="block truncate text-sm font-medium">
                {item.title || "Untitled conversation"}
              </span>
              <span className="mt-1 flex items-center justify-between gap-2 text-[11px] text-[var(--text-muted)]">
                <span>
                  {sourceMode(
                    item.database_connection_ids,
                    item.knowledge_base_ids,
                  )}
                </span>
                <span>
                  {timeLabel(item.last_message_at || item.updated_at)}
                </span>
              </span>
            </button>
            <button
              aria-label={`Delete ${item.title || "Untitled conversation"}`}
              onClick={() => onDelete(item)}
              className="m-1.5 self-center rounded p-2 text-[var(--text-muted)] opacity-60 hover:bg-[var(--surface)] hover:text-[var(--danger)] group-hover:opacity-100"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}

function NewConversationDialog({
  databases,
  knowledge,
  onClose,
  onCreated,
}: {
  databases: DatabaseSource[];
  knowledge: KnowledgeSource[];
  onClose(): void;
  onCreated(item: Conversation): void;
}) {
  const [title, setTitle] = useState("");
  const [databaseIds, setDatabaseIds] = useState<string[]>([]);
  const [knowledgeIds, setKnowledgeIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    titleRef.current?.focus();
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  const validation = validateSourceSelection(databaseIds, knowledgeIds);
  async function create() {
    if (validation || busy) return;
    setBusy(true);
    setError(null);
    try {
      const item = await api(
        "/conversations",
        {
          parse: (v) =>
            conversationDetailSchema
              .omit({
                messages: true,
                message_total: true,
                message_page: true,
                message_page_size: true,
              })
              .parse(v),
        },
        {
          method: "POST",
          body: JSON.stringify({
            title: title.trim() || null,
            database_connection_ids: databaseIds,
            knowledge_base_ids: knowledgeIds,
          }),
        },
      );
      onCreated(item);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Conversation creation failed.",
      );
      setBusy(false);
    }
  }
  function trapFocus(event: React.KeyboardEvent) {
    if (event.key !== "Tab") return;
    const controls = dialogRef.current?.querySelectorAll<HTMLElement>(
      "button:not(:disabled), input:not(:disabled)",
    );
    if (!controls?.length) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section
        ref={dialogRef}
        onKeyDown={trapFocus}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-title"
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-lg border border-[var(--border-strong)] bg-[var(--surface-elevated)] shadow-xl"
      >
        <header className="flex items-start justify-between border-b border-[var(--border)] p-5">
          <div>
            <h2 id="new-title" className="font-semibold">
              New conversation
            </h2>
            <p className="mt-1 text-sm text-[var(--text-muted)]">
              Sources are fixed after creation.
            </p>
          </div>
          <button
            aria-label="Close dialog"
            onClick={onClose}
            className="icon-button"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="space-y-5 p-5">
          <label className="block text-sm font-medium">
            Title{" "}
            <span className="font-normal text-[var(--text-muted)]">
              (optional)
            </span>
            <input
              ref={titleRef}
              value={title}
              maxLength={255}
              onChange={(e) => setTitle(e.target.value)}
              className="field mt-2"
              placeholder="Quarterly customer review"
            />
          </label>
          <fieldset>
            <legend className="text-sm font-medium">
              Database{" "}
              <span className="font-normal text-[var(--text-muted)]">
                — select up to one
              </span>
            </legend>
            <div className="mt-2 space-y-2">
              {!databases.length && (
                <p className="empty-inline">
                  No database sources are available. Database management will be
                  available in a future workspace.
                </p>
              )}
              {databases.map((item) => {
                const available = item.is_active && item.status === "connected";
                return (
                  <label
                    key={item.id}
                    className={`source-option ${!available ? "opacity-55" : ""}`}
                  >
                    <input
                      type="radio"
                      name="database"
                      disabled={!available}
                      checked={databaseIds[0] === item.id}
                      onChange={() =>
                        setDatabaseIds(
                          databaseIds[0] === item.id ? [] : [item.id],
                        )
                      }
                    />
                    <Database className="h-4 w-4" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {item.name}
                      </span>
                      <span className="text-xs text-[var(--text-muted)]">
                        {available ? item.database_type : "Unavailable"}
                      </span>
                    </span>
                  </label>
                );
              })}
              {databaseIds.length > 0 && (
                <button
                  className="text-button"
                  onClick={() => setDatabaseIds([])}
                >
                  Clear database
                </button>
              )}
            </div>
          </fieldset>
          <fieldset>
            <legend className="text-sm font-medium">
              Knowledge bases{" "}
              <span className="font-normal text-[var(--text-muted)]">
                — up to ten
              </span>
            </legend>
            <div className="mt-2 max-h-48 space-y-2 overflow-y-auto">
              {!knowledge.length && (
                <p className="empty-inline">
                  No knowledge bases are available. Knowledge management will be
                  available in a future workspace.
                </p>
              )}
              {knowledge.map((item) => {
                const available = item.status === "active";
                return (
                  <label
                    key={item.id}
                    className={`source-option ${!available ? "opacity-55" : ""}`}
                  >
                    <input
                      type="checkbox"
                      disabled={!available}
                      checked={knowledgeIds.includes(item.id)}
                      onChange={(e) =>
                        setKnowledgeIds(
                          e.target.checked
                            ? [...knowledgeIds, item.id]
                            : knowledgeIds.filter((id) => id !== item.id),
                        )
                      }
                    />
                    <BookOpen className="h-4 w-4" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {item.name}
                      </span>
                      <span className="text-xs text-[var(--text-muted)]">
                        {available ? "Available" : "Unavailable"}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
          <div className="rounded-md bg-[var(--surface-subtle)] p-3 text-sm">
            <span className="font-medium">
              {sourceMode(databaseIds, knowledgeIds)}
            </span>
            <span className="text-[var(--text-muted)]">
              {" "}
              · {databaseIds.length + knowledgeIds.length} selected
            </span>
          </div>
          {(validation || error) && (
            <p role="alert" className="text-sm text-[var(--danger)]">
              {validation || error}
            </p>
          )}
        </div>
        <footer className="flex justify-end gap-2 border-t border-[var(--border)] p-4">
          <button onClick={onClose} className="secondary-button">
            Cancel
          </button>
          <button
            disabled={busy || !!validation}
            onClick={create}
            className="primary-button"
          >
            {busy ? "Creating…" : "Create conversation"}
          </button>
        </footer>
      </section>
    </div>
  );
}

function MessageHistory({
  detail,
  stream,
  optimistic,
  onInspect,
}: {
  detail: ConversationDetail | null;
  stream: typeof initialStreamState;
  optimistic: string | null;
  onInspect(message: Message): void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "nearest" });
  }, [stream.answer, detail?.messages.length]);
  const messages = detail?.messages ?? [];
  if (!messages.length && !optimistic)
    return (
      <div className="flex flex-1 items-center justify-center p-8 text-center">
        <div>
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface-subtle)]">
            <MessageSquarePlus className="h-5 w-5" />
          </div>
          <h3 className="font-medium">Start this conversation</h3>
          <p className="mt-1 max-w-md text-sm text-[var(--text-muted)]">
            Ask a question grounded in the sources selected for this
            conversation.
          </p>
        </div>
      </div>
    );
  return (
    <div
      className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7"
      aria-label="Message history"
    >
      <div className="mx-auto max-w-3xl space-y-6">
        {messages.map((message) => (
          <article
            key={message.id}
            className={
              message.role === "user"
                ? "ml-auto max-w-[85%] rounded-lg bg-[var(--surface-subtle)] px-4 py-3"
                : "max-w-full"
            }
          >
            <header className="mb-1.5 flex items-center gap-2 text-xs font-semibold text-[var(--text-secondary)]">
              <span>{message.role === "user" ? "You" : "Assistant"}</span>
              <span className="font-normal text-[var(--text-muted)]">
                {timeLabel(message.created_at)}
              </span>
              {message.detected_intent && (
                <span className="font-normal">· {message.detected_intent}</span>
              )}
            </header>
            <p className="whitespace-pre-wrap break-words text-sm leading-6">
              {message.content}
            </p>
            {message.role === "assistant" && message.status !== "pending" && (
              <button
                onClick={() => onInspect(message)}
                className="text-button mt-2"
              >
                Inspect response details
              </button>
            )}
            {message.status !== "completed" && (
              <p className="mt-2 text-xs text-[var(--text-muted)]">
                Status: {message.status}
              </p>
            )}
          </article>
        ))}
        {optimistic && (
          <article className="ml-auto max-w-[85%] rounded-lg bg-[var(--surface-subtle)] px-4 py-3">
            <header className="mb-1 text-xs font-semibold">You</header>
            <p className="whitespace-pre-wrap break-words text-sm">
              {optimistic}
            </p>
          </article>
        )}
        {stream.phase !== "idle" && stream.phase !== "completed" && (
          <article aria-label="Streaming assistant response">
            <header className="mb-2 text-xs font-semibold">Assistant</header>
            <p className="whitespace-pre-wrap break-words text-sm leading-6">
              {stream.answer || "Working with the approved sources…"}
            </p>
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              {stream.status}
            </p>
          </article>
        )}
        <div ref={end} />
      </div>
    </div>
  );
}

type Tab = "overview" | "sql" | "citations";
function Inspector({
  tab,
  setTab,
  response,
  sql,
  citations,
  close,
}: {
  tab: Tab;
  setTab(v: Tab): void;
  response?: ChatResponse;
  sql?: SQLDetail;
  citations: Citation[];
  close?(): void;
}) {
  const tabs: Tab[] = ["overview", "sql", "citations"];
  return (
    <aside
      aria-label="Response details"
      className="flex h-full min-h-0 flex-col bg-[var(--surface)]"
    >
      <header className="flex items-center justify-between border-b border-[var(--border)] p-3">
        <h2 className="text-sm font-semibold">Response details</h2>
        {close && (
          <button
            aria-label="Close response details"
            onClick={close}
            className="icon-button"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </header>
      <div
        role="tablist"
        aria-label="Response details"
        className="flex border-b border-[var(--border)] px-2"
      >
        {tabs.map((item) => (
          <button
            key={item}
            role="tab"
            aria-selected={tab === item}
            onClick={() => setTab(item)}
            className={`px-3 py-2.5 text-xs font-medium capitalize ${tab === item ? "border-b-2 border-[var(--primary)] text-[var(--text)]" : "text-[var(--text-muted)]"}`}
          >
            {item}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4" role="tabpanel">
        {tab === "overview" &&
          (!response ? (
            <InspectorEmpty text="Complete a response to see its details." />
          ) : (
            <dl className="detail-list">
              <DT label="Intent" value={response.intent} />
              <DT
                label="Sources used"
                value={response.sources_used.join(", ") || "None"}
              />
              <DT label="Answer status" value="Completed" />
              <DT
                label="Prompt tokens"
                value={String(response.usage.prompt_tokens)}
              />
              <DT
                label="Completion tokens"
                value={String(response.usage.completion_tokens)}
              />
              <DT
                label="Provider latency"
                value={`${response.usage.provider_latency_ms} ms`}
              />
              {response.sql && (
                <>
                  <DT
                    label="Rows returned"
                    value={String(response.sql.row_count)}
                  />
                  <DT
                    label="Result truncated"
                    value={response.sql.truncated ? "Yes" : "No"}
                  />
                </>
              )}
              {response.warnings.length > 0 && (
                <div>
                  <dt>Warnings</dt>
                  <dd>
                    <ul className="list-disc pl-4">
                      {response.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </dd>
                </div>
              )}
              <details className="pt-2 text-xs">
                <summary>Technical details</summary>
                <p className="mt-2 break-all text-[var(--text-muted)]">
                  Message ID: {response.message_id}
                </p>
              </details>
            </dl>
          ))}
        {tab === "sql" &&
          (!sql && !response?.sql ? (
            <InspectorEmpty text="No SQL is associated with this response." />
          ) : (
            <SQLPanel
              value={
                sql ?? {
                  message_id: response!.message_id,
                  query_execution_id: response!.sql!.query_execution_id,
                  normalized_sql: response!.sql!.normalized_sql,
                  execution_status: "completed",
                  row_count: response!.sql!.row_count,
                  truncated: response!.sql!.truncated,
                  referenced_tables: response!.citations
                    .filter((c) => c.type === "database")
                    .map((c) => c.table),
                }
              }
            />
          ))}
        {tab === "citations" && (
          <CitationPanel
            citations={
              citations.length ? citations : (response?.citations ?? [])
            }
            setTab={setTab}
          />
        )}
      </div>
    </aside>
  );
}
function InspectorEmpty({ text }: { text: string }) {
  return (
    <p className="rounded-md bg-[var(--surface-subtle)] p-4 text-sm text-[var(--text-muted)]">
      {text}
    </p>
  );
}
function DT({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className="capitalize">{value}</dd>
    </div>
  );
}
function SQLPanel({ value }: { value: SQLDetail }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(value.normalized_sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--success)]">
          Validated SQL
        </span>
        <button onClick={copy} className="secondary-button px-2 py-1 text-xs">
          <Copy className="h-3.5 w-3.5" />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        aria-label="Validated SQL"
        className="max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-[var(--code-surface)] p-3 text-xs leading-5"
      >
        <code>{value.normalized_sql}</code>
      </pre>
      <dl className="detail-list">
        <DT
          label="Execution status"
          value={value.execution_status || "Available"}
        />
        <DT
          label="Rows returned"
          value={String(value.row_count ?? "Unknown")}
        />
        <DT label="Result truncated" value={value.truncated ? "Yes" : "No"} />
        <DT
          label="Referenced tables"
          value={value.referenced_tables.join(", ") || "Not provided"}
        />
      </dl>
      <p className="text-xs text-[var(--text-muted)]">
        The platform enforces read-only validation before query execution.
      </p>
    </div>
  );
}
function CitationPanel({
  citations,
  setTab,
}: {
  citations: Citation[];
  setTab(v: Tab): void;
}) {
  if (!citations.length)
    return (
      <InspectorEmpty text="No citations are associated with this response." />
    );
  return (
    <div className="space-y-4">
      {(["database", "document"] as const).map((type) => {
        const rows = citations.filter((c) => c.type === type);
        if (!rows.length) return null;
        return (
          <section key={type}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              {type}
            </h3>
            <ol className="space-y-2">
              {rows.map((citation, index) => (
                <li
                  key={`${type}-${index}`}
                  className="rounded-md border border-[var(--border)] p-3 text-sm"
                >
                  <span className="mr-2 font-semibold">[{index + 1}]</span>
                  {citation.type === "database" ? (
                    <>
                      <span>{citation.table}</span>
                      {citation.columns.length > 0 && (
                        <p className="mt-1 text-xs text-[var(--text-muted)]">
                          Columns: {citation.columns.join(", ")}
                        </p>
                      )}
                      <button
                        onClick={() => setTab("sql")}
                        className="text-button mt-2"
                      >
                        View SQL
                      </button>
                    </>
                  ) : (
                    <>
                      <span>{citation.file_name}</span>
                      <p className="mt-1 text-xs text-[var(--text-muted)]">
                        {[
                          citation.page_number &&
                            `Page ${citation.page_number}`,
                          citation.section_title,
                          citation.sheet_name && `Sheet ${citation.sheet_name}`,
                          citation.row_start &&
                            `Rows ${citation.row_start}${citation.row_end ? `–${citation.row_end}` : ""}`,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "Document reference"}
                      </p>
                      {citation.relevance_score != null && (
                        <p className="mt-1 text-xs text-[var(--text-muted)]">
                          Relevance: {citation.relevance_score.toFixed(3)}
                        </p>
                      )}
                    </>
                  )}
                </li>
              ))}
            </ol>
          </section>
        );
      })}
    </div>
  );
}

export function ChatWorkspace({
  initialConversationId = null,
}: {
  initialConversationId?: string | null;
}) {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(
    initialConversationId,
  );
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [databases, setDatabases] = useState<DatabaseSource[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [newOpen, setNewOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [deleting, setDeleting] = useState<Conversation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [optimistic, setOptimistic] = useState<string | null>(null);
  const [stream, dispatch] = useReducer(streamReducer, initialStreamState);
  const abort = useRef<AbortController | null>(null);
  const [response, setResponse] = useState<ChatResponse>();
  const [sql, setSQL] = useState<SQLDetail>();
  const [citations, setCitations] = useState<Citation[]>([]);
  const [tab, setTab] = useState<Tab>("overview");
  const composer = useRef<HTMLTextAreaElement>(null);

  const loadList = useCallback(async () => {
    const value = await api(
      "/conversations?page=1&page_size=100",
      conversationListSchema,
    );
    setConversations(value.items);
    setActiveId((id) => id ?? value.items[0]?.id ?? null);
  }, []);
  const loadDetail = useCallback(
    async (id: string) => {
      setDetailLoading(true);
      try {
        const value = await api(
          `/conversations/${id}?message_page=1&message_page_size=100`,
          conversationDetailSchema,
        );
        setDetail(value);
        history.replaceState(null, "", `/chat?conversation=${id}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Conversation unavailable.");
        setDetail(null);
        await loadList();
      } finally {
        setDetailLoading(false);
      }
    },
    [loadList],
  );
  useEffect(() => {
    Promise.all([
      // eslint-disable-next-line react-hooks/set-state-in-effect -- authenticated data load after hydration
      loadList(),
      api(
        "/database-connections?page=1&page_size=100",
        databaseListSchema,
      ).then((v) => setDatabases(v.items)),
      api(
        "/knowledge-bases?page=1&page_size=100",
        knowledgeBaseListSchema,
      ).then((v) => setKnowledge(v.items)),
    ])
      .catch((e) =>
        setError(
          e instanceof Error ? e.message : "The workspace could not be loaded.",
        ),
      )
      .finally(() => setLoading(false));
  }, [loadList]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- selection drives the persisted detail request
    if (activeId) void loadDetail(activeId);
    else setDetail(null);
  }, [activeId, loadDetail]);
  useEffect(() => {
    const expired = () => router.replace("/login");
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, [router]);
  const names = useMemo(
    () => (detail ? sourceNames(detail, databases, knowledge) : []),
    [detail, databases, knowledge],
  );

  async function remove() {
    if (!deleting) return;
    const id = deleting.id;
    try {
      const result = await fetch(`${API}/conversations/${id}`, {
        method: "DELETE",
      });
      if (!result.ok && result.status !== 404)
        throw new Error("Deletion failed.");
      setConversations((rows) => rows.filter((row) => row.id !== id));
      if (activeId === id) {
        setActiveId(conversations.find((row) => row.id !== id)?.id ?? null);
        setDetail(null);
      }
      setDeleting(null);
    } catch {
      setError("The conversation could not be deleted safely.");
    }
  }
  async function reconcile(messageId?: string) {
    if (!activeId) return;
    await loadDetail(activeId);
    await loadList();
    if (messageId) {
      const [sqlResult, citationResult] = await Promise.allSettled([
        api(`/messages/${messageId}/sql`, sqlResponseSchema),
        api(`/messages/${messageId}/citations`, citationListSchema),
      ]);
      if (sqlResult.status === "fulfilled") setSQL(sqlResult.value);
      if (citationResult.status === "fulfilled")
        setCitations(citationResult.value.items);
    }
  }
  async function inspectMessage(message: Message) {
    const sources = message.selected_sources.filter(
      (item): item is string => typeof item === "string",
    );
    const intents = [
      "general",
      "database",
      "document",
      "hybrid",
      "clarification",
    ];
    setResponse({
      conversation_id: detail!.id,
      message_id: message.id,
      answer: message.content,
      intent: (intents.includes(message.detected_intent ?? "")
        ? message.detected_intent
        : "clarification") as ChatResponse["intent"],
      sources_used: sources,
      sql: null,
      citations: [],
      warnings: message.warnings,
      usage: {
        prompt_tokens: message.prompt_tokens ?? 0,
        completion_tokens: message.completion_tokens ?? 0,
        provider_latency_ms: message.latency_ms ?? 0,
      },
    });
    setSQL(undefined);
    setCitations([]);
    setInspectorOpen(true);
    const [sqlResult, citationResult] = await Promise.allSettled([
      api(`/messages/${message.id}/sql`, sqlResponseSchema),
      api(`/messages/${message.id}/citations`, citationListSchema),
    ]);
    if (sqlResult.status === "fulfilled") setSQL(sqlResult.value);
    if (citationResult.status === "fulfilled")
      setCitations(citationResult.value.items);
  }
  async function send() {
    const message = draft.trim();
    if (
      !detail ||
      !message ||
      message.length > 4000 ||
      stream.phase === "preparing" ||
      stream.phase === "streaming"
    )
      return;
    setError(null);
    setDraft("");
    setOptimistic(message);
    setResponse(undefined);
    setSQL(undefined);
    setCitations([]);
    dispatch({ event: "begin" });
    const controller = new AbortController();
    abort.current = controller;
    const parser = new SSEParser();
    let completed = false;
    try {
      const result = await fetch(`${API}/chat/stream`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          conversation_id: detail.id,
          message,
          database_connection_ids: detail.database_connection_ids,
          knowledge_base_ids: detail.knowledge_base_ids,
          stream: true,
        }),
        signal: controller.signal,
      });
      if (result.status === 401) {
        router.replace("/login");
        return;
      }
      if (!result.ok || !result.body)
        throw new Error("The stream could not be started.");
      const reader = result.body
        .pipeThrough(new TextDecoderStream())
        .getReader();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const event of parser.push(value)) {
          dispatch(event);
          if (event.event === "completed") {
            completed = true;
            setResponse(event.data);
            await reconcile(event.data.message_id);
          }
          if (event.event === "error")
            throw new Error("The response could not be completed safely.");
        }
      }
      parser.finish();
      if (!completed) throw new Error("The response ended before completion.");
    } catch (e) {
      if (controller.signal.aborted) dispatch({ event: "cancel" });
      else {
        setError(
          e instanceof Error ? e.message : "The response stream failed.",
        );
        dispatch({ event: "error", data: { detail: "safe" } } as ChatEvent);
        await reconcile();
      }
    } finally {
      abort.current = null;
      setOptimistic(null);
    }
  }
  function cancel() {
    abort.current?.abort();
    dispatch({ event: "cancel" });
  }
  function select(id: string) {
    if (abort.current) return;
    setActiveId(id);
    setRailOpen(false);
    setResponse(undefined);
    setSQL(undefined);
    setCitations([]);
    dispatch({ event: "reset" });
  }
  return (
    <div className="chat-frame">
      <div className="hidden min-h-0 lg:block">
        <ConversationRail
          items={conversations}
          active={activeId}
          loading={loading}
          onSelect={select}
          onNew={() => setNewOpen(true)}
          onDelete={setDeleting}
        />
      </div>
      <section className="flex min-h-0 min-w-0 flex-col bg-[var(--surface)]">
        <header className="flex min-h-16 items-center gap-3 border-b border-[var(--border)] px-4">
          <button
            aria-label="Open conversations"
            onClick={() => setRailOpen(true)}
            className="icon-button lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-semibold">
              {detail?.title ||
                (activeId ? "Untitled conversation" : "Chat workspace")}
            </h1>
            <p className="truncate text-xs text-[var(--text-muted)]">
              {detail
                ? `${sourceMode(detail.database_connection_ids, detail.knowledge_base_ids)} · ${names.length ? names.join(", ") : "No selected sources"}`
                : "Create or select a conversation"}
            </p>
          </div>
          <button
            aria-label="Open response details"
            onClick={() => setInspectorOpen(true)}
            className="icon-button xl:hidden"
          >
            <PanelRight className="h-5 w-5" />
          </button>
        </header>
        {error && (
          <div
            role="alert"
            className="mx-4 mt-3 flex items-start justify-between rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
          >
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError(null)}>
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
        {detailLoading ? (
          <div className="flex flex-1 items-center justify-center text-sm text-[var(--text-muted)]">
            Loading conversation…
          </div>
        ) : activeId ? (
          <MessageHistory
            detail={detail}
            stream={stream}
            optimistic={optimistic}
            onInspect={(message) => void inspectMessage(message)}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center p-8 text-center">
            <div>
              <h2 className="font-semibold">No active conversation</h2>
              <p className="mt-1 text-sm text-[var(--text-muted)]">
                Create a conversation and choose approved sources to begin.
              </p>
              <button
                onClick={() => setNewOpen(true)}
                className="primary-button mx-auto mt-4"
              >
                <MessageSquarePlus className="h-4 w-4" />
                New conversation
              </button>
            </div>
          </div>
        )}
        <div className="sticky bottom-0 border-t border-[var(--border)] bg-[var(--surface)] p-3 sm:p-4">
          <div className="mx-auto max-w-3xl">
            <p className="mb-2 truncate text-xs text-[var(--text-muted)]">
              {detail
                ? `${sourceMode(detail.database_connection_ids, detail.knowledge_base_ids)} · ${names.join(", ") || "general knowledge"}`
                : "Select a conversation to send a message"}
            </p>
            <div className="flex items-end gap-2 rounded-lg border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-2 focus-within:border-[var(--primary)]">
              <label className="sr-only" htmlFor="chat-message">
                Message
              </label>
              <textarea
                ref={composer}
                id="chat-message"
                rows={1}
                maxLength={4000}
                value={draft}
                disabled={
                  !detail ||
                  stream.phase === "preparing" ||
                  stream.phase === "streaming"
                }
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
                placeholder="Ask a governed question…"
                className="max-h-36 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none"
              />
              {stream.phase === "preparing" || stream.phase === "streaming" ? (
                <button
                  aria-label="Cancel response"
                  onClick={cancel}
                  className="danger-button"
                >
                  <Square className="h-4 w-4" />
                </button>
              ) : (
                <button
                  aria-label="Send message"
                  disabled={!detail || !draft.trim() || draft.length > 4000}
                  onClick={send}
                  className="primary-button px-3"
                >
                  <Send className="h-4 w-4" />
                </button>
              )}
            </div>
            {draft.length >= 3600 && (
              <p
                className={`mt-1 text-right text-xs ${draft.length === 4000 ? "text-[var(--danger)]" : "text-[var(--text-muted)]"}`}
              >
                {4000 - draft.length} characters remaining
              </p>
            )}
            <p aria-live="polite" className="sr-only">
              {stream.status}
            </p>
          </div>
        </div>
      </section>
      <div className="hidden min-h-0 border-l border-[var(--border)] xl:block">
        <Inspector
          tab={tab}
          setTab={setTab}
          response={response ?? stream.final}
          sql={sql}
          citations={citations}
        />
      </div>
      {railOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label="Close conversations"
            className="absolute inset-0 bg-black/45"
            onClick={() => setRailOpen(false)}
          />
          <div className="relative h-full w-[min(88vw,300px)]">
            <ConversationRail
              items={conversations}
              active={activeId}
              loading={loading}
              onSelect={select}
              onNew={() => {
                setRailOpen(false);
                setNewOpen(true);
              }}
              onDelete={setDeleting}
              close={() => setRailOpen(false)}
            />
          </div>
        </div>
      )}
      {inspectorOpen && (
        <div className="fixed inset-0 z-40 xl:hidden">
          <button
            aria-label="Close response details"
            className="absolute inset-0 bg-black/45"
            onClick={() => setInspectorOpen(false)}
          />
          <div className="absolute inset-y-0 right-0 w-[min(92vw,380px)] border-l border-[var(--border)]">
            <Inspector
              tab={tab}
              setTab={setTab}
              response={response ?? stream.final}
              sql={sql}
              citations={citations}
              close={() => setInspectorOpen(false)}
            />
          </div>
        </div>
      )}
      {newOpen && (
        <NewConversationDialog
          databases={databases}
          knowledge={knowledge}
          onClose={() => setNewOpen(false)}
          onCreated={(item) => {
            setConversations((rows) => [item, ...rows]);
            setActiveId(item.id);
            setResponse(undefined);
            setSQL(undefined);
            setCitations([]);
            dispatch({ event: "reset" });
            setNewOpen(false);
            setTimeout(() => composer.current?.focus());
          }}
        />
      )}
      {deleting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
          <section
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            className="w-full max-w-md rounded-lg bg-[var(--surface-elevated)] p-5 shadow-xl"
          >
            <h2 id="delete-title" className="font-semibold">
              Delete conversation?
            </h2>
            <p className="mt-2 text-sm text-[var(--text-muted)]">
              “{deleting.title || "Untitled conversation"}” and its history will
              no longer be available.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setDeleting(null)}
                className="secondary-button"
              >
                Cancel
              </button>
              <button onClick={remove} className="danger-button">
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
