"use client";

import { useEffect, useRef, useState } from "react";
import { useAgentStore, useActionGroups, useCurrentIteration, AgentAction, ActionGroup } from "@/stores/agent-store";
import { cn, getAgentColor } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Brain,
  Wrench,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Clock,
  Layers,
  Loader2,
  Info,
} from "lucide-react";

function formatDuration(ms?: number): string {
  if (!ms) return "";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

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

function formatAgentName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getActionIcon(action: AgentAction): React.ReactNode {
  const isRunning = action.status === "running";
  if (isRunning) return <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />;

  switch (action.type) {
    case "tool_call":
      return <Wrench className="h-3.5 w-3.5 text-blue-500" />;
    case "tool_result":
      return <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />;
    case "thinking":
      return <Brain className="h-3.5 w-3.5 text-amber-500" />;
    case "error":
      return <XCircle className="h-3.5 w-3.5 text-red-500" />;
    case "parallel":
      return <Layers className="h-3.5 w-3.5 text-purple-500" />;
    default:
      return <Info className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

function getTimelineDotColor(action: AgentAction): string {
  if (action.status === "running") return "bg-blue-500 animate-pulse";
  switch (action.type) {
    case "tool_call":
    case "tool_result":
      return action.status === "error" ? "bg-red-500" : "bg-green-500";
    case "thinking":
      return "bg-amber-500";
    case "error":
      return "bg-red-500";
    default:
      return "bg-muted-foreground/50";
  }
}

function ActionItem({ action }: { action: AgentAction }) {
  const [expanded, setExpanded] = useState(false);
  const hasOutput = action.output && action.output.length > 0;

  return (
    <div className="relative pl-5 py-0.5 group">
      {/* Timeline dot */}
      <div className={cn(
        "absolute left-[3px] top-[10px] w-1.5 h-1.5 rounded-full",
        getTimelineDotColor(action)
      )} />

      <div className="flex items-start gap-1.5 min-w-0">
        <span className="shrink-0 mt-0.5">
          {getActionIcon(action)}
        </span>

        <div className="flex-1 min-w-0">
          <div
            className={cn(
              "flex items-center gap-1.5",
              hasOutput && "cursor-pointer hover:bg-muted/30 rounded -mx-1 px-1"
            )}
            onClick={() => hasOutput && setExpanded(!expanded)}
          >
            <span className={cn(
              "text-xs font-medium shrink-0",
              getAgentColor(action.agent)
            )}>
              {formatAgentName(action.agent)}
            </span>
            <span className="text-xs text-foreground/80 truncate">
              {action.description}
            </span>
            {action.duration !== undefined && action.duration > 0 && (
              <span className="text-[10px] text-muted-foreground shrink-0 flex items-center gap-0.5">
                <Clock className="h-2.5 w-2.5" />
                {formatDuration(action.duration)}
              </span>
            )}
            {hasOutput && (
              <span className="shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </span>
            )}
          </div>

          {expanded && action.output && (
            <pre className="mt-1 text-[10px] text-muted-foreground bg-muted/50 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap break-all border">
              {action.output.length > 500
                ? action.output.slice(0, 500) + "\n... (truncated)"
                : action.output}
            </pre>
          )}
        </div>

        <span className="text-[10px] text-muted-foreground/60 shrink-0 mt-0.5">
          {formatTime(action.timestamp)}
        </span>
      </div>
    </div>
  );
}

function IterationHeader({ iteration, group }: { iteration: number; group: ActionGroup }) {
  return (
    <div className="flex items-center gap-2 py-1 mt-1">
      <div className="h-px flex-1 bg-border" />
      <span className="text-[10px] font-medium text-muted-foreground px-1">
        Iteration {iteration}
      </span>
      {group.duration !== undefined && group.duration > 0 && (
        <Badge variant="outline" className="text-[9px] h-4 px-1.5 font-mono">
          {formatDuration(group.duration)}
        </Badge>
      )}
      {group.tokenUsage && (
        <Badge variant="secondary" className="text-[9px] h-4 px-1.5">
          {group.tokenUsage.input + group.tokenUsage.output} tok
        </Badge>
      )}
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}

function GroupView({ group }: { group: ActionGroup }) {
  const [collapsed, setCollapsed] = useState(false);

  if (group.actions.length === 0) return null;

  return (
    <div className="mb-0.5">
      {group.iteration !== undefined && group.iteration > 0 && group.actions[0]?.type === "thinking" && (
        <IterationHeader iteration={group.iteration} group={group} />
      )}

      {group.isParallel && (
        <div className="flex items-center gap-1 pl-5 py-0.5">
          <Layers className="h-3 w-3 text-purple-500" />
          <span className="text-[10px] text-purple-500 font-medium">Parallel execution</span>
        </div>
      )}

      {/* Collapsible group with more than 5 items */}
      {group.actions.length > 5 && (
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-1 pl-3 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
        >
          {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {group.actions.length} actions
          {group.duration ? ` (${formatDuration(group.duration)})` : ""}
        </button>
      )}

      {/* Timeline line */}
      <div className={cn("border-l border-border/40 ml-[6px]", collapsed && "hidden")}>
        {(collapsed ? group.actions.slice(-2) : group.actions).map((action) => (
          <ActionItem key={action.id} action={action} />
        ))}
      </div>
    </div>
  );
}

function CurrentActionBar({ action }: { action: AgentAction }) {
  return (
    <div className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm border-b px-3 py-1.5 flex items-center gap-2">
      <Loader2 className="h-3 w-3 animate-spin text-primary shrink-0" />
      <span className={cn("text-xs font-medium shrink-0", getAgentColor(action.agent))}>
        {formatAgentName(action.agent)}
      </span>
      <span className="text-xs text-foreground/80 truncate">{action.description}</span>
    </div>
  );
}

export function AgentStatus() {
  const { agents, actionLog } = useAgentStore();
  const actionGroups = useActionGroups();
  const currentIteration = useCurrentIteration();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  // Find busy agents
  const busyAgents = agents.filter((agent) => agent.status === "busy");
  const hasActivity = actionLog.length > 0 || busyAgents.length > 0;

  // Current running action
  const currentAction = actionLog.length > 0 ? actionLog[actionLog.length - 1] : null;
  const isActive = currentAction?.status === "running";

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [actionLog, autoScroll]);

  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      setAutoScroll(scrollHeight - scrollTop - clientHeight < 30);
    }
  };

  if (!hasActivity) return null;

  return (
    <div className="border-b bg-muted/30 shrink-0">
      {/* Header */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="w-full flex items-center justify-between px-4 py-1.5 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Agent Activity
          </span>
          {busyAgents.length > 0 && (
            <Badge variant="secondary" className="text-[9px] h-4 px-1.5">
              {busyAgents.length} active
            </Badge>
          )}
          {currentIteration > 0 && (
            <Badge variant="outline" className="text-[9px] h-4 px-1.5">
              iter {currentIteration}
            </Badge>
          )}
        </div>
        {isCollapsed ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>

      {!isCollapsed && (
        <div className="relative">
          {/* Current action sticky bar */}
          {isActive && currentAction && <CurrentActionBar action={currentAction} />}

          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="max-h-36 sm:max-h-52 overflow-y-auto px-3 pb-2"
          >
            {actionLog.length === 0 ? (
              <div className="text-xs text-muted-foreground py-2">
                {busyAgents.map((agent) => (
                  <div key={agent.name} className="flex items-center gap-2 py-0.5">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    <span className={cn("font-medium", getAgentColor(agent.name))}>
                      {formatAgentName(agent.name)}
                    </span>
                    <span>is working{agent.current_task ? `: ${agent.current_task}` : ""}</span>
                  </div>
                ))}
              </div>
            ) : actionGroups.length > 0 ? (
              actionGroups.map((group) => (
                <GroupView key={group.id} group={group} />
              ))
            ) : (
              <div className="border-l border-border/40 ml-[6px]">
                {actionLog.slice(-25).map((action) => (
                  <ActionItem key={action.id} action={action} />
                ))}
              </div>
            )}

            {!autoScroll && actionLog.length > 5 && (
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
        </div>
      )}
    </div>
  );
}
