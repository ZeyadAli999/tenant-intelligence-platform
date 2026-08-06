"use client";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  BookOpen,
  Bot,
  ChevronDown,
  Database,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ProductIdentity } from "@/components/product-identity";
import { ThemeToggle } from "@/components/theme-toggle";
import { Alert } from "@/components/ui/alert";
import { LoadingState } from "@/components/ui/states";
import { performClientLogout } from "@/components/ui/toast";
import {
  hasAdministratorAccess,
  type CurrentUser,
} from "@/lib/contracts";

const mainNavigation = [
  ["Overview", "/dashboard", LayoutDashboard],
  ["Chat", "/chat", Bot],
  ["Knowledge", "/knowledge", BookOpen],
  ["Databases", "/databases", Database],
] as const;
const adminNavigation = [
  ["Users", "/users", Users],
  ["Permissions", "/permissions", ShieldCheck],
] as const;
const settingsNavigation = [
  ["Settings", "/settings", Settings],
] as const;

export function NavigationGroup({
  label,
  items,
  onSelect,
}: {
  label: string;
  items:
    | typeof mainNavigation
    | typeof adminNavigation
    | typeof settingsNavigation;
  onSelect?: () => void;
}) {
  const pathname = usePathname();
  return (
    <div className="mb-6">
      <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
        {label}
      </p>
      <nav aria-label={label} className="space-y-0.5">
        {items.map(([itemLabel, href, Icon]) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href as never}
              onClick={onSelect}
              aria-current={active ? "page" : undefined}
              className={`relative flex min-h-10 items-center gap-3 rounded-[5px] px-3 text-sm font-medium ${active ? "bg-[var(--nav-selected)] text-[var(--text)] before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:bg-[var(--primary)]" : "text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text)]"}`}
            >
              <Icon aria-hidden className="h-[17px] w-[17px]" />
              {itemLabel}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function AccountMenu({
  user,
  logout,
  mobile = false,
}: {
  user: CurrentUser | null;
  logout: () => Promise<void>;
  mobile?: boolean;
}) {
  const administrator = hasAdministratorAccess(user);
  return (
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger
        aria-label="Open account menu"
        className={`flex min-h-11 w-full items-center gap-3 rounded-md px-2 text-left hover:bg-[var(--surface-subtle)] ${mobile ? "justify-end" : ""}`}
      >
        <span
          aria-hidden
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--surface-subtle)] text-xs font-semibold text-[var(--text-secondary)]"
        >
          {(user?.full_name || user?.email || "A").slice(0, 1).toUpperCase()}
        </span>
        <span
          className={`${mobile ? "hidden sm:block" : "block"} min-w-0 flex-1`}
        >
          <span className="block truncate text-sm font-medium">
            {user?.full_name || "Workspace account"}
          </span>
          {administrator && (
            <span className="mt-0.5 inline-flex rounded-full border border-[color-mix(in_srgb,var(--primary)_35%,var(--border))] bg-[color-mix(in_srgb,var(--primary)_8%,var(--surface))] px-2 py-0.5 text-[10px] font-semibold text-[var(--primary)]">
              Administrator
            </span>
          )}
          <span className="block truncate text-xs text-[var(--text-muted)]">
            {user?.email || "Loading identity"}
          </span>
        </span>
        <ChevronDown
          aria-hidden
          className="h-4 w-4 shrink-0 text-[var(--text-muted)]"
        />
      </DropdownMenu.Trigger>
      <DropdownMenu.Content
        align="end"
        sideOffset={6}
        className="z-50 min-w-56 rounded-md border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-1 shadow-lg"
      >
          <div className="border-b border-[var(--border)] px-3 py-2.5">
            <p className="truncate text-sm font-semibold">
              {user?.full_name || "User"}
            </p>
            <p className="mt-0.5 truncate text-xs text-[var(--text-secondary)]">
              {user?.email || "Loading identity"}
            </p>
            <p className="mt-2 truncate text-xs text-[var(--text-muted)]">
              {user?.tenant.name || "Tenant Intelligence"}
            </p>
          </div>
          <DropdownMenu.Item
            onSelect={logout}
            className="flex cursor-pointer items-center gap-2 rounded px-3 py-2 text-sm text-[var(--danger)] outline-none focus:bg-[var(--surface-subtle)]"
          >
            <LogOut aria-hidden className="h-4 w-4" />
            Sign out
          </DropdownMenu.Item>
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}

function SidebarContent({
  user,
  logout,
  onSelect,
}: {
  user: CurrentUser | null;
  logout: () => Promise<void>;
  onSelect?: () => void;
}) {
  const administrator = hasAdministratorAccess(user);
  return (
    <>
      <div className="flex h-[76px] items-center border-b border-[var(--border)] px-5">
        <ProductIdentity compact />
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-5">
        <NavigationGroup
          label="Main"
          items={mainNavigation}
          onSelect={onSelect}
        />
        {administrator && (
          <NavigationGroup
            label="Administration"
            items={adminNavigation}
            onSelect={onSelect}
          />
        )}
        <NavigationGroup
          label="Settings"
          items={settingsNavigation}
          onSelect={onSelect}
        />
      </div>
      <div className="border-t border-[var(--border)] p-3">
        <div className="mb-2 flex items-center justify-between px-2">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium">
              {user?.tenant.name || "Workspace"}
            </p>
            <p className="truncate text-[11px] text-[var(--text-muted)]">
              {user?.tenant.code || "Tenant identity"}
            </p>
          </div>
          <ThemeToggle />
        </div>
        <AccountMenu user={user} logout={logout} />
      </div>
    </>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    fetch("/api/session/me")
      .then(async (r) => {
        if (r.status === 401) {
          router.replace("/login");
          return;
        }
        if (r.ok) setUser((await r.json()) as CurrentUser);
      })
      .catch(() => undefined);
  }, [router]);
  async function logout() {
    await performClientLogout(router);
  }
  const currentLabel =
    [...mainNavigation, ...adminNavigation, ...settingsNavigation].find(
      ([, href]) => href === pathname,
    )?.[0] ?? "Workspace";
  const administratorRoute = adminNavigation.some(([, href]) => href === pathname);
  const administrator = hasAdministratorAccess(user);
  const content = administratorRoute ? (
    user === null ? (
      <LoadingState label="Verifying administrator access…" />
    ) : administrator ? (
      children
    ) : (
      <section aria-labelledby="access-denied-heading" className="max-w-2xl">
        <h1 id="access-denied-heading" className="text-xl font-semibold">
          Administration access required
        </h1>
        <div className="mt-4">
          <Alert>Access denied. This area is restricted to Administrators.</Alert>
        </div>
      </section>
    )
  ) : (
    children
  );
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[264px_1fr]">
      <aside
        aria-label="Primary navigation"
        className="fixed inset-y-0 left-0 z-30 hidden w-[264px] border-r border-[var(--border)] bg-[var(--sidebar)] lg:flex lg:flex-col"
      >
        <SidebarContent user={user} logout={logout} />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/45"
            onClick={() => setOpen(false)}
          />
          <aside
            aria-label="Mobile navigation"
            className="relative flex h-full w-[294px] flex-col bg-[var(--sidebar)] shadow-xl"
          >
            <button
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
              className="absolute right-3 top-[18px] z-10 flex h-10 w-10 items-center justify-center rounded-md hover:bg-[var(--surface-subtle)]"
            >
              <X aria-hidden className="h-5 w-5" />
            </button>
            <SidebarContent
              user={user}
              logout={logout}
              onSelect={() => setOpen(false)}
            />
          </aside>
        </div>
      )}
      <div className="min-w-0 lg:col-start-2">
        <header className="sticky top-0 z-20 flex h-16 items-center border-b border-[var(--border)] bg-[var(--surface)] px-4 sm:px-6 lg:px-8">
          <button
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
            className="mr-3 flex h-10 w-10 items-center justify-center rounded-md hover:bg-[var(--surface-subtle)] lg:hidden"
          >
            <Menu aria-hidden className="h-5 w-5" />
          </button>
          <div>
            <p className="text-sm font-semibold">{currentLabel}</p>
            <p className="hidden text-xs text-[var(--text-muted)] sm:block">
              {user?.tenant.name || "Secure workspace"}
            </p>
          </div>
          <div className="ml-auto flex items-center lg:hidden">
            <ThemeToggle />
            <div className="w-52 max-w-[55vw]">
              <AccountMenu user={user} logout={logout} mobile />
            </div>
          </div>
        </header>
        <main
          id="main-content"
          className={
            pathname === "/chat"
              ? "h-[calc(100vh-4rem)] min-h-[520px] overflow-hidden"
              : "mx-auto w-full max-w-[1240px] px-5 py-7 sm:px-8 lg:px-10 lg:py-9"
          }
        >
          {content}
        </main>
      </div>
    </div>
  );
}
