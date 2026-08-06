import { NextResponse } from "next/server";

export function safeError(
  status: number,
  message: string,
  requestId?: string | null,
) {
  return NextResponse.json(
    { message, ...(requestId ? { request_id: requestId } : {}) },
    { status },
  );
}

export function safeBackendMessage(status: number): string {
  if (status === 400) return "The request could not be completed.";
  if (status === 401) return "Invalid credentials";
  if (status === 403)
    return "You do not have permission to perform this action.";
  if (status === 404) return "The requested resource was not found.";
  if (status === 409) return "This item already exists.";
  return "The service could not complete the request.";
}
