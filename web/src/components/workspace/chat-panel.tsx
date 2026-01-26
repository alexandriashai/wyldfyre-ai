"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useChat } from "@/hooks/useChat";
import { MessageList } from "@/components/chat/message-list";
import { MessageInput } from "@/components/chat/message-input";
import { UsageBadge } from "@/components/chat/usage-meter";
import { AgentBadge } from "@/components/chat/agent-selector";
import { MessageSquare } from "lucide-react";

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
    } else if (!projectConv && !currentConversation && activeProjectId) {
      createConversation(token, activeProjectId, "Workspace Chat");
    }
  }, [token, activeProjectId, conversations]);

  return (
    <div className="flex flex-col h-full">
      {/* Compact header with agent & usage info */}
      <div className="flex items-center justify-between px-2 py-1.5 border-b bg-muted/30 shrink-0">
        <div className="flex items-center gap-1.5">
          <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground">Chat</span>
        </div>
        <div className="flex items-center gap-1.5">
          <AgentBadge />
          <UsageBadge />
        </div>
      </div>

      {/* Messages */}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <MessageList />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t">
        <MessageInput />
      </div>
    </div>
  );
}
