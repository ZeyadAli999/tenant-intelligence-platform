import { Suspense } from "react";
import { KnowledgeWorkspace } from "@/components/knowledge/knowledge-workspace";
import { LoadingState } from "@/components/ui/states";

export default function KnowledgePage() {
  return (
    <Suspense
      fallback={<LoadingState label="Loading Knowledge Workspace..." />}
    >
      <KnowledgeWorkspace />
    </Suspense>
  );
}
