"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useChat } from "@/hooks/useChat";
import { MessageList } from "@/components/chat/message-list";
import { MessageInput } from "@/components/chat/message-input";

export function WorkspaceChatPanel() {
  const { token } = useAuthStore();
  const {
    conversations,
    currentConversation,
    createConversation,
    selectConversation,
    fetchConversations,
  } = useChatStore();
  const { activeProjectId } = useWorkspaceStore();

  // Initialize chat connection
  useChat();

  // Ensure we have conversations loaded
  useEffect(() => {
    if (token && conversations.length === 0) {
      fetchConversations(token);
    }
  }, [token]);

  // Auto-select or create a conversation for the current project
  useEffect(() => {
    if (!token || !activeProjectId) return;

    // Find existing conversation for this project
    const projectConv = conversations.find(
      (c) => c.project_id === activeProjectId && c.status === "ACTIVE"
    );

    if (projectConv && projectConv.id !== currentConversation?.id) {
      selectConversation(token, projectConv.id);
    } else if (!projectConv && !currentConversation) {
      createConversation(token, "Workspace Chat", activeProjectId);
    }
  }, [token, activeProjectId, conversations]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <MessageList />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t">
        <MessageInput />
      </div>
    </div>
  );
}
