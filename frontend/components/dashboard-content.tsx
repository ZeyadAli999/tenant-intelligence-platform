"use client";
import { useEffect, useState } from "react";
import {
  CapabilitySections,
  GettingStarted,
  SecurityControlList,
  SystemStatusStrip,
  WorkflowSteps,
  WorkspaceHeader,
} from "@/components/dashboard-sections";
import { ErrorState, LoadingState } from "@/components/ui/states";
import type { CurrentUser } from "@/lib/contracts";

type State = { user: CurrentUser; live: boolean; ready: boolean };
export function DashboardContent() {
  const [state, setState] = useState<State | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    Promise.all([
      fetch("/api/session/me"),
      fetch("/api/backend/health/live"),
      fetch("/api/backend/health/ready"),
    ])
      .then(async ([me, live, ready]) => {
        if (!me.ok) throw new Error();
        setState({
          user: (await me.json()) as CurrentUser,
          live: live.ok,
          ready: ready.ok,
        });
      })
      .catch(() => setFailed(true));
  }, []);
  if (failed)
    return (
      <ErrorState
        title="Workspace unavailable"
        message="We could not reach the platform services. Check connectivity and try again."
      />
    );
  if (!state) return <LoadingState />;
  return (
    <>
      <WorkspaceHeader user={state.user} ready={state.ready} />
      <SystemStatusStrip live={state.live} ready={state.ready} />
      <WorkflowSteps />
      <CapabilitySections />
      <SecurityControlList />
      <GettingStarted />
    </>
  );
}
