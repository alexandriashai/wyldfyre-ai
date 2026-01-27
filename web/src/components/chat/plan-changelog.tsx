"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Plus,
  Minus,
  Pencil,
  ArrowUpDown,
  ChevronDown,
  ChevronRight,
  History,
  GitBranch,
} from "lucide-react";

export type PlanChangeType = "step_added" | "step_removed" | "step_modified" | "step_reordered";

export interface PlanChange {
  id: string;
  changeType: PlanChangeType;
  stepId: string;
  stepTitle?: string;
  reason: string;
  timestamp: string;
  before?: {
    title?: string;
    description?: string;
    order?: number;
  };
  after?: {
    title?: string;
    description?: string;
    order?: number;
  };
}

interface PlanChangelogProps {
  changes: PlanChange[];
  className?: string;
  maxVisible?: number;
}

const changeConfig: Record<PlanChangeType, { icon: React.ElementType; label: string; color: string; bgColor: string }> = {
  step_added: { icon: Plus, label: "Added", color: "text-green-500", bgColor: "bg-green-500/10" },
  step_removed: { icon: Minus, label: "Removed", color: "text-red-500", bgColor: "bg-red-500/10" },
  step_modified: { icon: Pencil, label: "Modified", color: "text-blue-500", bgColor: "bg-blue-500/10" },
  step_reordered: { icon: ArrowUpDown, label: "Reordered", color: "text-amber-500", bgColor: "bg-amber-500/10" },
};

function ChangeItem({ change, isLatest }: { change: PlanChange; isLatest: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const config = changeConfig[change.changeType];
  const Icon = config.icon;
  const hasDetails = change.before || change.after;

  return (
    <div
      className={cn(
        "relative pl-5 py-1.5",
        isLatest && "animate-in fade-in slide-in-from-left-2 duration-300"
      )}
    >
      {/* Timeline connector */}
      <div className="absolute left-[7px] top-0 bottom-0 w-px bg-border" />

      {/* Icon dot */}
      <div
        className={cn(
          "absolute left-0 top-[10px] w-4 h-4 rounded-full flex items-center justify-center",
          config.bgColor,
          isLatest && "ring-2 ring-offset-1 ring-offset-background",
          isLatest && change.changeType === "step_added" && "ring-green-500/30",
          isLatest && change.changeType === "step_removed" && "ring-red-500/30",
          isLatest && change.changeType === "step_modified" && "ring-blue-500/30",
          isLatest && change.changeType === "step_reordered" && "ring-amber-500/30"
        )}
      >
        <Icon className={cn("h-2.5 w-2.5", config.color)} />
      </div>

      <div
        className={cn(
          "rounded-md transition-colors",
          hasDetails && "cursor-pointer hover:bg-muted/30"
        )}
        onClick={() => hasDetails && setExpanded(!expanded)}
      >
        <div className="flex items-center gap-1.5 flex-wrap">
          <Badge variant="outline" className={cn("h-4 px-1.5 text-[9px]", config.color)}>
            {config.label}
          </Badge>
          {change.stepTitle && (
            <span className="text-xs font-medium truncate max-w-[150px]">
              {change.stepTitle}
            </span>
          )}
          {hasDetails && (
            <span className="text-muted-foreground">
              {expanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </span>
          )}
          <span className="text-[10px] text-muted-foreground ml-auto">
            {formatTime(change.timestamp)}
          </span>
        </div>

        <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
          {change.reason}
        </p>

        {expanded && hasDetails && (
          <div className="mt-2 space-y-1.5 text-[10px] border-t pt-2">
            {change.before && (
              <div className="flex items-start gap-2">
                <span className="text-red-500 font-mono">-</span>
                <div className="flex-1 bg-red-500/5 rounded px-2 py-1 border border-red-500/10">
                  {change.before.title && (
                    <div>
                      <span className="text-muted-foreground">Title: </span>
                      <span className="line-through">{change.before.title}</span>
                    </div>
                  )}
                  {change.before.order !== undefined && (
                    <div>
                      <span className="text-muted-foreground">Order: </span>
                      <span>{change.before.order}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            {change.after && (
              <div className="flex items-start gap-2">
                <span className="text-green-500 font-mono">+</span>
                <div className="flex-1 bg-green-500/5 rounded px-2 py-1 border border-green-500/10">
                  {change.after.title && (
                    <div>
                      <span className="text-muted-foreground">Title: </span>
                      <span>{change.after.title}</span>
                    </div>
                  )}
                  {change.after.order !== undefined && (
                    <div>
                      <span className="text-muted-foreground">Order: </span>
                      <span>{change.after.order}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function formatTime(timestamp: string): string {
  try {
    if (!timestamp) return "--:--";
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "--:--";
    return date.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "--:--";
  }
}

export function PlanChangelog({ changes, className, maxVisible = 5 }: PlanChangelogProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [showAll, setShowAll] = useState(false);

  if (changes.length === 0) {
    return null;
  }

  const visibleChanges = showAll ? changes : changes.slice(-maxVisible);
  const hiddenCount = changes.length - maxVisible;

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("border-t mt-3 pt-3", className)}
    >
      <CollapsibleTrigger asChild>
        <button className="w-full flex items-center gap-2 hover:opacity-80 transition-opacity">
          <History className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground">Plan Changes</span>
          <Badge variant="secondary" className="text-[9px] h-4 px-1.5">
            {changes.length}
          </Badge>
          <span className="flex-1" />
          {isOpen ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 ml-1">
          {!showAll && hiddenCount > 0 && (
            <button
              onClick={() => setShowAll(true)}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground mb-2 ml-5"
            >
              <GitBranch className="h-3 w-3" />
              Show {hiddenCount} earlier change{hiddenCount !== 1 ? "s" : ""}
            </button>
          )}
          {visibleChanges.map((change, i) => (
            <ChangeItem
              key={change.id}
              change={change}
              isLatest={i === visibleChanges.length - 1}
            />
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

// Summary badges for inline display
export function PlanChangesSummary({ changes }: { changes: PlanChange[] }) {
  if (changes.length === 0) return null;

  const counts = changes.reduce((acc, c) => {
    acc[c.changeType] = (acc[c.changeType] || 0) + 1;
    return acc;
  }, {} as Record<PlanChangeType, number>);

  return (
    <div className="flex items-center gap-1">
      {Object.entries(counts).map(([type, count]) => {
        const config = changeConfig[type as PlanChangeType];
        const Icon = config.icon;
        return (
          <Badge
            key={type}
            variant="outline"
            className={cn("h-4 px-1 text-[9px] gap-0.5", config.color)}
          >
            <Icon className="h-2.5 w-2.5" />
            {count}
          </Badge>
        );
      })}
    </div>
  );
}
