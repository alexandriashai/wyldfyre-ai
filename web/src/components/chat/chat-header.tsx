"use client";

import { useChatStore } from "@/stores/chat-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  FileCode,
  X,
  Link2,
  Unlink2,
  MoreVertical,
  Pause,
  Play,
  Square,
  Settings,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AgentSelector, AgentBadge } from "./agent-selector";
import { UsageMeter } from "./usage-meter";

interface ChatHeaderProps {
  className?: string;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  isPaused?: boolean;
  isExecuting?: boolean;
}

export function ChatHeader({
  className,
  onPause,
  onResume,
  onCancel,
  isPaused = false,
  isExecuting = false,
}: ChatHeaderProps) {
  const { currentConversation, isSending, activeAgent } = useChatStore();
  const { activeFile, openFiles, linkedFile, setLinkedFile } = useWorkspaceStore();

  // Get the currently active or linked file
  const contextFile = linkedFile || activeFile;
  const fileName = contextFile?.split("/").pop();

  // Handle linking/unlinking file to chat
  const handleToggleLink = () => {
    if (linkedFile) {
      setLinkedFile(null);
    } else if (activeFile) {
      setLinkedFile(activeFile);
    }
  };

  return (
    <div className={cn(
      "flex items-center justify-between gap-2 px-3 py-2 border-b bg-card shrink-0",
      className
    )}>
      {/* Left section - Agent selector and file context */}
      <div className="flex items-center gap-2 min-w-0 flex-1">
        {/* Agent selector - compact on mobile */}
        <AgentSelector variant="compact" className="shrink-0" />

        {/* File context indicator */}
        {contextFile && (
          <div className="flex items-center gap-1 min-w-0">
            <Badge
              variant="outline"
              className={cn(
                "h-6 px-2 gap-1 max-w-[140px] sm:max-w-[200px]",
                linkedFile && "border-primary/50 bg-primary/5"
              )}
            >
              <FileCode className="h-3 w-3 shrink-0" />
              <span className="truncate text-xs font-mono">{fileName}</span>
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 shrink-0"
              onClick={handleToggleLink}
              title={linkedFile ? "Unlink file from chat" : "Link file to chat"}
            >
              {linkedFile ? (
                <Unlink2 className="h-3 w-3 text-primary" />
              ) : (
                <Link2 className="h-3 w-3 text-muted-foreground" />
              )}
            </Button>
          </div>
        )}
      </div>

      {/* Right section - Usage meter and controls */}
      <div className="flex items-center gap-1 shrink-0">
        {/* Usage meter - hidden on mobile when executing */}
        <div className={cn(isExecuting && "hidden sm:block")}>
          <UsageMeter variant="compact" />
        </div>

        {/* Execution controls */}
        {isExecuting && (
          <div className="flex items-center gap-0.5 ml-1">
            {isPaused ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-green-600"
                onClick={onResume}
              >
                <Play className="h-3.5 w-3.5 mr-1" />
                <span className="hidden sm:inline">Resume</span>
              </Button>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-amber-600"
                onClick={onPause}
              >
                <Pause className="h-3.5 w-3.5 mr-1" />
                <span className="hidden sm:inline">Pause</span>
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-red-600"
              onClick={onCancel}
            >
              <Square className="h-3.5 w-3.5 mr-1" />
              <span className="hidden sm:inline">Cancel</span>
            </Button>
          </div>
        )}

        {/* More options menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => useChatStore.getState().clearPlan()}>
              Clear Plan
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => useChatStore.getState().clearSupervisorThoughts()}>
              Clear Activity
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <Settings className="h-4 w-4 mr-2" />
              Chat Settings
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

// Minimal header for mobile/embedded view
export function ChatHeaderMinimal({ className }: { className?: string }) {
  return (
    <div className={cn(
      "flex items-center justify-between gap-2 px-3 py-1.5 border-b bg-card/50",
      className
    )}>
      <AgentBadge />
      <UsageMeter variant="compact" />
    </div>
  );
}
