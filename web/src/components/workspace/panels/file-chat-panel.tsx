"use client";

import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useChat } from "@/hooks/useChat";
import { MessageList } from "@/components/chat/message-list";
import { AgentStatus } from "@/components/chat/agent-status";
import { Button } from "@/components/ui/button";
import { Send, FileCode } from "lucide-react";
import { cn } from "@/lib/utils";

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
    messages,
    isSending,
  } = useChatStore();
  const { activeFilePath, openFiles, activeProjectId } = useWorkspaceStore();
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage } = useChat();

  // Find or create a file-assistant conversation for this project
  useEffect(() => {
    if (!token || !activeProjectId) return;

    const fileAssistantConv = conversations.find(
      (c) =>
        c.project_id === activeProjectId &&
        c.title === "File Assistant" &&
        c.status === "ACTIVE"
    );

    if (fileAssistantConv && fileAssistantConv.id !== currentConversation?.id) {
      selectConversation(token, fileAssistantConv.id);
    } else if (!fileAssistantConv && activeProjectId) {
      createConversation(token, activeProjectId, "File Assistant");
    }
  }, [token, activeProjectId]);

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
    <div className="flex flex-col h-full">
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

      {/* Agent Status */}
      <AgentStatus />

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-hidden">
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
    </div>
  );
}
