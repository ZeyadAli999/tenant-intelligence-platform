import { ChatWorkspace } from "@/components/chat-workspace";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ conversation?: string }>;
}) {
  const { conversation } = await searchParams;
  return <ChatWorkspace initialConversationId={conversation ?? null} />;
}
