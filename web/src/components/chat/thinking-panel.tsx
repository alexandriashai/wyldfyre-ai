"use client";

import { useEffect, useRef, useState } from "react";
import { useChatStore, ThinkingEntry, ThoughtType } from "@/stores/chat-store";
import { cn, getAgentColor } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Brain,
  GitBranch,
  Search,
  Lightbulb,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

function formatTime(timestamp: string): string {
  try {
    if (!timestamp) return "--:--:--";
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "--:--:--";
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

function formatAgentName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getThoughtIcon(type: ThoughtType): React.ReactNode {
  switch (type) {
    case "reasoning":
      return <Brain className="h-3.5 w-3.5 text-amber-500" />;
    case "decision":
      return <GitBranch className="h-3.5 w-3.5 text-purple-500" />;
    case "analysis":
      return <Search className="h-3.5 w-3.5 text-blue-500" />;
    case "observation":
      return <Lightbulb className="h-3.5 w-3.5 text-green-500" />;
    default:
      return <Brain className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

function getThoughtBadgeColor(type: ThoughtType): string {
  switch (type) {
    case "reasoning":
      return "bg-amber-500/10 text-amber-500 border-amber-500/20";
    case "decision":
      return "bg-purple-500/10 text-purple-500 border-purple-500/20";
    case "analysis":
      return "bg-blue-500/10 text-blue-500 border-blue-500/20";
    case "observation":
      return "bg-green-500/10 text-green-500 border-green-500/20";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function getTimelineDotColor(type: ThoughtType): string {
  switch (type) {
    case "reasoning":
      return "bg-amber-500";
    case "decision":
      return "bg-purple-500";
    case "analysis":
      return "bg-blue-500";
    case "observation":
      return "bg-green-500";
    default:
      return "bg-muted-foreground/50";
  }
}

interface ThinkingItemProps {
  entry: ThinkingEntry;
}

function ThinkingItem({ entry }: ThinkingItemProps) {
  const [expanded, setExpanded] = useState(false);
  const hasContext = entry.context && Object.keys(entry.context).length > 0;

  return (
    <div className="relative pl-5 py-1 group">
      {/* Timeline dot */}
      <div
        className={cn(
          "absolute left-[3px] top-[12px] w-1.5 h-1.5 rounded-full",
          getTimelineDotColor(entry.type)
        )}
      />

      <div className="flex items-start gap-1.5 min-w-0">
        <span className="shrink-0 mt-0.5">{getThoughtIcon(entry.type)}</span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
            <Badge
              variant="outline"
              className={cn(
                "text-[9px] h-4 px-1.5 font-medium capitalize",
                getThoughtBadgeColor(entry.type)
              )}
            >
              {entry.type}
            </Badge>
            <span className={cn("text-xs font-medium shrink-0", getAgentColor(entry.agent))}>
              {formatAgentName(entry.agent)}
            </span>
            <span className="text-[10px] text-muted-foreground/60 shrink-0">
              {formatTime(entry.timestamp)}
            </span>
          </div>

          <p className="text-xs text-foreground/90 leading-relaxed whitespace-pre-wrap">
            {entry.content}
          </p>

          {/* Context badges */}
          {hasContext && (
            <div className="mt-1 flex flex-wrap gap-1">
              <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-0.5 text-[10px] text-muted-foreground hover:text-foreground"
              >
                {expanded ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
                Context
              </button>
              {!expanded &&
                Object.keys(entry.context!).slice(0, 3).map((key) => (
                  <Badge
                    key={key}
                    variant="secondary"
                    className="text-[9px] h-4 px-1.5"
                  >
                    {key}
                  </Badge>
                ))}
              {!expanded && Object.keys(entry.context!).length > 3 && (
                <span className="text-[9px] text-muted-foreground">
                  +{Object.keys(entry.context!).length - 3} more
                </span>
              )}
            </div>
          )}

          {/* Expanded context */}
          {expanded && entry.context && (
            <pre className="mt-1 text-[10px] text-muted-foreground bg-muted/50 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap break-all border">
              {JSON.stringify(entry.context, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

export function ThinkingPanel() {
  const { thinkingEntries } = useChatStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll to latest entry
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thinkingEntries, autoScroll]);

  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      setAutoScroll(scrollHeight - scrollTop - clientHeight < 30);
    }
  };

  if (thinkingEntries.length === 0) {
    return (
      <div className="flex items-center justify-center py-4 text-xs text-muted-foreground">
        No thinking entries yet
      </div>
    );
  }

  return (
    <div className="relative">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="max-h-28 sm:max-h-40 overflow-y-auto"
      >
        {/* Timeline line */}
        <div className="border-l border-border/40 ml-[6px]">
          {thinkingEntries.map((entry) => (
            <ThinkingItem key={entry.id} entry={entry} />
          ))}
        </div>
      </div>

      {!autoScroll && thinkingEntries.length > 3 && (
        <button
          onClick={() => {
            setAutoScroll(true);
            if (scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          }}
          className="sticky bottom-0 w-full text-center py-1 text-xs text-primary bg-card/90 hover:bg-muted rounded border-t"
        >
          Scroll to latest
        </button>
      )}
    </div>
  );
}
