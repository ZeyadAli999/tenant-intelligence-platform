import type { Metadata } from "next";
import { PermissionsWorkspace } from "@/components/permissions/permissions-workspace";

export const metadata: Metadata = { title: "Permissions" };

export default function PermissionsPage() {
  return <PermissionsWorkspace />;
}
