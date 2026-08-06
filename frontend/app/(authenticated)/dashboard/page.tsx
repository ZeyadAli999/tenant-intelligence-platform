import type { Metadata } from "next";
import { DashboardContent } from "@/components/dashboard-content";
export const metadata: Metadata = { title: "Overview" };
export default function DashboardPage() {
  return <DashboardContent />;
}
