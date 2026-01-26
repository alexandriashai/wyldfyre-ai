"use client";

import { useState } from "react";
import { useCurrentUsage, useSessionUsage, formatTokenCount, formatCost } from "@/stores/usage-store";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Zap, TrendingUp, Clock, DollarSign, ArrowDownToLine, ArrowUpFromLine } from "lucide-react";

interface UsageMeterProps {
  className?: string;
  variant?: "compact" | "detailed";
}

export function UsageMeter({ className, variant = "compact" }: UsageMeterProps) {
  const current = useCurrentUsage();
  const session = useSessionUsage();
  const [isOpen, setIsOpen] = useState(false);

  const totalTokens = current.input + current.output;
  const sessionTotal = session.input + session.output;

  // Don't show if no usage yet
  if (sessionTotal === 0 && totalTokens === 0) {
    return null;
  }

  if (variant === "compact") {
    return (
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <button
            className={cn(
              "inline-flex items-center gap-1.5 px-2 py-1 rounded-md",
              "text-xs text-muted-foreground hover:text-foreground",
              "hover:bg-muted/50 transition-colors",
              className
            )}
          >
            <Zap className="h-3 w-3" />
            <span className="font-mono">
              {formatTokenCount(current.input)}
              <span className="text-muted-foreground/60 mx-0.5">/</span>
              {formatTokenCount(current.output)}
            </span>
            {current.cost > 0 && (
              <>
                <span className="text-muted-foreground/40">|</span>
                <span className="font-mono">{formatCost(current.cost)}</span>
              </>
            )}
            {current.tps > 0 && (
              <Badge variant="secondary" className="h-4 px-1 text-[9px] font-mono">
                {current.tps} t/s
              </Badge>
            )}
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-64 p-3" align="end">
          <UsageDetails current={current} session={session} />
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <div className={cn("p-3 rounded-lg bg-muted/30 border", className)}>
      <UsageDetails current={current} session={session} />
    </div>
  );
}

interface UsageDetailsProps {
  current: {
    input: number;
    output: number;
    cost: number;
    tps: number;
  };
  session: {
    input: number;
    output: number;
    cost: number;
    requests: number;
  };
}

function UsageDetails({ current, session }: UsageDetailsProps) {
  return (
    <div className="space-y-3">
      <div>
        <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
          <Clock className="h-3 w-3" />
          Current Request
        </h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-1.5">
            <ArrowDownToLine className="h-3 w-3 text-blue-500" />
            <span className="text-muted-foreground">In:</span>
            <span className="font-mono font-medium">{formatTokenCount(current.input)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <ArrowUpFromLine className="h-3 w-3 text-green-500" />
            <span className="text-muted-foreground">Out:</span>
            <span className="font-mono font-medium">{formatTokenCount(current.output)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <DollarSign className="h-3 w-3 text-amber-500" />
            <span className="text-muted-foreground">Cost:</span>
            <span className="font-mono font-medium">{formatCost(current.cost)}</span>
          </div>
          {current.tps > 0 && (
            <div className="flex items-center gap-1.5">
              <TrendingUp className="h-3 w-3 text-purple-500" />
              <span className="text-muted-foreground">Speed:</span>
              <span className="font-mono font-medium">{current.tps} t/s</span>
            </div>
          )}
        </div>
      </div>

      <div className="border-t pt-3">
        <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
          <Zap className="h-3 w-3" />
          Session Total
        </h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-1.5">
            <ArrowDownToLine className="h-3 w-3 text-blue-500/60" />
            <span className="text-muted-foreground">In:</span>
            <span className="font-mono">{formatTokenCount(session.input)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <ArrowUpFromLine className="h-3 w-3 text-green-500/60" />
            <span className="text-muted-foreground">Out:</span>
            <span className="font-mono">{formatTokenCount(session.output)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <DollarSign className="h-3 w-3 text-amber-500/60" />
            <span className="text-muted-foreground">Cost:</span>
            <span className="font-mono">{formatCost(session.cost)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Requests:</span>
            <span className="font-mono">{session.requests}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Compact inline version for headers
export function UsageBadge({ className }: { className?: string }) {
  const current = useCurrentUsage();
  const total = current.input + current.output;

  if (total === 0) return null;

  return (
    <Badge variant="outline" className={cn("font-mono text-[10px] h-5 px-1.5", className)}>
      <Zap className="h-2.5 w-2.5 mr-0.5" />
      {formatTokenCount(total)}
      {current.cost > 0 && (
        <span className="ml-1 text-muted-foreground">{formatCost(current.cost)}</span>
      )}
    </Badge>
  );
}
