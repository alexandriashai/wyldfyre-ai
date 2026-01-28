"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useProjectStore } from "@/stores/project-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { MessageList } from "@/components/chat/message-list";
import { MessageInput } from "@/components/chat/message-input";
import { AgentStatus } from "@/components/chat/agent-status";
import { TaskControls } from "@/components/chat/task-controls";
import { PlanPanel } from "@/components/chat/plan-panel";
import { RollbackControls } from "@/components/chat/rollback-controls";
import { ActiveTasksPanel } from "@/components/chat/active-tasks-panel";
import { PlanSuggestionBanner } from "@/components/chat/plan-suggestion-banner";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { UsageMeter } from "@/components/chat/usage-meter";
import { AgentSelector } from "@/components/chat/agent-selector";
import { AIDiffEditor, AIChangesNotification } from "@/components/workspace/editor/ai-diff-editor";
import { Button } from "@/components/ui/button";
import { Loader2, PanelLeft, Sparkles, GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";

const SIDEBAR_MIN_WIDTH = 200;
const SIDEBAR_MAX_WIDTH = 500;
const SIDEBAR_DEFAULT_WIDTH = 280;
const SIDEBAR_STORAGE_KEY = "chat-sidebar-width";

export default function WorkspaceChatsPage() {
  const { token } = useAuthStore();
  const {
    currentConversation,
    fetchConversations,
    selectConversation,
    createConversation,
    conversations,
    currentPlan,
    currentPlanId,
    pendingFileChanges,
    acceptFileChange,
    rejectFileChange,
    clearFileChangePreviews,
    lastRollbackResult,
  } = useChatStore();
  const { selectedProject } = useProjectStore();
  const { isChatSidebarCollapsed, setChatSidebarCollapsed, openFile, setActiveFile } = useWorkspaceStore();
  const [isInitializing, setIsInitializing] = useState(true);
  const [showDiffPanel, setShowDiffPanel] = useState(false);

  // Resizable sidebar state
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<HTMLDivElement>(null);

  // Load saved width on mount
  useEffect(() => {
    const saved = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (saved) {
      const width = parseInt(saved, 10);
      if (width >= SIDEBAR_MIN_WIDTH && width <= SIDEBAR_MAX_WIDTH) {
        setSidebarWidth(width);
      }
    }
  }, []);

  // Handle resize
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = Math.min(
        SIDEBAR_MAX_WIDTH,
        Math.max(SIDEBAR_MIN_WIDTH, e.clientX)
      );
      setSidebarWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      localStorage.setItem(SIDEBAR_STORAGE_KEY, sidebarWidth.toString());
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, sidebarWidth]);

  // AI Diff handlers
  const handleAcceptChange = useCallback((changeId: string) => {
    acceptFileChange(changeId);
  }, [acceptFileChange]);

  const handleRejectChange = useCallback((changeId: string) => {
    rejectFileChange(changeId);
  }, [rejectFileChange]);

  const handleAcceptAll = useCallback(() => {
    pendingFileChanges.forEach((change) => acceptFileChange(change.id));
  }, [pendingFileChanges, acceptFileChange]);

  const handleRejectAll = useCallback(() => {
    clearFileChangePreviews();
    setShowDiffPanel(false);
  }, [clearFileChangePreviews]);

  const handleOpenInEditor = useCallback((path: string) => {
    const change = pendingFileChanges.find((c) => c.path === path);
    if (change) {
      openFile({
        path: change.path,
        content: change.after,
        originalContent: change.before,
        language: change.language || null,
        isDirty: true,
      });
      setActiveFile(change.path);
    }
  }, [pendingFileChanges, openFile, setActiveFile]);

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
    <div className={cn(
      "flex h-full w-full min-h-0 overflow-hidden",
      isResizing && "select-none cursor-col-resize"
    )}>
      {/* Left: Conversation sidebar with tag filtering */}
      {/* On mobile, completely hide when collapsed; on desktop, show narrow version */}
      <div
        className={cn(
          "relative shrink-0",
          isChatSidebarCollapsed ? "hidden md:block" : ""
        )}
        style={{ width: isChatSidebarCollapsed ? undefined : sidebarWidth }}
      >
        <ConversationSidebar
          projectId={selectedProject?.id}
          isCollapsed={isChatSidebarCollapsed}
          onToggle={handleToggleSidebar}
          width={sidebarWidth}
        />

        {/* Resize handle */}
        {!isChatSidebarCollapsed && (
          <div
            ref={resizeRef}
            className={cn(
              "absolute top-0 right-0 w-1 h-full cursor-col-resize group hidden md:flex items-center justify-center",
              "hover:bg-primary/20 transition-colors",
              isResizing && "bg-primary/30"
            )}
            onMouseDown={handleMouseDown}
          >
            <div className={cn(
              "absolute right-0 w-3 h-full",
              "flex items-center justify-center"
            )}>
              <GripVertical className={cn(
                "h-4 w-4 text-muted-foreground/50 opacity-0 group-hover:opacity-100 transition-opacity",
                isResizing && "opacity-100"
              )} />
            </div>
          </div>
        )}
      </div>

      {/* Right: Full chat experience */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
        {/* Mobile header with sidebar toggle, agent selector, and usage */}
        {isChatSidebarCollapsed && (
          <div className="md:hidden flex items-center gap-2 px-2 py-1.5 border-b shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={handleToggleSidebar}
              title="Show conversations"
            >
              <PanelLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium truncate flex-1 min-w-0">
              {currentConversation?.title || "Chat"}
            </span>
            <AgentSelector variant="compact" />
            <UsageMeter variant="compact" />
          </div>
        )}

        {/* Desktop header bar with agent selector and usage */}
        <div className="hidden md:flex items-center justify-between px-3 py-1.5 border-b bg-muted/30 shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-500" />
            <span className="text-sm font-medium">
              {currentConversation?.title || "Chat"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <AgentSelector variant="compact" />
            <UsageMeter variant="compact" />
          </div>
        </div>

        {/* AI Changes notification banner */}
        {pendingFileChanges.length > 0 && !showDiffPanel && (
          <AIChangesNotification
            count={pendingFileChanges.length}
            onClick={() => setShowDiffPanel(true)}
          />
        )}
        <AgentStatus />
        <TaskControls />
        {currentPlan && <PlanPanel />}
        {/* Active task tracking - show when there are tracked tasks (non-plan mode) */}
        {!currentPlan && <ActiveTasksPanel />}
        {/* Plan suggestion banner - show when supervisor suggests entering plan mode */}
        <PlanSuggestionBanner />
        {/* Rollback controls - show when there's rollback data available */}
        {(currentPlanId || lastRollbackResult) && !currentPlan && (
          <div className="px-4 py-2 border-b bg-muted/30">
            <RollbackControls
              planId={currentPlanId || lastRollbackResult?.planId}
              className="w-full"
            />
          </div>
        )}

        {/* Main content area - either chat or diff panel */}
        {showDiffPanel && pendingFileChanges.length > 0 ? (
          <AIDiffEditor
            changes={pendingFileChanges}
            onAccept={handleAcceptChange}
            onReject={handleRejectChange}
            onAcceptAll={handleAcceptAll}
            onRejectAll={handleRejectAll}
            onOpenInEditor={handleOpenInEditor}
            onClose={() => setShowDiffPanel(false)}
            className="flex-1 min-h-0"
          />
        ) : (
          <>
            <MessageList />
            <MessageInput />
          </>
        )}
      </div>
    </div>
  );
}
