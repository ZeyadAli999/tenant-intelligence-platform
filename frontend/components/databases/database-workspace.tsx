"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DatabaseDetailView } from "./database-detail-view";
import { DatabaseListView } from "./database-list-view";

export function DatabaseWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const selectedConnectionId = searchParams.get("connectionId");
  const [isTenantAdmin, setIsTenantAdmin] = useState(false);

  useEffect(() => {
    async function checkAdmin() {
      try {
        const res = await fetch("/api/session/me");
        if (res.ok) {
          const user = await res.json();
          setIsTenantAdmin(Boolean(user.is_tenant_admin));
        }
      } catch {
        setIsTenantAdmin(false);
      }
    }
    checkAdmin();
  }, []);

  const handleSelectConnection = (id: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("connectionId", id);
    router.push(`${pathname}?${params.toString()}` as never);
  };

  const handleBack = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("connectionId");
    const target = params.toString()
      ? `${pathname}?${params.toString()}`
      : pathname;
    router.push(target as never);
  };

  if (selectedConnectionId) {
    return (
      <DatabaseDetailView
        connectionId={selectedConnectionId}
        isTenantAdmin={isTenantAdmin}
        onBack={handleBack}
      />
    );
  }

  return (
    <DatabaseListView
      isTenantAdmin={isTenantAdmin}
      onSelectConnection={handleSelectConnection}
    />
  );
}
