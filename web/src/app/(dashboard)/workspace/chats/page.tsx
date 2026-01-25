"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useProjectStore } from "@/stores/project-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { MessageList } from "@/components/chat/message-list";
import { MessageInput } from "@/components/chat/message-input";
import { AgentStatus } from "@/components/chat/agent-status";
import { TaskControls } from "@/components/chat/task-controls";
import { PlanPanel } from "@/components/chat/plan-panel";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { Button } from "@/components/ui/button";
import { Loader2, PanelLeft } from "lucide-react";

export default function WorkspaceChatsPage() {
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
  const { isChatSidebarCollapsed, setChatSidebarCollapsed } = useWorkspaceStore();
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    const initializeChat = async () => {
      if (!token || !selectedProject) return;

      try {
        await fetchConversations(token, selectedProject.id);

        const state = useChatStore.getState();

        if (state.conversations.length > 0) {
          await selectConversation(token, state.conversations[0].id);
        } else {
          await createConversation(token, selectedProject.id, "Chat with Wyld");
        }
      } catch (error) {
        console.error("Failed to initialize chat:", error);
      } finally {
        setIsInitializing(false);
      }
    };

    initializeChat();
  }, [token, fetchConversations, selectConversation, createConversation, selectedProject]);

  useEffect(() => {
    const handleMissingConversation = async () => {
      if (!token || !selectedProject || isInitializing) return;
      if (currentConversation) return;

      if (conversations.length > 0) {
        await selectConversation(token, conversations[0].id);
      } else {
        await createConversation(token, selectedProject.id, "Chat with Wyld");
      }
    };

    handleMissingConversation();
  }, [token, currentConversation, conversations, isInitializing, selectConversation, createConversation, selectedProject]);

  if (isInitializing) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const handleToggleSidebar = () => {
    setChatSidebarCollapsed(!isChatSidebarCollapsed);
  };

  return (
    <div className="flex h-full w-full min-h-0 overflow-hidden">
      {/* Left: Conversation sidebar with tag filtering */}
      {/* On mobile, completely hide when collapsed; on desktop, show narrow version */}
      <div className={isChatSidebarCollapsed ? "hidden md:block" : ""}>
        <ConversationSidebar
          projectId={selectedProject?.id}
          isCollapsed={isChatSidebarCollapsed}
          onToggle={handleToggleSidebar}
        />
      </div>

      {/* Right: Full chat experience */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
        {/* Mobile sidebar toggle button - only visible on mobile when sidebar is collapsed */}
        {isChatSidebarCollapsed && (
          <div className="md:hidden flex items-center gap-2 px-2 py-1.5 border-b shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={handleToggleSidebar}
              title="Show conversations"
            >
              <PanelLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium truncate">
              {currentConversation?.title || "Chat"}
            </span>
          </div>
        )}
        <AgentStatus />
        <TaskControls />
        {currentPlan && <PlanPanel />}
        <MessageList />
        <MessageInput />
      </div>
    </div>
  );
}
