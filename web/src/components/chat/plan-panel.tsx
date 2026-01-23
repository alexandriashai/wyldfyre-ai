"use client";

import { useState, useEffect, useRef } from "react";
import { useChatStore, PlanStep } from "@/stores/chat-store";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  FileText,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  Clock,
  Pencil,
  Square,
  CheckSquare,
  Loader2,
  AlertCircle,
  SkipForward,
} from "lucide-react";

// Simple markdown-like rendering
function renderPlanContent(content: string) {
  const lines = content.split("\n");
  const elements: JSX.Element[] = [];

  lines.forEach((line, i) => {
    // Headers
    if (line.startsWith("### ")) {
      elements.push(
        <h4 key={i} className="font-semibold text-sm mt-3 mb-1">
          {line.slice(4)}
        </h4>
      );
    } else if (line.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="font-semibold mt-3 mb-1">
          {line.slice(3)}
        </h3>
      );
    } else if (line.startsWith("# ")) {
      elements.push(
        <h2 key={i} className="font-bold text-lg mt-4 mb-2">
          {line.slice(2)}
        </h2>
      );
    }
    // List items
    else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <li key={i} className="ml-4 text-sm">
          {line.slice(2)}
        </li>
      );
    }
    // Numbered list items
    else if (/^\d+\.\s/.test(line)) {
      elements.push(
        <li key={i} className="ml-4 text-sm list-decimal">
          {line.replace(/^\d+\.\s/, "")}
        </li>
      );
    }
    // Code blocks
    else if (line.startsWith("```")) {
      // Skip code block markers
    }
    // Empty lines
    else if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
    }
    // Regular text
    else {
      elements.push(
        <p key={i} className="text-sm">
          {line}
        </p>
      );
    }
  });

  return elements;
}

// Render plan steps with checkbox-style icons
function renderPlanSteps(steps: PlanStep[], currentStepIndex: number) {
  const stepIcons = {
    pending: Square,
    in_progress: Loader2,
    completed: CheckSquare,
    failed: AlertCircle,
    skipped: SkipForward,
  };

  const stepColors = {
    pending: "text-muted-foreground",
    in_progress: "text-blue-500 animate-spin",
    completed: "text-green-500",
    failed: "text-red-500",
    skipped: "text-yellow-500",
  };

  return (
    <div className="space-y-2">
      {steps.map((step, index) => {
        const Icon = stepIcons[step.status] || Square;
        const colorClass = stepColors[step.status] || "text-muted-foreground";
        const isActive = step.status === "in_progress";

        return (
          <div
            key={step.id}
            className={cn(
              "flex items-start gap-2 p-2 rounded-md transition-colors",
              isActive && "bg-blue-500/10 border border-blue-500/30",
              step.status === "completed" && "bg-green-500/5",
              step.status === "failed" && "bg-red-500/5"
            )}
          >
            <Icon className={cn("h-5 w-5 mt-0.5 flex-shrink-0", colorClass)} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "font-medium text-sm",
                    step.status === "completed" && "line-through text-muted-foreground"
                  )}
                >
                  {step.title}
                </span>
                {step.agent && (
                  <Badge variant="outline" className="text-xs h-5">
                    {step.agent}
                  </Badge>
                )}
              </div>
              {step.description && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {step.description}
                </p>
              )}
              {step.output && step.status === "completed" && (
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                  {step.output}
                </p>
              )}
              {step.error && step.status === "failed" && (
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                  Error: {step.error}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface PlanPanelProps {
  className?: string;
}

export function PlanPanel({ className }: PlanPanelProps) {
  const { token } = useAuthStore();
  const {
    currentPlan,
    planStatus,
    planSteps,
    currentStepIndex,
    approvePlan,
    rejectPlan,
    currentConversation,
  } = useChatStore();

  const [isOpen, setIsOpen] = useState(true);
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const closeTimerRef = useRef<NodeJS.Timeout | null>(null);
  const { clearPlan } = useChatStore();

  // Auto-close plan panel after completion
  useEffect(() => {
    if (planStatus === "COMPLETED") {
      closeTimerRef.current = setTimeout(() => {
        clearPlan();
      }, 5000);
    }
    return () => {
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
      }
    };
  }, [planStatus, clearPlan]);

  if (!currentPlan) {
    return null;
  }

  const handleApprove = async () => {
    if (!token) return;
    setIsApproving(true);
    try {
      await approvePlan(token);
    } finally {
      setIsApproving(false);
    }
  };

  const handleReject = async () => {
    if (!token) return;
    setIsRejecting(true);
    try {
      await rejectPlan(token);
    } finally {
      setIsRejecting(false);
    }
  };

  // Check if plan is currently executing (has in_progress steps)
  const isExecuting = planSteps.some((s) => s.status === "in_progress");
  const isPaused = planStatus === "APPROVED" && planSteps.length > 0 &&
    !isExecuting && planSteps.some((s) => s.status === "pending");

  const statusConfig = {
    DRAFT: {
      label: "Draft",
      variant: "secondary" as const,
      icon: Pencil,
    },
    PENDING: {
      label: "Pending Approval",
      variant: "outline" as const,
      icon: Clock,
    },
    APPROVED: {
      label: isExecuting ? "Executing" : isPaused ? "Paused" : "Approved",
      variant: "default" as const,
      icon: isExecuting ? Loader2 : isPaused ? Clock : Check,
    },
    REJECTED: {
      label: "Rejected",
      variant: "destructive" as const,
      icon: X,
    },
    COMPLETED: {
      label: "Completed",
      variant: "default" as const,
      icon: Check,
    },
  };

  const status = planStatus && statusConfig[planStatus] ? statusConfig[planStatus] : statusConfig.DRAFT;
  const StatusIcon = status.icon;
  const showActions = planStatus === "PENDING" || planStatus === "DRAFT";

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("border-b bg-muted/30", className)}
    >
      <CollapsibleTrigger asChild>
        <div className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-muted/50 transition-colors">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Plan</span>
            <Badge variant={status.variant} className="h-5 text-xs">
              <StatusIcon className="h-3 w-3 mr-1" />
              {status.label}
            </Badge>
          </div>
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-4 pb-3">
          <div className="max-h-[60vh] sm:max-h-80 overflow-y-auto overscroll-contain touch-pan-y">
            {planSteps.length > 0 ? (
              // Show step checkboxes when executing
              <div className="py-2">
                {renderPlanSteps(planSteps, currentStepIndex)}
                {/* Progress indicator */}
                <div className="mt-3 pt-3 border-t">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {planSteps.filter((s) => s.status === "completed").length} of{" "}
                      {planSteps.length} steps completed
                    </span>
                    <span>
                      {Math.round(
                        (planSteps.filter((s) => s.status === "completed").length /
                          planSteps.length) *
                          100
                      )}
                      %
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 transition-all duration-300"
                      style={{
                        width: `${
                          (planSteps.filter((s) => s.status === "completed").length /
                            planSteps.length) *
                          100
                        }%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            ) : (
              // Show plan content when in planning phase
              <div className="prose prose-sm dark:prose-invert max-w-none">
                {renderPlanContent(currentPlan)}
              </div>
            )}
          </div>

          {showActions && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t">
              <Button
                variant="default"
                size="sm"
                onClick={handleApprove}
                disabled={isApproving || isRejecting}
                className="flex-1"
              >
                <Check className="h-4 w-4 mr-2" />
                {isApproving ? "Approving..." : "Approve Plan"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleReject}
                disabled={isApproving || isRejecting}
                className="flex-1"
              >
                <X className="h-4 w-4 mr-2" />
                {isRejecting ? "Rejecting..." : "Reject"}
              </Button>
            </div>
          )}

          {/* Show hint when executing */}
          {isExecuting && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-xs text-muted-foreground italic">
                💡 Tip: Type in chat to modify the plan (e.g., &quot;add a testing step&quot; or &quot;skip step 2&quot;)
              </p>
            </div>
          )}

          {/* Show resume hint when paused */}
          {isPaused && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-xs text-muted-foreground italic">
                Plan is paused. Type &quot;resume&quot; in chat to continue, or modify the remaining steps.
              </p>
            </div>
          )}

          {/* Show dismiss for completed plans */}
          {planStatus === "COMPLETED" && (
            <div className="mt-3 pt-3 border-t flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Plan saved to memory. Closing shortly...
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => clearPlan()}
                className="h-6 text-xs"
              >
                Dismiss
              </Button>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
