"use client";

import { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { useChatStore } from "@/stores/chat-store";
import { useAgentStore } from "@/stores/agent-store";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Pause,
  Play,
  Square,
  MessageSquarePlus,
  Send,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface TaskControlsProps {
  className?: string;
}

export function TaskControls({ className }: TaskControlsProps) {
  const { isSending } = useChatStore();
  const { agents, actionLog } = useAgentStore();
  const { pauseTask, resumeTask, cancelTask, addMessageWhileBusy } = useChat();

  const [isPaused, setIsPaused] = useState(false);
  const [showAddMessage, setShowAddMessage] = useState(false);
  const [additionalMessage, setAdditionalMessage] = useState("");

  // Check if any agent is busy
  const busyAgents = agents.filter((agent) => agent.status === "busy");
  const isAgentWorking = busyAgents.length > 0 || isSending;

  // Get the latest action description
  const latestAction = actionLog.length > 0 ? actionLog[actionLog.length - 1] : null;
  const statusText = latestAction?.description || "Working...";

  if (!isAgentWorking) {
    return null;
  }

  const handlePauseResume = () => {
    if (isPaused) {
      resumeTask();
      setIsPaused(false);
    } else {
      pauseTask();
      setIsPaused(true);
    }
  };

  const handleCancel = () => {
    cancelTask();
    setIsPaused(false);
  };

  const handleAddMessage = () => {
    if (additionalMessage.trim()) {
      addMessageWhileBusy(additionalMessage.trim());
      setAdditionalMessage("");
      setShowAddMessage(false);
    }
  };

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 sm:px-4 py-2 bg-muted/50 border-b flex-wrap",
        className
      )}
    >
      <span className="text-xs text-muted-foreground mr-1 sm:mr-2 truncate max-w-[120px] sm:max-w-[200px] md:max-w-none">
        {statusText}
      </span>

      {/* Pause/Resume button */}
      <Button
        variant="outline"
        size="sm"
        onClick={handlePauseResume}
        className="h-7 px-2"
      >
        {isPaused ? (
          <>
            <Play className="h-3.5 w-3.5 sm:mr-1" />
            <span className="hidden sm:inline">Resume</span>
          </>
        ) : (
          <>
            <Pause className="h-3.5 w-3.5 sm:mr-1" />
            <span className="hidden sm:inline">Pause</span>
          </>
        )}
      </Button>

      {/* Cancel button */}
      <Button
        variant="outline"
        size="sm"
        onClick={handleCancel}
        className="h-7 px-2 text-destructive hover:text-destructive"
      >
        <Square className="h-3.5 w-3.5 sm:mr-1" />
        <span className="hidden sm:inline">Stop</span>
      </Button>

      {/* Add message button */}
      <Popover open={showAddMessage} onOpenChange={setShowAddMessage}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-7 px-2">
            <MessageSquarePlus className="h-3.5 w-3.5 sm:mr-1" />
            <span className="hidden sm:inline">Add Context</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80" align="start">
          <div className="space-y-2">
            <p className="text-sm font-medium">Add additional context</p>
            <p className="text-xs text-muted-foreground">
              Send additional instructions or context while the agent is working.
            </p>
            <Textarea
              placeholder="Type additional instructions..."
              value={additionalMessage}
              onChange={(e) => setAdditionalMessage(e.target.value)}
              className="min-h-[80px]"
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAddMessage(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleAddMessage}
                disabled={!additionalMessage.trim()}
              >
                <Send className="h-3.5 w-3.5 mr-1" />
                Send
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>

      {isPaused && (
        <span className="text-xs text-yellow-600 dark:text-yellow-400 ml-2">
          Paused
        </span>
      )}
    </div>
  );
}
