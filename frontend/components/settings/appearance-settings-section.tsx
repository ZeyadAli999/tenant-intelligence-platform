"use client";

import { Monitor, Moon, Palette, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

type Theme = "light" | "dark" | "system";

function currentTheme(): Theme {
  if (typeof window === "undefined") return "system";
  const stored = localStorage.getItem("theme");
  return stored === "light" || stored === "dark" ? stored : "system";
}

function subscribe(callback: () => void) {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener("storage", callback);
  window.addEventListener("tenant-intelligence-theme", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("tenant-intelligence-theme", callback);
  };
}

function applyTheme(next: Theme) {
  if (next === "system") {
    localStorage.removeItem("theme");
    delete document.documentElement.dataset.theme;
  } else {
    localStorage.setItem("theme", next);
    document.documentElement.dataset.theme = next;
  }
  window.dispatchEvent(new Event("tenant-intelligence-theme"));
}

const themeOptions: Array<{
  id: Theme;
  label: string;
  description: string;
  icon: typeof Sun;
}> = [
  {
    id: "system",
    label: "System Preference",
    description: "Automatically match your operating system theme settings.",
    icon: Monitor,
  },
  {
    id: "light",
    label: "Light Mode",
    description: "Clean, high-contrast light theme with high legibility.",
    icon: Sun,
  },
  {
    id: "dark",
    label: "Dark Mode",
    description: "Sleek dark theme optimized for low-light environments.",
    icon: Moon,
  },
];

export function AppearanceSettingsSection() {
  const activeTheme = useSyncExternalStore(
    subscribe,
    currentTheme,
    (): Theme => "system",
  );

  return (
    <section aria-labelledby="appearance-settings-heading" className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h2
          id="appearance-settings-heading"
          className="flex items-center gap-2 text-lg font-semibold text-[var(--text)]"
        >
          <Palette className="h-5 w-5 text-[var(--primary)]" aria-hidden />
          Appearance &amp; Interface
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Personalize workspace theme modes and visual preference settings.
        </p>
      </div>

      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Interface Theme Mode
        </p>
        <div
          role="radiogroup"
          aria-label="Interface Theme Mode"
          className="grid gap-3 sm:grid-cols-3"
        >
          {themeOptions.map(({ id, label, description, icon: Icon }) => {
            const isSelected = activeTheme === id;
            return (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => applyTheme(id)}
                className={`flex flex-col justify-between rounded-lg border p-4 text-left transition-all ${
                  isSelected
                    ? "border-[var(--primary)] bg-[color-mix(in_srgb,var(--primary)_8%,var(--surface))] ring-1 ring-[var(--primary)]"
                    : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-subtle)]"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div
                    className={`flex h-9 w-9 items-center justify-center rounded-md ${
                      isSelected
                        ? "bg-[var(--primary)] text-[var(--on-primary)]"
                        : "bg-[var(--surface-subtle)] text-[var(--text-secondary)]"
                    }`}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </div>
                  {isSelected && (
                    <span className="rounded-full bg-[var(--primary)] px-2 py-0.5 text-[10px] font-semibold text-[var(--on-primary)]">
                      Active
                    </span>
                  )}
                </div>
                <div className="mt-4">
                  <span className="block text-sm font-semibold text-[var(--text)]">
                    {label}
                  </span>
                  <span className="mt-1 block text-xs leading-relaxed text-[var(--text-secondary)]">
                    {description}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-subtle)] p-4 text-xs text-[var(--text-secondary)]">
        <p className="font-semibold text-[var(--text)]">
          Accessibility &amp; Motion Behavior
        </p>
        <p className="mt-1 leading-relaxed">
          Tenant Intelligence automatically respects your operating system&apos;s reduced-motion configuration (<code className="rounded bg-[var(--surface)] px-1 py-0.5 font-mono text-[11px]">prefers-reduced-motion</code>). Interface animations and dynamic transitions are subdued automatically when requested by system settings.
        </p>
      </div>
    </section>
  );
}
