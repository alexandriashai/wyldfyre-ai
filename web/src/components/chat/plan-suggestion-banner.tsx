"use client";

import { useChatStore } from "@/stores/chat-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Lightbulb, X, CheckCircle } from "lucide-react";

interface PlanSuggestionBannerProps {
  className?: string;
  onAccept?: () => void;
}

export function PlanSuggestionBanner({ className, onAccept }: PlanSuggestionBannerProps) {
  const planSuggestion = useChatStore((state) => state.planSuggestion);
  const clearPlanSuggestion = useChatStore((state) => state.clearPlanSuggestion);

  if (!planSuggestion) return null;

  return (
    <div className={cn(
      "px-4 py-3 bg-amber-500/10 border border-amber-500/30 rounded-lg mx-4 mb-2",
      className
    )}>
      <div className="flex items-start gap-3">
        <Lightbulb className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
            {planSuggestion.message}
          </p>
          {planSuggestion.reason && (
            <p className="text-xs text-muted-foreground mt-1">
              {planSuggestion.reason}
            </p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs border-amber-500/30 hover:bg-amber-500/10"
              onClick={() => {
                if (onAccept) {
                  onAccept();
                }
                clearPlanSuggestion();
              }}
            >
              <CheckCircle className="h-3 w-3 mr-1" />
              Enter Plan Mode
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-muted-foreground"
              onClick={clearPlanSuggestion}
            >
              Continue Without Planning
            </Button>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground shrink-0"
          onClick={clearPlanSuggestion}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
