import "server-only";

export function backendUrl(path: string): URL {
  const base = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const parsed = new URL(base);
  if (!/^https?:$/.test(parsed.protocol))
    throw new Error("Invalid backend configuration");

  const suffixStart = path.search(/[?#]/);
  const rawPath = suffixStart === -1 ? path : path.slice(0, suffixStart);
  const suffix = suffixStart === -1 ? "" : path.slice(suffixStart);
  const parts = rawPath.split("/").filter(Boolean);

  while (parts[0] === "api") parts.shift();

  const apiPath = `/api${parts.length ? `/${parts.join("/")}` : ""}${suffix}`;
  const result = new URL(apiPath, parsed.origin);
  if (result.pathname !== "/api" && !result.pathname.startsWith("/api/"))
    throw new Error("Invalid backend configuration or path");
  return result;
}
