"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useChat } from "@/hooks/useChat";
import { useVoice } from "@/hooks/useVoice";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Send, Paperclip, Mic, Square, Loader2, Hash, WifiOff } from "lucide-react";
import { CommandSuggestions, getFilteredCommands, Command } from "./command-suggestions";

export function MessageInput() {
  const [message, setMessage] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const [commandFilter, setCommandFilter] = useState("");
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { isSending, currentConversation } = useChatStore();
  const { sendMessage, isConnected } = useChat();
  const { isRecording, isProcessing, audioLevel, startRecording, stopRecording } = useVoice({
    onTranscription: (text) => {
      setMessage((prev) => prev + text);
    },
    onError: (error) => {
      console.error("Voice error:", error);
    },
  });

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [message]);

  // Handle message changes for command detection
  const handleMessageChange = useCallback((value: string) => {
    setMessage(value);

    // Check for slash command at start
    if (value.startsWith("/")) {
      const filter = value.slice(1).split(" ")[0];
      setCommandFilter(filter);
      setShowCommands(true);
      setSelectedCommandIndex(0);
    } else {
      setShowCommands(false);
      setCommandFilter("");
    }
  }, []);

  // Handle command selection
  const handleCommandSelect = useCallback((command: Command) => {
    setMessage(`/${command.name} `);
    setShowCommands(false);
    textareaRef.current?.focus();
  }, []);

  // Extract hashtags from message for display
  const extractHashtags = useCallback((text: string): string[] => {
    const pattern = /(?:^|\s)#([a-zA-Z][a-zA-Z0-9_-]{0,49})(?=\s|$|[.,!?])/g;
    const matches: string[] = [];
    let match;
    while ((match = pattern.exec(text)) !== null) {
      if (!matches.includes(match[1])) {
        matches.push(match[1]);
      }
    }
    return matches;
  }, []);

  const hashtags = extractHashtags(message);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isSending || !currentConversation) return;

    sendMessage(message.trim());
    setMessage("");
    setShowCommands(false);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Handle command navigation when suggestions are shown
    if (showCommands) {
      const filteredCommands = getFilteredCommands(commandFilter);

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedCommandIndex((prev) =>
          prev < filteredCommands.length - 1 ? prev + 1 : 0
        );
        return;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedCommandIndex((prev) =>
          prev > 0 ? prev - 1 : filteredCommands.length - 1
        );
        return;
      }

      if (e.key === "Tab" || (e.key === "Enter" && filteredCommands.length > 0)) {
        e.preventDefault();
        const selectedCommand = filteredCommands[selectedCommandIndex];
        if (selectedCommand) {
          handleCommandSelect(selectedCommand);
        }
        return;
      }

      if (e.key === "Escape") {
        e.preventDefault();
        setShowCommands(false);
        return;
      }
    }

    // Regular enter to submit
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleVoiceToggle = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const { connectionState } = useChatStore();
  const isDisabled = !currentConversation;
  const isOffline = !isConnected;

  return (
    <div className="border-t bg-card p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shrink-0">
      {/* Hashtag indicators */}
      {hashtags.length > 0 && (
        <div className="flex items-center gap-2 mb-2 text-xs">
          <Hash className="h-3 w-3 text-primary" />
          <span className="text-muted-foreground">Will save to memory with tags:</span>
          {hashtags.map((tag) => (
            <span key={tag} className="bg-primary/10 text-primary px-2 py-0.5 rounded-full">
              #{tag}
            </span>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex items-end gap-2 max-w-full">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="shrink-0"
          disabled={isDisabled}
        >
          <Paperclip className="h-5 w-5" />
        </Button>

        <div className="relative flex-1">
          {/* Command suggestions dropdown */}
          {showCommands && (
            <CommandSuggestions
              filter={commandFilter}
              onSelect={handleCommandSelect}
              onClose={() => setShowCommands(false)}
              selectedIndex={selectedCommandIndex}
            />
          )}

          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => handleMessageChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isDisabled
                ? "Select a conversation to start"
                : isOffline
                ? "Messages will be sent when reconnected..."
                : "Type / for commands or # to tag memory..."
            }
            disabled={isDisabled}
            rows={1}
            className={cn(
              "w-full resize-none rounded-lg border bg-background px-3 py-2 text-base",
              "focus:outline-none focus:ring-2 focus:ring-ring",
              "placeholder:text-muted-foreground",
              "disabled:cursor-not-allowed disabled:opacity-50",
              "max-h-[120px]"
            )}
          />
        </div>

        <Button
          type="button"
          variant={isRecording ? "destructive" : "ghost"}
          size="icon"
          className={cn(
            "shrink-0 relative",
            isRecording && "animate-pulse"
          )}
          onClick={handleVoiceToggle}
          disabled={isDisabled || isProcessing}
        >
          {isProcessing ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : isRecording ? (
            <>
              <Square className="h-5 w-5" />
              {/* Audio level indicator */}
              <div
                className="absolute inset-0 rounded-md bg-destructive/20"
                style={{ transform: `scale(${1 + audioLevel * 0.5})` }}
              />
            </>
          ) : (
            <Mic className="h-5 w-5" />
          )}
        </Button>

        <Button
          type="submit"
          size="icon"
          className="shrink-0"
          disabled={!message.trim() || isSending || isDisabled}
        >
          {isSending ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Send className="h-5 w-5" />
          )}
        </Button>
      </form>

      {isOffline && connectionState !== "connected" && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-yellow-600 dark:text-yellow-500">
          <WifiOff className="h-3 w-3" />
          <span>
            {connectionState === "reconnecting"
              ? "Reconnecting... Messages will be queued."
              : "Disconnected. Messages will be sent when reconnected."}
          </span>
        </div>
      )}
    </div>
  );
}
