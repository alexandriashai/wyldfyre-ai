"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useProjectStore } from "@/stores/project-store";
import { MessageList } from "@/components/chat/message-list";
import { MessageInput } from "@/components/chat/message-input";
import { AgentStatus } from "@/components/chat/agent-status";
import { TaskControls } from "@/components/chat/task-controls";
import { PlanPanel } from "@/components/chat/plan-panel";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { Loader2 } from "lucide-react";

export default function ChatPage() {
  const { token } = useAuthStore();
  const {
    currentConversation,
    fetchConversations,
    selectConversation,
    createConversation,
    conversations,
    currentPlan,
  } = useChatStore();
  const { selectedProject } = useProjectStore();
  const [isInitializing, setIsInitializing] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    const initializeChat = async () => {
      if (!token) return;

      try {
        // Fetch existing conversations (optionally filtered by project)
        await fetchConversations(token, selectedProject?.id);

        const state = useChatStore.getState();

        if (state.conversations.length > 0) {
          // Use the most recent conversation
          await selectConversation(token, state.conversations[0].id);
        } else {
          // Create a new conversation
          await createConversation(token, "Chat with Wyld", selectedProject?.id);
        }
      } catch (error) {
        console.error("Failed to initialize chat:", error);
      } finally {
        setIsInitializing(false);
      }
    };

    initializeChat();
  }, [token, fetchConversations, selectConversation, createConversation, selectedProject?.id]);

  // Handle when current conversation is deleted - select another or create new
  useEffect(() => {
    const handleMissingConversation = async () => {
      if (!token || isInitializing) return;
      if (currentConversation) return; // We have a conversation, nothing to do

      // No current conversation - try to select first available or create new
      if (conversations.length > 0) {
        await selectConversation(token, conversations[0].id);
      } else {
        await createConversation(token, "Chat with Wyld", selectedProject?.id);
      }
    };

    handleMissingConversation();
  }, [token, currentConversation, conversations, isInitializing, selectConversation, createConversation, selectedProject?.id]);

  if (isInitializing) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex h-full w-full min-h-0 overflow-hidden">
      {/* Conversation Sidebar - hidden on mobile, visible on md+ */}
      <div className="hidden md:block h-full">
        <ConversationSidebar
          isCollapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 h-full min-w-0 overflow-hidden">
        <AgentStatus />
        <TaskControls />
        {currentPlan && <PlanPanel />}
        <MessageList />
        <MessageInput />
      </div>
    </div>
  );
}
