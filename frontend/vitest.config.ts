import { defineConfig } from "vitest/config";
export default defineConfig({
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    exclude: ["tests/e2e/**", "node_modules/**"],
    coverage: { reporter: ["text"] },
  },
  resolve: {
    alias: {
      "@": import.meta.dirname,
      "server-only": `${import.meta.dirname}/tests/server-only.ts`,
    },
  },
});
