"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { KBDetailView } from "./kb-detail-view";
import { KBListView } from "./kb-list-view";

export function KnowledgeWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const selectedKbId = searchParams.get("kbId");

  const handleSelectKB = (id: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("kbId", id);
    router.push(`${pathname}?${params.toString()}` as never);
  };

  const handleBack = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("kbId");
    const target = params.toString()
      ? `${pathname}?${params.toString()}`
      : pathname;
    router.push(target as never);
  };

  if (selectedKbId) {
    return <KBDetailView kbId={selectedKbId} onBack={handleBack} />;
  }

  return <KBListView onSelectKB={handleSelectKB} />;
}
