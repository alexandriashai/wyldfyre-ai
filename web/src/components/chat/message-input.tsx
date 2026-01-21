"use client";

import { useState, useRef, useEffect } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useChat } from "@/hooks/useChat";
import { useVoice } from "@/hooks/useVoice";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Send, Paperclip, Mic, Square, Loader2 } from "lucide-react";

export function MessageInput() {
  const [message, setMessage] = useState("");
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isSending || !currentConversation) return;

    sendMessage(message.trim());
    setMessage("");

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
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

  const isDisabled = !isConnected || !currentConversation;

  return (
    <div className="border-t bg-card p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shrink-0">
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
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isDisabled
                ? "Select a conversation to start"
                : "Type your message..."
            }
            disabled={isDisabled || isSending}
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

      {!isConnected && (
        <p className="mt-2 text-xs text-destructive">
          Disconnected from server. Reconnecting...
        </p>
      )}
    </div>
  );
}
