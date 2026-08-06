"use client";
import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

type Theme = "light" | "dark" | "system";
const themes: Theme[] = ["system", "light", "dark"];

function currentTheme(): Theme {
  const stored = localStorage.getItem("theme");
  return stored === "light" || stored === "dark" ? stored : "system";
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("tenant-intelligence-theme", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("tenant-intelligence-theme", callback);
  };
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(
    subscribe,
    currentTheme,
    (): Theme => "system",
  );
  function cycle() {
    const next =
      themes[(themes.indexOf(theme) + 1) % themes.length] ?? "system";
    if (next === "system") {
      localStorage.removeItem("theme");
      delete document.documentElement.dataset.theme;
    } else {
      localStorage.setItem("theme", next);
      document.documentElement.dataset.theme = next;
    }
    window.dispatchEvent(new Event("tenant-intelligence-theme"));
  }
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return (
    <button
      type="button"
      onClick={cycle}
      className="inline-flex h-10 w-10 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text)]"
      aria-label={`Theme: ${theme}. Change theme`}
    >
      <Icon aria-hidden className="h-4 w-4" />
    </button>
  );
}
