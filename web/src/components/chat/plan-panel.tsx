"use client";

import { useState, useEffect, useRef } from "react";
import { useChatStore, PlanStep, TodoProgress } from "@/stores/chat-store";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { MarkdownRenderer } from "./markdown-renderer";
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
  Info,
  Link2,
  GitBranch,
  AlertTriangle,
} from "lucide-react";
import { PlanChangelog } from "./plan-changelog";
import { StepRollbackButton } from "./rollback-controls";

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

function getStepDuration(step: PlanStep): number | null {
  try {
    if (step.started_at && step.completed_at) {
      const start = new Date(step.started_at);
      const end = new Date(step.completed_at);
      if (isNaN(start.getTime()) || isNaN(end.getTime())) return null;
      return end.getTime() - start.getTime();
    }
    if (step.started_at && step.status === "in_progress") {
      const start = new Date(step.started_at);
      if (isNaN(start.getTime())) return null;
      return Date.now() - start.getTime();
    }
  } catch {
    return null;
  }
  return null;
}

interface TodoItemProps {
  todo: string;
  index: number;
  stepId: string;
  stepStatus: PlanStep["status"];
  progress?: TodoProgress;
}

function TodoItem({ todo, index, stepId, stepStatus, progress }: TodoItemProps) {
  const isCompleted = stepStatus === "completed" || (progress && progress.progress >= 100);
  const isInProgress = progress && progress.progress > 0 && progress.progress < 100;
  const hasMessage = progress?.statusMessage;

  return (
    <li className="flex flex-col gap-0.5">
      <div className="flex items-start gap-1.5 text-xs">
        <span className="mt-0.5 shrink-0">
          {isCompleted ? (
            <Check className="h-3 w-3 text-green-500" />
          ) : isInProgress ? (
            <Loader2 className="h-3 w-3 text-blue-500 animate-spin" />
          ) : (
            <Square className="h-3 w-3 text-muted-foreground" />
          )}
        </span>
        <span className={cn(
          "flex-1",
          isCompleted && "text-muted-foreground line-through",
          !isCompleted && "text-foreground/80"
        )}>
          {todo}
        </span>
        {progress && progress.progress > 0 && progress.progress < 100 && (
          <span className="text-[10px] text-blue-500 font-mono shrink-0">
            {progress.progress}%
          </span>
        )}
      </div>

      {/* Progress bar for multi-part todos */}
      {isInProgress && (
        <div className="ml-4 flex items-center gap-2">
          <Progress value={progress?.progress || 0} className="h-1 flex-1" />
        </div>
      )}

      {/* Status message */}
      {hasMessage && (
        <div className="ml-4 flex items-start gap-1 text-[10px] text-muted-foreground">
          <Info className="h-2.5 w-2.5 mt-0.5 shrink-0" />
          <span>{progress.statusMessage}</span>
        </div>
      )}
    </li>
  );
}

interface StepItemProps {
  step: PlanStep;
  index: number;
  isLast: boolean;
  todoProgressMap: Record<number, TodoProgress>;
  planId?: string;
}

function StepItem({ step, index, isLast, todoProgressMap, planId }: StepItemProps) {
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
        <div className="relative shrink-0">
          <Icon className={cn(
            "h-5 w-5 mt-0.5 transition-all duration-300",
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
          <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
            <span className={cn(
              "font-medium text-sm transition-all duration-300",
              step.status === "completed" && "line-through text-muted-foreground"
            )}>
              {step.title}
            </span>
            {step.agent && (
              <Badge variant="outline" className="text-[10px] h-4 px-1.5 hidden sm:inline-flex">
                {step.agent}
              </Badge>
            )}
            {duration !== null && duration > 0 && (
              <span className="text-[10px] text-muted-foreground flex items-center gap-0.5 shrink-0">
                <Clock className="h-2.5 w-2.5" />
                {formatDuration(duration)}
              </span>
            )}
            {/* Rollback button for completed steps */}
            {step.status === "completed" && planId && (
              <StepRollbackButton planId={planId} stepId={step.id} className="ml-auto" />
            )}
          </div>

          {step.description && (
            <div className="text-xs text-muted-foreground mt-0.5 prose prose-xs dark:prose-invert max-w-none [&_p]:m-0 [&_ul]:m-0 [&_ol]:m-0 [&_li]:m-0 line-clamp-2 sm:line-clamp-none">
              <MarkdownRenderer content={step.description} />
            </div>
          )}

          {/* Enhanced Todos with progress */}
          {step.todos && step.todos.length > 0 && (
            <ul className="mt-1.5 space-y-1">
              {step.todos.map((todo, i) => (
                <TodoItem
                  key={i}
                  todo={todo}
                  index={i}
                  stepId={step.id}
                  stepStatus={step.status}
                  progress={todoProgressMap[i]}
                />
              ))}
            </ul>
          )}

          {/* Files affected - responsive */}
          {step.files && step.files.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {step.files.slice(0, 3).map((file, i) => (
                <Badge key={i} variant="secondary" className="text-[9px] h-4 px-1 font-mono max-w-[120px] truncate">
                  {file.split("/").pop()}
                </Badge>
              ))}
              {step.files.length > 3 && (
                <Badge variant="secondary" className="text-[9px] h-4 px-1">
                  +{step.files.length - 3} more
                </Badge>
              )}
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
            <div className="mt-1.5 flex flex-col sm:flex-row sm:items-start gap-2">
              <p className="text-xs text-red-600 dark:text-red-400 flex-1">
                {step.error}
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[10px] text-primary shrink-0 self-start"
                onClick={() => {
                  const chatStore = useChatStore.getState();
                  if (chatStore.currentConversation) {
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

  const completedSteps = steps.filter((s) => s.completed_at);
  const totalDuration = completedSteps.reduce((acc, step) => {
    if (step.started_at && step.completed_at) {
      try {
        const start = new Date(step.started_at);
        const end = new Date(step.completed_at);
        if (!isNaN(start.getTime()) && !isNaN(end.getTime())) {
          return acc + (end.getTime() - start.getTime());
        }
      } catch {
        // Skip invalid dates
      }
    }
    return acc;
  }, 0);

  return (
    <div className="mt-3 pt-3 border-t">
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5 flex-wrap gap-1">
        <span className="flex items-center gap-1 sm:gap-2">
          <span>{completed}/{total} steps</span>
          {failed > 0 && <span className="text-destructive">({failed} failed)</span>}
          {inProgress > 0 && <span className="text-blue-500">(1 running)</span>}
        </span>
        <span className="flex items-center gap-1 sm:gap-2">
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
    currentPlanId,
    planStatus,
    planSteps,
    currentStepIndex,
    approvePlan,
    rejectPlan,
    clearPlan,
    currentConversation,
    planChanges,
    todoProgress,
    planBranch,
    branchMismatchWarning,
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
  const isPaused = planStatus === "PAUSED";

  const statusConfig = {
    DRAFT: { label: "Draft", variant: "secondary" as const, icon: Pencil },
    PENDING: { label: "Pending", variant: "outline" as const, icon: Clock },
    APPROVED: {
      label: isExecuting ? "Running" : "Approved",
      variant: "default" as const,
      icon: isExecuting ? Loader2 : Check,
    },
    PAUSED: { label: "Paused", variant: "outline" as const, icon: Clock },
    REJECTED: { label: "Rejected", variant: "destructive" as const, icon: X },
    COMPLETED: { label: "Done", variant: "default" as const, icon: Check },
  };

  const status = planStatus && statusConfig[planStatus] ? statusConfig[planStatus] : statusConfig.DRAFT;
  const StatusIcon = status.icon;
  const showActions = planStatus === "PENDING" || planStatus === "DRAFT";

  // Build todo progress map per step
  const getTodoProgressMap = (stepId: string): Record<number, TodoProgress> => {
    const progress = todoProgress[stepId] || [];
    return progress.reduce((acc, p) => {
      acc[p.todoIndex] = p;
      return acc;
    }, {} as Record<number, TodoProgress>);
  };

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("border-b bg-muted/30", className)}
    >
      <div className="flex items-center justify-between px-3 sm:px-4 py-2">
        <CollapsibleTrigger asChild>
          <div className="flex items-center gap-1.5 sm:gap-2 flex-1 cursor-pointer hover:opacity-80 transition-opacity min-w-0">
            <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="text-sm font-medium hidden sm:inline">Plan</span>
            <Badge variant={status.variant} className="h-5 text-[10px] sm:text-xs shrink-0">
              <StatusIcon className={cn("h-3 w-3 mr-0.5 sm:mr-1", isExecuting && "animate-spin")} />
              <span className="hidden xs:inline">{status.label}</span>
            </Badge>
            {planBranch && (
              <Badge variant="outline" className="h-5 text-[10px] sm:text-xs shrink-0 gap-0.5">
                <GitBranch className="h-3 w-3" />
                <span className="hidden sm:inline max-w-[60px] truncate">{planBranch}</span>
              </Badge>
            )}
            {planSteps.length > 0 && (
              <span className="text-[10px] text-muted-foreground shrink-0">
                {planSteps.filter((s) => s.status === "completed").length}/{planSteps.length}
              </span>
            )}
            {isOpen ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground ml-auto shrink-0" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground ml-auto shrink-0" />
            )}
          </div>
        </CollapsibleTrigger>
        <Button
          variant="ghost"
          size="icon"
          onClick={(e) => { e.stopPropagation(); clearPlan(); }}
          className="h-7 w-7 ml-1 sm:ml-2 shrink-0 text-muted-foreground hover:text-foreground hover:bg-destructive/10"
          title="Dismiss plan"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      <CollapsibleContent>
        {branchMismatchWarning && (
          <div className="mx-3 sm:mx-4 mb-2 mt-2 p-2 rounded-md bg-amber-500/10 border border-amber-500/30 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
            <p className="text-xs text-amber-600 dark:text-amber-400">
              <span className="font-medium">Branch mismatch:</span> Plan was created on{" "}
              <code className="bg-amber-500/20 px-1 rounded">{branchMismatchWarning.planBranch}</code>{" "}
              but you&apos;re now on{" "}
              <code className="bg-amber-500/20 px-1 rounded">{branchMismatchWarning.currentBranch}</code>
            </p>
          </div>
        )}
        <div className="px-3 sm:px-4 pb-3">
          <div className="max-h-[50vh] sm:max-h-80 overflow-y-auto overscroll-contain touch-pan-y">
            {planSteps.length > 0 ? (
              <div className="py-2 space-y-0.5">
                {planSteps.map((step, index) => (
                  <StepItem
                    key={step.id}
                    step={step}
                    index={index}
                    isLast={index === planSteps.length - 1}
                    todoProgressMap={getTodoProgressMap(step.id)}
                    planId={currentPlanId || undefined}
                  />
                ))}
                <ProgressBar steps={planSteps} />
              </div>
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <MarkdownRenderer content={currentPlan} />
              </div>
            )}
          </div>

          {/* Plan Changelog */}
          {planChanges.length > 0 && (
            <PlanChangelog changes={planChanges} maxVisible={3} />
          )}

          {showActions && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t">
              <Button
                variant="default"
                size="sm"
                onClick={handleApprove}
                disabled={isApproving || isRejecting}
                className="flex-1 h-9"
              >
                <Check className="h-4 w-4 mr-1 sm:mr-2" />
                <span className="hidden sm:inline">{isApproving ? "Approving..." : "Approve Plan"}</span>
                <span className="sm:hidden">{isApproving ? "..." : "Approve"}</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleReject}
                disabled={isApproving || isRejecting}
                className="flex-1 h-9"
              >
                <X className="h-4 w-4 mr-1 sm:mr-2" />
                <span className="hidden sm:inline">{isRejecting ? "Rejecting..." : "Reject"}</span>
                <span className="sm:hidden">{isRejecting ? "..." : "Reject"}</span>
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
