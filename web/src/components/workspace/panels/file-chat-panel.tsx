"use client";

import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useChat } from "@/hooks/useChat";
import { MessageList } from "@/components/chat/message-list";
import { AgentStatus } from "@/components/chat/agent-status";
import { UsageBadge } from "@/components/chat/usage-meter";
import { AgentBadge } from "@/components/chat/agent-selector";
import { Button } from "@/components/ui/button";
import { Send, FileCode, MessageSquare, ChevronDown, X, Plus, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProjectStore } from "@/stores/project-store";

function getLanguageFromPath(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  const langMap: Record<string, string> = {
    ts: "TypeScript",
    tsx: "TypeScript React",
    js: "JavaScript",
    jsx: "JavaScript React",
    py: "Python",
    html: "HTML",
    css: "CSS",
    scss: "SCSS",
    json: "JSON",
    md: "Markdown",
    yaml: "YAML",
    yml: "YAML",
    sql: "SQL",
    sh: "Shell",
    bash: "Shell",
    rs: "Rust",
    go: "Go",
    java: "Java",
    rb: "Ruby",
    php: "PHP",
  };
  return langMap[ext] || ext.toUpperCase();
}

export function FileChatPanel() {
  const { token } = useAuthStore();
  const {
    currentConversation,
    createConversation,
    conversations,
    selectConversation,
    fetchConversations,
    messages,
    isSending,
  } = useChatStore();
  const { selectedProject } = useProjectStore();
  const { activeFilePath, openFiles, setFileChatExpanded } = useWorkspaceStore();
  const [input, setInput] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage } = useChat();

  const projectId = selectedProject?.id;

  // Ensure we have conversations loaded
  useEffect(() => {
    if (token && conversations.length === 0) {
      fetchConversations(token);
    }
  }, [token]);

  // Find existing file-assistant conversation for this project (but don't auto-create)
  useEffect(() => {
    if (!token || !projectId) return;

    const fileAssistantConv = conversations.find(
      (c) =>
        c.project_id === projectId &&
        c.title === "File Assistant" &&
        c.status === "ACTIVE"
    );

    // Only auto-select if we found an existing one
    if (fileAssistantConv && fileAssistantConv.id !== currentConversation?.id) {
      selectConversation(token, fileAssistantConv.id);
    }
  }, [token, projectId, conversations]);

  // Handle starting a new chat
  const handleStartChat = async () => {
    if (!token || !projectId || isCreating) return;
    setIsCreating(true);
    try {
      await createConversation(token, projectId, "File Assistant");
    } finally {
      setIsCreating(false);
    }
  };

  // Check if we have an active conversation for this project
  const hasActiveConversation = currentConversation && currentConversation.project_id === projectId;

  const activeFile = openFiles.find((f) => f.path === activeFilePath);
  const fileName = activeFilePath?.split("/").pop() || "No file";
  const language = activeFilePath ? getLanguageFromPath(activeFilePath) : "";

  const handleSend = () => {
    if (!input.trim() || !currentConversation || isSending) return;

    // Inject file context into message
    let contextualMessage = input.trim();
    if (activeFilePath && activeFile) {
      const fileContext = `[File: ${activeFilePath} (${language})]\n\`\`\`${language.toLowerCase()}\n${activeFile.content.slice(0, 3000)}\n\`\`\`\n\n`;
      contextualMessage = fileContext + contextualMessage;
    }

    sendMessage(contextualMessage);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full border-t bg-card">
      {/* Header with title, badges, and collapse */}
      <div className="flex items-center justify-between px-2 py-1 border-b bg-muted/30 shrink-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <MessageSquare className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-xs font-medium truncate">File Assistant</span>
          {activeFilePath && (
            <span className="text-[10px] text-muted-foreground truncate hidden sm:inline">
              • {fileName}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <AgentBadge />
          <UsageBadge />
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5"
            onClick={() => setFileChatExpanded(false)}
            title="Collapse chat"
          >
            <ChevronDown className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* File context indicator */}
      {activeFilePath && (
        <div className="flex items-center gap-1.5 px-2 py-1 bg-muted/50 border-b shrink-0">
          <FileCode className="h-3 w-3 text-muted-foreground" />
          <span className="text-[10px] text-muted-foreground truncate">
            Context: <span className="font-medium text-foreground">{fileName}</span>
            {language && <span className="ml-1 opacity-60">({language})</span>}
          </span>
        </div>
      )}

      {/* Show start chat prompt if no conversation */}
      {!hasActiveConversation ? (
        <div className="flex-1 flex flex-col items-center justify-center p-4 text-center">
          <div className="rounded-full bg-muted p-3 mb-3">
            <Sparkles className="h-6 w-6 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium mb-1">File Assistant</h3>
          <p className="text-xs text-muted-foreground mb-4 max-w-[200px]">
            Get help understanding, modifying, or discussing your code
          </p>
          <Button
            size="sm"
            onClick={handleStartChat}
            disabled={isCreating || !projectId}
            className="gap-1.5"
          >
            {isCreating ? (
              <>Starting...</>
            ) : (
              <>
                <Plus className="h-3.5 w-3.5" />
                Start Chat
              </>
            )}
          </Button>
        </div>
      ) : (
        <>
          {/* Agent Status */}
          <AgentStatus />

          {/* Messages */}
          <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
            <MessageList />
          </div>

          {/* Input */}
          <div className="border-t p-2 shrink-0">
            <div className="flex gap-1.5">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={activeFilePath ? `Ask about ${fileName}...` : "Select a file..."}
                disabled={!currentConversation || isSending}
                rows={1}
                className={cn(
                  "flex-1 resize-none rounded-md border bg-background px-2 py-1.5 text-xs",
                  "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary",
                  "min-h-[28px] max-h-[80px]"
                )}
              />
              <Button
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={handleSend}
                disabled={!input.trim() || !currentConversation || isSending}
              >
                <Send className="h-3 w-3" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
