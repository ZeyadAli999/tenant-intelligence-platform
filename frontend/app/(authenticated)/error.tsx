"use client";
import { ErrorState } from "@/components/ui/states";
export default function ErrorPage() {
  return (
    <ErrorState message="The page could not be loaded. Refresh the browser or return to the overview." />
  );
}
