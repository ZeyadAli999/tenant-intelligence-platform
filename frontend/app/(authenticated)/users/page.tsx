import type { Metadata } from "next";
import { UsersWorkspace } from "@/components/users/users-workspace";

export const metadata: Metadata = { title: "Users" };

export default function UsersPage() {
  return <UsersWorkspace />;
}
