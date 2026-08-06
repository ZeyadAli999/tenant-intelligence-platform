"use client";

import { Search, UserPlus, X } from "lucide-react";
import { createPortal } from "react-dom";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {
  ADMINISTRATOR_DENIED_MESSAGE,
  AdministratorRequiredError,
  createTenantUser,
  listTenantRoles,
  listTenantUsers,
  updateTenantUser,
} from "@/lib/admin-api";
import {
  tenantUserCreateSchema,
  type TenantRole,
  type TenantUser,
  type TenantUserCreateInput,
} from "@/lib/admin-contracts";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

function roleLabel(name: string) {
  return name.toLowerCase() === "administrator"
    ? "Administrator"
    : name.replace(/(^|[-_\s])\w/g, (value) => value.toUpperCase());
}

function RoleOptions({
  roles,
  selected,
  onChange,
}: {
  roles: TenantRole[];
  selected: string[];
  onChange(value: string[]): void;
}) {
  return (
    <fieldset>
      <legend className="text-sm font-medium">Roles</legend>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {roles.map((role) => (
          <label
            key={role.id}
            className="flex min-h-11 items-center gap-3 rounded-md border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-sm"
          >
            <input
              type="checkbox"
              checked={selected.includes(role.id)}
              onChange={(event) =>
                onChange(
                  event.target.checked
                    ? [...selected, role.id]
                    : selected.filter((id) => id !== role.id),
                )
              }
            />
            <span>{roleLabel(role.name)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function DialogFrame({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose(): void;
  children: React.ReactNode;
}) {
  const headingId = "user-dialog-heading";
  const backdropRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useLayoutEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    const background = Array.from(document.body.children).filter(
      (element): element is HTMLElement =>
        element instanceof HTMLElement && element !== backdropRef.current,
    );
    background.forEach((element) => {
      element.inert = true;
    });
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();
    return () => {
      background.forEach((element) => {
        element.inert = false;
      });
      document.body.style.overflow = previousOverflow;
      trigger?.focus();
    };
  }, []);

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(
      backdropRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    ).filter((element) => !element.hidden);
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        onKeyDown={handleKeyDown}
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-lg border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-5 shadow-xl sm:p-6"
      >
        <div className="mb-5 flex items-center justify-between gap-4 border-b border-[var(--border)] pb-4">
          <h2 id={headingId} className="text-lg font-semibold">
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            aria-label="Close account dialog"
            onClick={onClose}
            className="icon-button"
          >
            <X aria-hidden className="h-4 w-4" />
          </button>
        </div>
        {children}
      </section>
    </div>,
    document.body,
  );
}

function CreateUserDialog({
  roles,
  onClose,
  onCreate,
}: {
  roles: TenantRole[];
  onClose(): void;
  onCreate(input: TenantUserCreateInput): Promise<void>;
}) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"active" | "inactive">("active");
  const [roleIds, setRoleIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const parsed = tenantUserCreateSchema.safeParse({
      full_name: fullName,
      email,
      password,
      status,
      role_ids: roleIds,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message || "Check the account details.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onCreate(parsed.data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Account creation failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <DialogFrame title="Create tenant user" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert>{error}</Alert>}
        <label className="block text-sm font-medium">
          Full name
          <Input
            className="mt-1.5"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            autoComplete="name"
          />
        </label>
        <label className="block text-sm font-medium">
          Email address
          <Input
            className="mt-1.5"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
          />
        </label>
        <label className="block text-sm font-medium">
          Initial password
          <Input
            className="mt-1.5"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
          />
          <span className="mt-1 block text-xs font-normal text-[var(--text-muted)]">
            Minimum 12 characters. The password is never displayed after creation.
          </span>
        </label>
        <label className="block text-sm font-medium">
          Account status
          <select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as "active" | "inactive")
            }
            className="field mt-1.5"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
        <RoleOptions roles={roles} selected={roleIds} onChange={setRoleIds} />
        <div className="flex justify-end gap-3 border-t border-[var(--border)] pt-4">
          <button type="button" onClick={onClose} className="secondary-button">
            Cancel
          </button>
          <Button type="submit" disabled={saving}>
            {saving ? "Creating…" : "Create user"}
          </Button>
        </div>
      </form>
    </DialogFrame>
  );
}

function ManageUserDialog({
  user,
  roles,
  onClose,
  onSave,
}: {
  user: TenantUser;
  roles: TenantRole[];
  onClose(): void;
  onSave(input: {
    full_name: string | null;
    status: "active" | "inactive";
    role_ids: string[];
  }): Promise<void>;
}) {
  const [fullName, setFullName] = useState(user.full_name || "");
  const [status, setStatus] = useState(user.status);
  const [roleIds, setRoleIds] = useState(user.roles.map((role) => role.id));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave({
        full_name: fullName.trim() || null,
        status,
        role_ids: roleIds,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Account update failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <DialogFrame title={`Manage ${user.full_name || user.email}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
            Email address
          </p>
          <p className="mt-1 text-sm">{user.email}</p>
        </div>
        <label className="block text-sm font-medium">
          Full name
          <Input
            className="mt-1.5"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium">
          Account status
          <select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as "active" | "inactive")
            }
            className="field mt-1.5"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
        <RoleOptions roles={roles} selected={roleIds} onChange={setRoleIds} />
        <div className="flex justify-end gap-3 border-t border-[var(--border)] pt-4">
          <button type="button" onClick={onClose} className="secondary-button">
            Cancel
          </button>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
    </DialogFrame>
  );
}

export function UsersWorkspace() {
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [roles, setRoles] = useState<TenantRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<TenantUser | null>(null);

  const handleError = useCallback((reason: unknown) => {
    if (reason instanceof AdministratorRequiredError) {
      setDenied(true);
      setError(null);
      return;
    }
    setError(reason instanceof Error ? reason.message : "Administration is unavailable.");
  }, []);

  const load = useCallback(
    async (searchValue: string, statusValue: string) => {
      try {
        const [userPage, rolePage] = await Promise.all([
          listTenantUsers(searchValue, statusValue),
          listTenantRoles(),
        ]);
        setUsers(userPage.items);
        setRoles(rolePage.items);
      } catch (reason) {
        handleError(reason);
      } finally {
        setLoading(false);
      }
    },
    [handleError],
  );

  useEffect(() => {
    let active = true;
    void Promise.all([listTenantUsers(), listTenantRoles()])
      .then(([userPage, rolePage]) => {
        if (!active) return;
        setUsers(userPage.items);
        setRoles(rolePage.items);
      })
      .catch((reason: unknown) => {
        if (active) handleError(reason);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [handleError]);

  if (denied) return <Alert>{ADMINISTRATOR_DENIED_MESSAGE}</Alert>;

  return (
    <section aria-labelledby="users-heading">
      <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-[var(--primary)]">Administration</p>
          <h1 id="users-heading" className="mt-1 text-2xl font-semibold">
            Users
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-[var(--text-secondary)]">
            Create and manage accounts, status, and tenant-scoped role assignments.
          </p>
        </div>
        <Button type="button" onClick={() => setCreating(true)}>
          <UserPlus aria-hidden className="h-4 w-4" />
          Create user
        </Button>
      </header>

      <form
        className="my-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          setLoading(true);
          setError(null);
          void load(search, status);
        }}
        role="search"
      >
        <label className="relative">
          <span className="sr-only">Search users</span>
          <Search
            aria-hidden
            className="absolute left-3 top-3.5 h-4 w-4 text-[var(--text-muted)]"
          />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name or email"
            className="pl-9"
          />
        </label>
        <label>
          <span className="sr-only">Filter by status</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="field h-11"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
        <button type="submit" className="secondary-button">
          Apply filters
        </button>
      </form>

      {error && (
        <div className="mb-4">
          <ErrorState title="User management unavailable" message={error} />
        </div>
      )}
      {loading ? (
        <LoadingState label="Loading tenant users…" />
      ) : !users.length ? (
        <EmptyState
          title="No users found"
          message="Adjust the filters or create a tenant user."
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border-strong)] bg-[var(--surface)]">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-[var(--border)] bg-[var(--surface-subtle)] text-xs uppercase tracking-wide text-[var(--text-secondary)]">
              <tr>
                <th scope="col" className="px-4 py-3">Account</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3">Roles</th>
                <th scope="col" className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {users.map((user) => (
                <tr key={user.id}>
                  <td className="px-4 py-3">
                    <p className="font-medium">{user.full_name || "User"}</p>
                    <p className="mt-0.5 text-xs text-[var(--text-muted)]">{user.email}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${user.status === "active" ? "bg-[color-mix(in_srgb,var(--success)_12%,var(--surface))] text-[var(--success)]" : "bg-[var(--surface-subtle)] text-[var(--text-secondary)]"}`}>
                      {user.status === "active" ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {user.roles.length
                      ? user.roles.map((role) => roleLabel(role.name)).join(", ")
                      : "No roles assigned"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      className="secondary-button min-h-9 px-3 py-1.5 text-xs"
                      onClick={() => setEditing(user)}
                    >
                      Manage account
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <CreateUserDialog
          roles={roles}
          onClose={() => setCreating(false)}
          onCreate={async (input) => {
            try {
              await createTenantUser(input);
              setCreating(false);
              await load(search, status);
            } catch (reason) {
              handleError(reason);
              throw reason;
            }
          }}
        />
      )}
      {editing && (
        <ManageUserDialog
          user={editing}
          roles={roles}
          onClose={() => setEditing(null)}
          onSave={async (input) => {
            try {
              await updateTenantUser(editing.id, input);
              setEditing(null);
              await load(search, status);
            } catch (reason) {
              handleError(reason);
              throw reason;
            }
          }}
        />
      )}
    </section>
  );
}
