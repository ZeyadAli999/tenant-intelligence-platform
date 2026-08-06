import { Suspense } from "react";
import { DatabaseWorkspace } from "@/components/databases/database-workspace";

export default function DatabasesPage() {
  return (
    <Suspense
      fallback={
        <div className="py-12 text-center text-sm text-[var(--fg-muted)]">
          Loading database workspace...
        </div>
      }
    >
      <DatabaseWorkspace />
    </Suspense>
  );
}
