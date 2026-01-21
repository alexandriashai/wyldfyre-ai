"use client";

import { useEffect, useRef, useState } from "react";
import { useAgentStore } from "@/stores/agent-store";
import { cn, getAgentColor } from "@/lib/utils";
import {
  Brain,
  Wrench,
  CheckCircle2,
  XCircle,
  FileText,
  PenLine,
  Search,
  Send,
  Clock,
  Download,
  Globe,
  MessageSquare,
  Database,
  HardDrive,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

// Action type to icon mapping
const ACTION_ICONS: Record<string, React.ReactNode> = {
  thinking: <Brain className="h-3.5 w-3.5" />,
  tool_call: <Wrench className="h-3.5 w-3.5" />,
  tool_result: <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />,
  tool_error: <XCircle className="h-3.5 w-3.5 text-red-500" />,
  file_read: <FileText className="h-3.5 w-3.5" />,
  file_write: <PenLine className="h-3.5 w-3.5" />,
  file_search: <Search className="h-3.5 w-3.5" />,
  delegating: <Send className="h-3.5 w-3.5 text-blue-500" />,
  waiting: <Clock className="h-3.5 w-3.5 text-yellow-500" />,
  received: <Download className="h-3.5 w-3.5 text-green-500" />,
  api_call: <Globe className="h-3.5 w-3.5" />,
  api_response: <MessageSquare className="h-3.5 w-3.5" />,
  memory_search: <Database className="h-3.5 w-3.5" />,
  memory_store: <HardDrive className="h-3.5 w-3.5" />,
  complete: <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />,
  error: <XCircle className="h-3.5 w-3.5 text-red-500" />,
};

// Get icon for action type, with fallback
function getActionIcon(action: string): React.ReactNode {
  return ACTION_ICONS[action] || <Wrench className="h-3.5 w-3.5" />;
}

// Format timestamp to HH:MM:SS
function formatTime(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "--:--:--";
  }
}

// Capitalize and format agent name
function formatAgentName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function AgentStatus() {
  const { agents, actionLog } = useAgentStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  // Find busy agents
  const busyAgents = agents.filter((agent) => agent.status === "busy");
  const hasActivity = actionLog.length > 0 || busyAgents.length > 0;

  // Auto-scroll to bottom when new actions arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [actionLog, autoScroll]);

  // Handle manual scroll to detect if user scrolled up
  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 30;
      setAutoScroll(isAtBottom);
    }
  };

  if (!hasActivity) {
    return null;
  }

  return (
    <div className="border-b bg-muted/30 shrink-0">
      {/* Header with collapse toggle */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">
            Agent Activity
          </span>
          {busyAgents.length > 0 && (
            <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full">
              {busyAgents.length} active
            </span>
          )}
        </div>
        {isCollapsed ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {/* Action log */}
      {!isCollapsed && (
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="max-h-32 sm:max-h-48 overflow-y-auto px-4 pb-2 space-y-1 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent"
        >
          {actionLog.length === 0 ? (
            // Show busy agents when no actions yet
            <div className="text-xs text-muted-foreground py-2">
              {busyAgents.map((agent) => (
                <div key={agent.name} className="flex items-center gap-2">
                  <span className="animate-pulse">...</span>
                  <span className={cn("font-medium", getAgentColor(agent.name))}>
                    {formatAgentName(agent.name)}
                  </span>
                  <span>is working</span>
                </div>
              ))}
            </div>
          ) : (
            // Show action log
            actionLog.map((action) => (
              <div
                key={action.id}
                className="flex items-start gap-2 text-xs font-mono group"
              >
                {/* Timestamp */}
                <span className="text-muted-foreground/70 shrink-0">
                  {formatTime(action.timestamp)}
                </span>

                {/* Icon */}
                <span className="shrink-0 mt-0.5">{getActionIcon(action.action)}</span>

                {/* Agent name */}
                <span
                  className={cn(
                    "font-medium shrink-0",
                    getAgentColor(action.agent)
                  )}
                >
                  {formatAgentName(action.agent)}
                </span>

                {/* Description */}
                <span className="text-foreground/80 truncate group-hover:text-clip group-hover:whitespace-normal">
                  {action.description}
                </span>
              </div>
            ))
          )}

          {/* Auto-scroll indicator */}
          {!autoScroll && actionLog.length > 5 && (
            <button
              onClick={() => {
                setAutoScroll(true);
                if (scrollRef.current) {
                  scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                }
              }}
              className="sticky bottom-0 w-full text-center py-1 text-xs text-primary bg-muted/90 hover:bg-muted rounded"
            >
              Scroll to bottom
            </button>
          )}
        </div>
      )}
    </div>
  );
}
