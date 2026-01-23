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
  ChevronRight,
  Check,
  X,
  Clock,
  Pencil,
  Square,
  CheckSquare,
  Loader2,
  AlertCircle,
  SkipForward,
  RefreshCw,
} from "lucide-react";

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

function getStepDuration(step: PlanStep): number | null {
  if (step.started_at && step.completed_at) {
    return new Date(step.completed_at).getTime() - new Date(step.started_at).getTime();
  }
  if (step.started_at && step.status === "in_progress") {
    return Date.now() - new Date(step.started_at).getTime();
  }
  return null;
}

// Simple markdown-like rendering
function renderPlanContent(content: string) {
  const lines = content.split("\n");
  const elements: JSX.Element[] = [];

  lines.forEach((line, i) => {
    if (line.startsWith("### ")) {
      elements.push(<h4 key={i} className="font-semibold text-sm mt-3 mb-1">{line.slice(4)}</h4>);
    } else if (line.startsWith("## ")) {
      elements.push(<h3 key={i} className="font-semibold mt-3 mb-1">{line.slice(3)}</h3>);
    } else if (line.startsWith("# ")) {
      elements.push(<h2 key={i} className="font-bold text-lg mt-4 mb-2">{line.slice(2)}</h2>);
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(<li key={i} className="ml-4 text-sm">{line.slice(2)}</li>);
    } else if (/^\d+\.\s/.test(line)) {
      elements.push(<li key={i} className="ml-4 text-sm list-decimal">{line.replace(/^\d+\.\s/, "")}</li>);
    } else if (line.startsWith("```")) {
      // Skip
    } else if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
    } else {
      elements.push(<p key={i} className="text-sm">{line}</p>);
    }
  });

  return elements;
}

function StepItem({ step, index, isLast }: { step: PlanStep; index: number; isLast: boolean }) {
  const [showOutput, setShowOutput] = useState(false);
  const duration = getStepDuration(step);
  const hasOutput = step.output && step.output.length > 0;
  const hasError = step.error && step.error.length > 0;

  const stepIcons = {
    pending: Square,
    in_progress: Loader2,
    completed: CheckSquare,
    failed: AlertCircle,
    skipped: SkipForward,
  };

  const stepColors = {
    pending: "text-muted-foreground",
    in_progress: "text-blue-500",
    completed: "text-green-500",
    failed: "text-red-500",
    skipped: "text-yellow-500",
  };

  const Icon = stepIcons[step.status] || Square;
  const colorClass = stepColors[step.status] || "text-muted-foreground";
  const isActive = step.status === "in_progress";

  return (
    <div className="relative">
      {/* Connecting line */}
      {!isLast && (
        <div className={cn(
          "absolute left-[11px] top-[28px] w-px h-[calc(100%-12px)]",
          step.status === "completed" ? "bg-green-500/40" : "bg-border"
        )} />
      )}

      <div
        className={cn(
          "flex items-start gap-2 p-2 rounded-md transition-all duration-300",
          isActive && "bg-blue-500/10 border border-blue-500/30 scale-[1.01]",
          step.status === "completed" && "bg-green-500/5",
          step.status === "failed" && "bg-red-500/5 border border-red-500/20"
        )}
      >
        <div className="relative">
          <Icon className={cn(
            "h-5 w-5 mt-0.5 flex-shrink-0 transition-all duration-300",
            colorClass,
            isActive && "animate-spin"
          )} />
          {isActive && (
            <div className="absolute inset-0 animate-ping">
              <div className="h-5 w-5 rounded-full bg-blue-500/20" />
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={cn(
              "font-medium text-sm transition-all duration-300",
              step.status === "completed" && "line-through text-muted-foreground"
            )}>
              {step.title}
            </span>
            {step.agent && (
              <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                {step.agent}
              </Badge>
            )}
            {duration !== null && duration > 0 && (
              <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                <Clock className="h-2.5 w-2.5" />
                {formatDuration(duration)}
              </span>
            )}
          </div>

          {step.description && (
            <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
          )}

          {/* Files affected */}
          {step.files && step.files.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {step.files.map((file, i) => (
                <Badge key={i} variant="secondary" className="text-[9px] h-4 px-1 font-mono">
                  {file.split("/").pop()}
                </Badge>
              ))}
            </div>
          )}

          {/* Output preview */}
          {hasOutput && step.status === "completed" && (
            <div className="mt-1.5">
              <button
                onClick={() => setShowOutput(!showOutput)}
                className="flex items-center gap-1 text-[10px] text-green-600 dark:text-green-400 hover:underline"
              >
                {showOutput ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                View output
              </button>
              {showOutput && (
                <pre className="mt-1 text-[10px] text-muted-foreground bg-muted/50 rounded p-2 overflow-x-auto max-h-24 overflow-y-auto whitespace-pre-wrap break-all border">
                  {step.output}
                </pre>
              )}
            </div>
          )}

          {/* Error display with retry */}
          {hasError && step.status === "failed" && (
            <div className="mt-1.5 flex items-start gap-2">
              <p className="text-xs text-red-600 dark:text-red-400 flex-1">
                {step.error}
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="h-5 px-2 text-[10px] text-primary shrink-0"
                onClick={() => {
                  // Send retry command via chat
                  const chatStore = useChatStore.getState();
                  if (chatStore.currentConversation) {
                    // This would be handled by the useChat hook
                    console.log("Retry step:", step.id);
                  }
                }}
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                Retry
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProgressBar({ steps }: { steps: PlanStep[] }) {
  const completed = steps.filter((s) => s.status === "completed").length;
  const failed = steps.filter((s) => s.status === "failed").length;
  const inProgress = steps.filter((s) => s.status === "in_progress").length;
  const total = steps.length;
  const percentage = Math.round((completed / total) * 100);

  // Calculate total elapsed time
  const startedSteps = steps.filter((s) => s.started_at);
  const completedSteps = steps.filter((s) => s.completed_at);
  const totalDuration = completedSteps.reduce((acc, step) => {
    if (step.started_at && step.completed_at) {
      return acc + (new Date(step.completed_at).getTime() - new Date(step.started_at).getTime());
    }
    return acc;
  }, 0);

  return (
    <div className="mt-3 pt-3 border-t">
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
        <span className="flex items-center gap-2">
          <span>{completed}/{total} steps</span>
          {failed > 0 && <span className="text-destructive">({failed} failed)</span>}
          {inProgress > 0 && <span className="text-blue-500">(1 running)</span>}
        </span>
        <span className="flex items-center gap-2">
          {totalDuration > 0 && (
            <span className="flex items-center gap-0.5">
              <Clock className="h-3 w-3" />
              {formatDuration(totalDuration)}
            </span>
          )}
          <span className="font-medium">{percentage}%</span>
        </span>
      </div>

      {/* Segmented progress bar */}
      <div className="h-2 bg-muted rounded-full overflow-hidden flex">
        {steps.map((step, i) => (
          <div
            key={step.id}
            className={cn(
              "h-full transition-all duration-500",
              step.status === "completed" && "bg-green-500",
              step.status === "failed" && "bg-destructive",
              step.status === "in_progress" && "bg-blue-500 animate-pulse",
              step.status === "skipped" && "bg-yellow-500/50",
              step.status === "pending" && "bg-transparent",
              i > 0 && "border-l border-background/30"
            )}
            style={{ width: `${100 / total}%` }}
          />
        ))}
      </div>
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
    clearPlan,
    currentConversation,
  } = useChatStore();

  const [isOpen, setIsOpen] = useState(true);
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const closeTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-close plan panel after completion
  useEffect(() => {
    if (planStatus === "COMPLETED") {
      closeTimerRef.current = setTimeout(() => {
        clearPlan();
      }, 5000);
    }
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, [planStatus, clearPlan]);

  if (!currentPlan) return null;

  const handleApprove = async () => {
    if (!token) return;
    setIsApproving(true);
    try { await approvePlan(token); }
    finally { setIsApproving(false); }
  };

  const handleReject = async () => {
    if (!token) return;
    setIsRejecting(true);
    try { await rejectPlan(token); }
    finally { setIsRejecting(false); }
  };

  const isExecuting = planSteps.some((s) => s.status === "in_progress");
  const isPaused = planStatus === "APPROVED" && planSteps.length > 0 &&
    !isExecuting && planSteps.some((s) => s.status === "pending");

  const statusConfig = {
    DRAFT: { label: "Draft", variant: "secondary" as const, icon: Pencil },
    PENDING: { label: "Pending Approval", variant: "outline" as const, icon: Clock },
    APPROVED: {
      label: isExecuting ? "Executing" : isPaused ? "Paused" : "Approved",
      variant: "default" as const,
      icon: isExecuting ? Loader2 : isPaused ? Clock : Check,
    },
    REJECTED: { label: "Rejected", variant: "destructive" as const, icon: X },
    COMPLETED: { label: "Completed", variant: "default" as const, icon: Check },
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
              <StatusIcon className={cn("h-3 w-3 mr-1", isExecuting && "animate-spin")} />
              {status.label}
            </Badge>
            {planSteps.length > 0 && (
              <span className="text-[10px] text-muted-foreground">
                {planSteps.filter((s) => s.status === "completed").length}/{planSteps.length}
              </span>
            )}
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
              <div className="py-2 space-y-0.5">
                {planSteps.map((step, index) => (
                  <StepItem
                    key={step.id}
                    step={step}
                    index={index}
                    isLast={index === planSteps.length - 1}
                  />
                ))}
                <ProgressBar steps={planSteps} />
              </div>
            ) : (
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

          {isExecuting && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-xs text-muted-foreground italic">
                Tip: Type in chat to modify the plan while executing.
              </p>
            </div>
          )}

          {isPaused && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-xs text-muted-foreground italic">
                Plan is paused. Type &quot;resume&quot; to continue.
              </p>
            </div>
          )}

          {planStatus === "COMPLETED" && (
            <div className="mt-3 pt-3 border-t flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Plan completed. Closing shortly...
              </p>
              <Button variant="ghost" size="sm" onClick={() => clearPlan()} className="h-6 text-xs">
                Dismiss
              </Button>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
