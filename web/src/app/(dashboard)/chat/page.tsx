"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { ConversationList } from "@/components/chat/conversation-list";
import { MessageList } from "@/components/chat/message-list";
import { MessageInput } from "@/components/chat/message-input";
import { AgentStatus } from "@/components/chat/agent-status";

export default function ChatPage() {
  const { token } = useAuthStore();
  const { fetchConversations } = useChatStore();

  useEffect(() => {
    if (token) {
      fetchConversations(token);
    }
  }, [token, fetchConversations]);

  return (
    <div className="flex h-full">
      <ConversationList />
      <div className="flex flex-1 flex-col">
        <AgentStatus />
        <MessageList />
        <MessageInput />
      </div>
    </div>
  );
}
