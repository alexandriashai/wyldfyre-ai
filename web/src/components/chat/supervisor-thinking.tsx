"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Brain,
  ChevronDown,
  ChevronRight,
  Target,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  TrendingUp,
  TrendingDown,
} from "lucide-react";

export type ThinkingPhase = "evaluating" | "deciding" | "replanning" | "course_correcting";

export interface SupervisorThought {
  id: string;
  content: string;
  phase: ThinkingPhase;
  timestamp: string;
  stepId?: string;
  confidence?: number;
}

export interface ConfidenceUpdate {
  stepId: string;
  oldConfidence: number;
  newConfidence: number;
  reason: string;
  timestamp: string;
}

interface SupervisorThinkingProps {
  thoughts: SupervisorThought[];
  confidenceUpdates?: ConfidenceUpdate[];
  isActive?: boolean;
  className?: string;
}

const phaseConfig: Record<ThinkingPhase, { icon: React.ElementType; label: string; color: string }> = {
  evaluating: { icon: Target, label: "Evaluating", color: "text-blue-500" },
  deciding: { icon: Brain, label: "Deciding", color: "text-purple-500" },
  replanning: { icon: RefreshCw, label: "Replanning", color: "text-amber-500" },
  course_correcting: { icon: AlertTriangle, label: "Adjusting", color: "text-orange-500" },
};

function ThoughtItem({ thought, isLatest }: { thought: SupervisorThought; isLatest: boolean }) {
  const config = phaseConfig[thought.phase];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        "flex items-start gap-2 py-1.5 px-2 rounded-md transition-all",
        isLatest && "bg-muted/50"
      )}
    >
      <div className={cn("mt-0.5", config.color)}>
        {isLatest ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Icon className="h-3.5 w-3.5" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <Badge variant="outline" className={cn("h-4 px-1.5 text-[9px]", config.color)}>
            {config.label}
          </Badge>
          {thought.confidence !== undefined && (
            <ConfidenceBadge confidence={thought.confidence} />
          )}
          <span className="text-[10px] text-muted-foreground ml-auto">
            {formatTime(thought.timestamp)}
          </span>
        </div>
        <p className="text-xs text-foreground/80 leading-relaxed">{thought.content}</p>
      </div>
    </div>
  );
}

function ConfidenceUpdate({ update }: { update: ConfidenceUpdate }) {
  const isIncrease = update.newConfidence > update.oldConfidence;
  const diff = Math.abs(update.newConfidence - update.oldConfidence);
  const Icon = isIncrease ? TrendingUp : TrendingDown;

  return (
    <div className="flex items-start gap-2 py-1 px-2 text-xs">
      <Icon
        className={cn(
          "h-3.5 w-3.5 mt-0.5",
          isIncrease ? "text-green-500" : "text-red-500"
        )}
      />
      <div className="flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Confidence:</span>
          <span className={cn("font-mono", isIncrease ? "text-green-500" : "text-red-500")}>
            {update.oldConfidence}% → {update.newConfidence}%
          </span>
          <span className={cn("text-[10px]", isIncrease ? "text-green-500" : "text-red-500")}>
            ({isIncrease ? "+" : "-"}{diff}%)
          </span>
        </div>
        <p className="text-muted-foreground mt-0.5">{update.reason}</p>
      </div>
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const getColor = () => {
    if (confidence >= 80) return "bg-green-500/10 text-green-500 border-green-500/20";
    if (confidence >= 60) return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
    return "bg-red-500/10 text-red-500 border-red-500/20";
  };

  return (
    <Badge variant="outline" className={cn("h-4 px-1 text-[9px] font-mono", getColor())}>
      {confidence}%
    </Badge>
  );
}

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

export function SupervisorThinking({
  thoughts,
  confidenceUpdates = [],
  isActive = false,
  className,
}: SupervisorThinkingProps) {
  const [isOpen, setIsOpen] = useState(true);

  // Auto-expand when new thoughts arrive
  useEffect(() => {
    if (thoughts.length > 0 && isActive) {
      setIsOpen(true);
    }
  }, [thoughts.length, isActive]);

  if (thoughts.length === 0 && confidenceUpdates.length === 0) {
    return null;
  }

  const latestThought = thoughts[thoughts.length - 1];
  const latestPhase = latestThought?.phase;

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("border-b bg-gradient-to-r from-purple-500/5 to-blue-500/5", className)}
    >
      <CollapsibleTrigger asChild>
        <button className="w-full flex items-center gap-2 px-4 py-2 hover:bg-muted/30 transition-colors">
          <Brain className={cn("h-4 w-4", isActive ? "text-purple-500 animate-pulse" : "text-muted-foreground")} />
          <span className="text-xs font-medium">Supervisor Reasoning</span>
          {isActive && latestPhase && (
            <Badge variant="secondary" className="text-[9px] h-4 px-1.5">
              {phaseConfig[latestPhase].label}
            </Badge>
          )}
          {thoughts.length > 0 && (
            <span className="text-[10px] text-muted-foreground ml-auto mr-2">
              {thoughts.length} thought{thoughts.length !== 1 ? "s" : ""}
            </span>
          )}
          {isOpen ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-3 pb-3 space-y-1 max-h-48 overflow-y-auto">
          {/* Interleave thoughts and confidence updates by timestamp */}
          {[...thoughts, ...confidenceUpdates.map(u => ({ ...u, _type: "confidence" as const }))]
            .sort((a, b) => {
              const dateA = new Date(a.timestamp);
              const dateB = new Date(b.timestamp);
              const timeA = isNaN(dateA.getTime()) ? 0 : dateA.getTime();
              const timeB = isNaN(dateB.getTime()) ? 0 : dateB.getTime();
              return timeA - timeB;
            })
            .map((item, i) => {
              if ("_type" in item && item._type === "confidence") {
                return <ConfidenceUpdate key={`conf-${i}`} update={item as ConfidenceUpdate} />;
              }
              const thought = item as SupervisorThought;
              return (
                <ThoughtItem
                  key={thought.id}
                  thought={thought}
                  isLatest={isActive && i === thoughts.length + confidenceUpdates.length - 1 && !("_type" in item)}
                />
              );
            })}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

// Compact version for inline display
export function SupervisorThinkingInline({ thought, isActive }: { thought: SupervisorThought | null; isActive: boolean }) {
  if (!thought) return null;

  const config = phaseConfig[thought.phase];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/30 border-b text-xs">
      {isActive ? (
        <Loader2 className={cn("h-3 w-3 animate-spin", config.color)} />
      ) : (
        <Icon className={cn("h-3 w-3", config.color)} />
      )}
      <span className={cn("font-medium", config.color)}>{config.label}:</span>
      <span className="text-foreground/80 truncate">{thought.content}</span>
      {thought.confidence !== undefined && (
        <ConfidenceBadge confidence={thought.confidence} />
      )}
    </div>
  );
}
