"use client";

import { useChatStore, ActiveTask, ActiveTaskTodo } from "@/stores/chat-store";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Check,
  Square,
  Loader2,
  Info,
  X,
  ListTodo,
} from "lucide-react";

interface ActiveTasksPanelProps {
  className?: string;
}

interface TodoItemProps {
  todo: ActiveTaskTodo;
  index: number;
}

function TodoItem({ todo, index }: TodoItemProps) {
  const isCompleted = todo.status === "completed";
  const isInProgress = todo.status === "in_progress";
  const isFailed = todo.status === "failed";

  return (
    <li className="flex flex-col gap-0.5">
      <div className="flex items-start gap-1.5 text-xs">
        <span className="mt-0.5 shrink-0">
          {isCompleted ? (
            <Check className="h-3 w-3 text-green-500" />
          ) : isFailed ? (
            <X className="h-3 w-3 text-red-500" />
          ) : isInProgress ? (
            <Loader2 className="h-3 w-3 text-blue-500 animate-spin" />
          ) : (
            <Square className="h-3 w-3 text-muted-foreground" />
          )}
        </span>
        <span className={cn(
          "flex-1",
          isCompleted && "text-muted-foreground line-through",
          isFailed && "text-red-500",
          !isCompleted && !isFailed && "text-foreground/80"
        )}>
          {todo.text}
        </span>
        {isInProgress && todo.progress > 0 && todo.progress < 100 && (
          <span className="text-[10px] text-blue-500 font-mono shrink-0">
            {todo.progress}%
          </span>
        )}
      </div>

      {/* Progress bar for in-progress todos */}
      {isInProgress && todo.progress > 0 && todo.progress < 100 && (
        <div className="ml-4 flex items-center gap-2">
          <Progress value={todo.progress} className="h-1 flex-1" />
        </div>
      )}

      {/* Status message */}
      {todo.statusMessage && (
        <div className="ml-4 flex items-start gap-1 text-[10px] text-muted-foreground">
          <Info className="h-2.5 w-2.5 mt-0.5 shrink-0" />
          <span>{todo.statusMessage}</span>
        </div>
      )}
    </li>
  );
}

interface TaskCardProps {
  task: ActiveTask;
  onDismiss?: () => void;
}

function TaskCard({ task, onDismiss }: TaskCardProps) {
  const completedTodos = task.todos.filter((t) => t.status === "completed").length;
  const totalTodos = task.todos.length;
  const overallProgress = totalTodos > 0 ? (completedTodos / totalTodos) * 100 : 0;
  const hasInProgress = task.todos.some((t) => t.status === "in_progress");

  return (
    <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          {hasInProgress ? (
            <Loader2 className="h-4 w-4 text-blue-500 animate-spin shrink-0" />
          ) : (
            <ListTodo className="h-4 w-4 text-blue-500 shrink-0" />
          )}
          <span className="text-sm font-medium truncate">{task.description}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {task.agent && (
            <Badge variant="outline" className="text-[10px] h-4 px-1.5">
              {task.agent}
            </Badge>
          )}
          {onDismiss && (
            <Button
              variant="ghost"
              size="sm"
              className="h-5 w-5 p-0 text-muted-foreground hover:text-foreground"
              onClick={onDismiss}
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
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

      {/* Todos list */}
      {task.todos.length > 0 && (
        <ul className="space-y-1">
          {task.todos.map((todo, i) => (
            <TodoItem key={i} todo={todo} index={i} />
          ))}
        </ul>
      )}
    </div>
  );
}

export function ActiveTasksPanel({ className }: ActiveTasksPanelProps) {
  const activeTasks = useChatStore((state) => state.activeTasks);
  const removeActiveTask = useChatStore((state) => state.removeActiveTask);
  const planSteps = useChatStore((state) => state.planSteps);

  // Don't show if there are no active tasks or if we're in plan mode
  if (activeTasks.size === 0 || planSteps.length > 0) return null;

  const tasksArray = Array.from(activeTasks.values());

  return (
    <div className={cn("px-4 py-2 border-b space-y-2", className)}>
      {tasksArray.map((task) => (
        <TaskCard
          key={task.id}
          task={task}
          onDismiss={() => removeActiveTask(task.id)}
        />
      ))}
    </div>
  );
}
