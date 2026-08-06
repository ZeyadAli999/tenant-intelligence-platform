"use client";

import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  X,
} from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastOptions {
  title?: string;
  duration?: number;
}

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
  created_at: number;
}

type ToastListener = (
  toast: Omit<ToastItem, "id" | "created_at">,
) => void;

const listeners = new Set<ToastListener>();

export const toast = {
  success(message: string, options?: ToastOptions) {
    emit({ type: "success", message, ...options });
  },
  error(message: string, options?: ToastOptions) {
    emit({ type: "error", message, ...options });
  },
  warning(message: string, options?: ToastOptions) {
    emit({ type: "warning", message, ...options });
  },
  info(message: string, options?: ToastOptions) {
    emit({ type: "info", message, ...options });
  },
  subscribe(listener: ToastListener) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

const FLASH_STORAGE_KEY = "app_flash_toast";

const ALLOWLISTED_FLASH_MESSAGES: Record<
  string,
  { type: ToastType; message: string }
> = {
  logout_success: {
    type: "info",
    message: "Signed out successfully.",
  },
};

export function setFlashToast(key: string): void {
  if (typeof window === "undefined") return;
  if (!ALLOWLISTED_FLASH_MESSAGES[key]) return;
  try {
    sessionStorage.setItem(FLASH_STORAGE_KEY, key);
  } catch {
    // Ignore storage failure
  }
}

export function consumeFlashToast(): void {
  if (typeof window === "undefined") return;
  try {
    const key = sessionStorage.getItem(FLASH_STORAGE_KEY);
    if (key) {
      sessionStorage.removeItem(FLASH_STORAGE_KEY);
      const flash = ALLOWLISTED_FLASH_MESSAGES[key];
      if (flash) {
        toast[flash.type](flash.message);
      }
    }
  } catch {
    // Ignore storage failure
  }
}

export async function performClientLogout(router?: {
  replace(url: string): void;
  refresh(): void;
}): Promise<boolean> {
  try {
    const res = await fetch("/api/session/logout", { method: "POST" });
    if (res.ok) {
      setFlashToast("logout_success");
      toast.info("Signed out successfully.");
      if (router) {
        router.replace("/login");
        router.refresh();
      } else if (typeof window !== "undefined") {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/login");
      }
      return true;
    } else {
      toast.error("Failed to sign out. Please try again.");
      return false;
    }
  } catch {
    toast.error("Network error during sign out.");
    return false;
  }
}

function emit(toastData: Omit<ToastItem, "id" | "created_at">) {
  listeners.forEach((listener) => listener(toastData));
}

interface ToastContextValue {
  toast: typeof toast;
  toasts: ToastItem[];
  dismissToast: (id: string) => void;
  clearToasts: () => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    return {
      toast,
      toasts: [],
      dismissToast: () => undefined,
      clearToasts: () => undefined,
    };
  }
  return context;
}

const DEFAULT_DURATIONS: Record<ToastType, number> = {
  success: 4000,
  info: 4000,
  warning: 6000,
  error: 8000,
};

const DUPLICATE_SUPPRESSION_MS = 2000;
const MAX_VISIBLE_TOASTS = 5;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const lastEmittedRef = useRef<Map<string, number>>(new Map());

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearToasts = useCallback(() => {
    setToasts([]);
  }, []);

  const addToast = useCallback(
    (data: Omit<ToastItem, "id" | "created_at">) => {
      const now = Date.now();
      const key = `${data.type}:${data.message}`;
      const lastTime = lastEmittedRef.current.get(key) || 0;

      // Duplicate prevention within 2 seconds
      if (now - lastTime < DUPLICATE_SUPPRESSION_MS) {
        return;
      }
      lastEmittedRef.current.set(key, now);

      const id = Math.random().toString(36).substring(2, 9) + now.toString(36);
      const duration = data.duration ?? DEFAULT_DURATIONS[data.type];

      const newItem: ToastItem = {
        ...data,
        id,
        duration,
        created_at: now,
      };

      setToasts((prev) => [...prev.slice(-(MAX_VISIBLE_TOASTS - 1)), newItem]);
    },
    [],
  );

  useEffect(() => {
    const unsubscribe = toast.subscribe(addToast);
    consumeFlashToast();
    return unsubscribe;
  }, [addToast]);

  return (
    <ToastContext.Provider
      value={{ toast, toasts, dismissToast, clearToasts }}
    >
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  );
}

export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Notifications"
      className="fixed top-4 right-4 z-50 flex flex-col gap-2.5 max-w-sm w-[calc(100vw-2rem)] sm:w-80 pointer-events-none"
    >
      {toasts.map((item) => (
        <ToastCard key={item.id} item={item} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastCard({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: string) => void;
}) {
  useEffect(() => {
    const duration = item.duration ?? DEFAULT_DURATIONS[item.type];
    if (duration <= 0 || duration === Infinity) return;
    const timer = setTimeout(() => {
      onDismiss(item.id);
    }, duration);
    return () => clearTimeout(timer);
  }, [item.id, item.type, item.duration, onDismiss]);

  const isError = item.type === "error";
  const role = isError ? "alert" : "status";
  const ariaLive = isError ? "assertive" : "polite";

  return (
    <div
      role={role}
      aria-live={ariaLive}
      className={`pointer-events-auto flex items-start gap-3 rounded-lg border p-3.5 shadow-lg transition-all duration-200 motion-reduce:transition-none bg-[var(--surface-elevated)] text-[var(--text-primary)] ${
        item.type === "success"
          ? "border-[color-mix(in_srgb,var(--success)_35%,var(--border))]"
          : item.type === "error"
          ? "border-[color-mix(in_srgb,var(--danger)_35%,var(--border))]"
          : item.type === "warning"
          ? "border-[color-mix(in_srgb,var(--warning)_35%,var(--border))]"
          : "border-[color-mix(in_srgb,var(--primary)_35%,var(--border))]"
      }`}
    >
      {/* Icon */}
      <div className="shrink-0 mt-0.5">
        {item.type === "success" && (
          <CheckCircle2 aria-hidden className="h-5 w-5 text-[var(--success)]" />
        )}
        {item.type === "error" && (
          <AlertCircle aria-hidden className="h-5 w-5 text-[var(--danger)]" />
        )}
        {item.type === "warning" && (
          <AlertTriangle aria-hidden className="h-5 w-5 text-[var(--warning)]" />
        )}
        {item.type === "info" && (
          <Info aria-hidden className="h-5 w-5 text-[var(--primary)]" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pr-1">
        {item.title && (
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-0.5">
            {item.title}
          </p>
        )}
        <p className="text-sm font-medium leading-snug break-words">
          {item.message}
        </p>
      </div>

      {/* Close Button */}
      <button
        type="button"
        onClick={() => onDismiss(item.id)}
        className="shrink-0 rounded p-1 text-[var(--text-muted)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] transition-colors"
        aria-label="Dismiss notification"
        title="Dismiss notification"
      >
        <X aria-hidden className="h-4 w-4" />
      </button>
    </div>
  );
}
