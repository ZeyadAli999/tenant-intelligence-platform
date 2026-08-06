import "server-only";

export function backendUrl(path: string): URL {
  const base = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const parsed = new URL(base);
  if (!/^https?:$/.test(parsed.protocol))
    throw new Error("Invalid backend configuration");
  return new URL(path, parsed.origin);
}
