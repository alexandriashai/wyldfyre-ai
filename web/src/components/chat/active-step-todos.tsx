"use client";

import { useChatStore, PlanStep, TodoProgress } from "@/stores/chat-store";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import {
  Check,
  Square,
  Loader2,
  Info,
  ExternalLink,
  ChevronRight,
} from "lucide-react";

interface ActiveStepTodosProps {
  className?: string;
}

interface TodoItemProps {
  todo: string;
  index: number;
  stepId: string;
  progress?: TodoProgress;
  isStepCompleted: boolean;
}

function TodoItem({ todo, index, stepId, progress, isStepCompleted }: TodoItemProps) {
  const isCompleted = isStepCompleted || (progress && progress.progress >= 100);
  const isInProgress = progress && progress.progress > 0 && progress.progress < 100;

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
      {progress?.statusMessage && (
        <div className="ml-4 flex items-start gap-1 text-[10px] text-muted-foreground">
          <Info className="h-2.5 w-2.5 mt-0.5 shrink-0" />
          <span>{progress.statusMessage}</span>
        </div>
      )}
    </li>
  );
}

export function ActiveStepTodos({ className }: ActiveStepTodosProps) {
  const {
    planSteps,
    currentStepIndex,
    currentPlanId,
    todoProgress,
  } = useChatStore();

  // Get current active step
  const activeStep = planSteps.find((s) => s.status === "in_progress") ||
    planSteps[currentStepIndex];

  if (!activeStep || planSteps.length === 0) return null;

  // Get todo progress for this step
  const stepProgress = todoProgress[activeStep.id] || [];
  const progressMap: Record<number, TodoProgress> = {};
  stepProgress.forEach((p) => {
    progressMap[p.todoIndex] = p;
  });

  // Count completed todos
  const completedTodos = activeStep.todos?.filter((_, i) => {
    const progress = progressMap[i];
    return activeStep.status === "completed" || (progress && progress.progress >= 100);
  }).length || 0;
  const totalTodos = activeStep.todos?.length || 0;
  const overallProgress = totalTodos > 0 ? (completedTodos / totalTodos) * 100 : 0;

  return (
    <div className={cn(
      "px-4 py-2 border-b bg-blue-500/5 border-blue-500/20",
      className
    )}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Loader2 className="h-4 w-4 text-blue-500 animate-spin shrink-0" />
          <span className="text-sm font-medium truncate">{activeStep.title}</span>
          {activeStep.agent && (
            <Badge variant="outline" className="text-[10px] h-4 px-1.5 shrink-0">
              {activeStep.agent}
            </Badge>
          )}
        </div>
        {currentPlanId && (
          <Link href={`/workspace/plans?id=${currentPlanId}`}>
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground">
              <ExternalLink className="h-3 w-3 mr-1" />
              View Plan
            </Button>
          </Link>
        )}
      </div>

      {/* Progress summary */}
      {totalTodos > 0 && (
        <div className="flex items-center gap-2 mb-2">
          <Progress value={overallProgress} className="h-1.5 flex-1" />
          <span className="text-[10px] text-muted-foreground shrink-0">
            {completedTodos}/{totalTodos}
          </span>
        </div>
      )}

      {/* Todos list - compact view */}
      {activeStep.todos && activeStep.todos.length > 0 && (
        <ul className="space-y-1">
          {activeStep.todos.map((todo, i) => (
            <TodoItem
              key={i}
              todo={typeof todo === "string" ? todo : (todo as any).text || ""}
              index={i}
              stepId={activeStep.id}
              progress={progressMap[i]}
              isStepCompleted={activeStep.status === "completed"}
            />
          ))}
        </ul>
      )}

      {/* Step progress info */}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-blue-500/10">
        <span className="text-[10px] text-muted-foreground">
          Step {currentStepIndex + 1} of {planSteps.length}
        </span>
        <div className="flex items-center gap-2">
          {planSteps.filter((s) => s.status === "completed").length > 0 && (
            <span className="text-[10px] text-green-500">
              {planSteps.filter((s) => s.status === "completed").length} completed
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
