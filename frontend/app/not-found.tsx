import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";
export default function NotFound() {
  return (
    <main className="mx-auto max-w-xl px-5 py-24">
      <ErrorState
        title="Page not found"
        message="The page you requested does not exist or is not available in this workspace."
      />
      <div className="text-center">
        <Button asChild>
          <Link href="/dashboard">Return to overview</Link>
        </Button>
      </div>
    </main>
  );
}
