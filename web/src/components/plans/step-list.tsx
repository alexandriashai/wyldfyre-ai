"use client";

import { useState } from "react";
import { StepProgress } from "@/lib/api";
import { usePlansStore } from "@/stores/plans-store";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { StepEditor } from "./step-editor";
import { StepContextMenu } from "./step-context-menu";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Square,
  CheckSquare,
  Loader2,
  AlertCircle,
  SkipForward,
  Plus,
  GripVertical,
} from "lucide-react";

interface StepListProps {
  steps: StepProgress[];
  currentStepIndex: number;
  planId: string;
  isEditing?: boolean;
}

const STEP_ICONS = {
  pending: Square,
  in_progress: Loader2,
  completed: CheckSquare,
  failed: AlertCircle,
  skipped: SkipForward,
};

const STEP_COLORS = {
  pending: "text-muted-foreground",
  in_progress: "text-blue-500",
  completed: "text-green-500",
  failed: "text-red-500",
  skipped: "text-yellow-500",
};

interface StepItemProps {
  step: StepProgress;
  index: number;
  isLast: boolean;
  isActive: boolean;
  planId: string;
  isEditing?: boolean;
  onEdit?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  onDelete?: () => void;
  onAddBefore?: () => void;
  onAddAfter?: () => void;
}

function StepItem({
  step,
  index,
  isLast,
  isActive,
  planId,
  isEditing,
  onEdit,
  onMoveUp,
  onMoveDown,
  onDelete,
  onAddBefore,
  onAddAfter,
}: StepItemProps) {
  const [isExpanded, setIsExpanded] = useState(isActive);
  const [showEditor, setShowEditor] = useState(false);
  const { token } = useAuthStore();
  const { updateStep } = usePlansStore();

  // Sortable hook for drag-and-drop
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: step.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 100 : 1,
  };

  const Icon = STEP_ICONS[step.status] || Square;
  const colorClass = STEP_COLORS[step.status] || "text-muted-foreground";

  const todoProgress = step.total_todos > 0
    ? (step.completed_todos / step.total_todos) * 100
    : 0;

  const handleSaveEdit = async (data: Partial<StepProgress>) => {
    if (!token) return;
    await updateStep(token, planId, step.id, data);
    setShowEditor(false);
  };

  if (showEditor) {
    return (
      <StepEditor
        step={step}
        onSave={handleSaveEdit}
        onCancel={() => setShowEditor(false)}
      />
    );
  }

  return (
    <div ref={setNodeRef} style={style}>
      <StepContextMenu
        step={step}
        canMoveUp={index > 0}
        canMoveDown={!isLast}
        isEditing={isEditing}
        onEdit={() => setShowEditor(true)}
        onMoveUp={onMoveUp}
        onMoveDown={onMoveDown}
        onDelete={onDelete}
        onAddBefore={onAddBefore}
        onAddAfter={onAddAfter}
      >
        <div className="relative">
          {/* Connecting line */}
          {!isLast && !isDragging && (
            <div className={cn(
              "absolute left-[11px] top-[28px] w-px h-[calc(100%-12px)]",
              step.status === "completed" ? "bg-green-500/40" : "bg-border"
            )} />
          )}

          <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
            <div
              className={cn(
                "flex items-start gap-2 p-2 rounded-md transition-all duration-300 cursor-pointer",
                isActive && "bg-blue-500/10 border border-blue-500/30",
                step.status === "completed" && "bg-green-500/5",
                step.status === "failed" && "bg-red-500/5 border border-red-500/20",
                isDragging && "shadow-lg bg-card"
              )}
              onDoubleClick={() => setShowEditor(true)}
            >
              {/* Drag handle when editing */}
              {isEditing && (
                <div {...attributes} {...listeners}>
                  <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab active:cursor-grabbing shrink-0 mt-1 hover:text-foreground" />
                </div>
              )}

            {/* Status icon */}
            <div className="relative shrink-0">
              <Icon className={cn(
                "h-5 w-5 mt-0.5 transition-all duration-300",
                colorClass,
                isActive && step.status === "in_progress" && "animate-spin"
              )} />
              {isActive && step.status === "in_progress" && (
                <div className="absolute inset-0 animate-ping">
                  <div className="h-5 w-5 rounded-full bg-blue-500/20" />
                </div>
              )}
            </div>

            {/* Step content */}
            <div className="flex-1 min-w-0">
              <CollapsibleTrigger className="flex items-center gap-1.5 w-full text-left">
                <span className={cn(
                  "font-medium text-sm transition-all duration-300 flex-1",
                  step.status === "completed" && "line-through text-muted-foreground"
                )}>
                  {step.title}
                </span>
                {step.agent && (
                  <Badge variant="outline" className="text-[10px] h-4 px-1.5 shrink-0">
                    {step.agent}
                  </Badge>
                )}
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                )}
              </CollapsibleTrigger>

              <CollapsibleContent>
                {/* Description */}
                {step.description && (
                  <p className="text-xs text-muted-foreground mt-1.5">
                    {step.description}
                  </p>
                )}

                {/* Todos */}
                {step.todos && step.todos.length > 0 && (
                  <div className="mt-2 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-muted-foreground">
                        Todos ({step.completed_todos}/{step.total_todos})
                      </span>
                      {step.total_todos > 0 && (
                        <Progress value={todoProgress} className="h-1 flex-1" />
                      )}
                    </div>
                    <ul className="space-y-1">
                      {step.todos.map((todo, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-1.5 text-xs"
                        >
                          <span className="mt-0.5 shrink-0">
                            {i < step.completed_todos ? (
                              <Check className="h-3 w-3 text-green-500" />
                            ) : (
                              <Square className="h-3 w-3 text-muted-foreground" />
                            )}
                          </span>
                          <span className={cn(
                            i < step.completed_todos && "text-muted-foreground line-through"
                          )}>
                            {todo.text || (typeof todo === "string" ? todo : "")}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Notes */}
                {step.notes && step.notes.length > 0 && (
                  <div className="mt-2">
                    <span className="text-[10px] text-muted-foreground">Notes:</span>
                    <ul className="mt-1 space-y-0.5">
                      {step.notes.map((note, i) => (
                        <li key={i} className="text-xs text-muted-foreground italic">
                          {note}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Error */}
                {step.error && step.status === "failed" && (
                  <div className="mt-2 p-2 rounded bg-red-500/10 border border-red-500/20">
                    <p className="text-xs text-red-600 dark:text-red-400">
                      {step.error}
                    </p>
                  </div>
                )}

                {/* Output preview */}
                {step.output && step.status === "completed" && (
                  <div className="mt-2">
                    <span className="text-[10px] text-muted-foreground">Output:</span>
                    <pre className="mt-1 text-[10px] text-muted-foreground bg-muted/50 rounded p-2 overflow-x-auto max-h-20 overflow-y-auto whitespace-pre-wrap break-all border">
                      {step.output.slice(0, 500)}
                      {step.output.length > 500 && "..."}
                    </pre>
                  </div>
                )}

                {/* Timestamps */}
                {(step.started_at || step.completed_at) && (
                  <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
                    {step.started_at && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Started: {new Date(step.started_at).toLocaleTimeString()}
                      </span>
                    )}
                    {step.completed_at && (
                      <span className="flex items-center gap-1">
                        <Check className="h-3 w-3" />
                        Completed: {new Date(step.completed_at).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                )}
              </CollapsibleContent>
            </div>
          </div>
          </Collapsible>
        </div>
      </StepContextMenu>
    </div>
  );
}

export function StepList({ steps, currentStepIndex, planId, isEditing }: StepListProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
  const { token } = useAuthStore();
  const { addStep, removeStep, reorderSteps } = usePlansStore();
  const [isAddingStep, setIsAddingStep] = useState(false);
  const [addAfterStepId, setAddAfterStepId] = useState<string | null>(null);

  const handleAddStep = async (data: Partial<StepProgress>) => {
    if (!token) return;
    await addStep(token, planId, addAfterStepId, data);
    setIsAddingStep(false);
    setAddAfterStepId(null);
  };

  const handleMoveStep = async (stepId: string, direction: "up" | "down") => {
    if (!token) return;
    const currentIndex = steps.findIndex((s) => s.id === stepId);
    if (currentIndex === -1) return;

    const newIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
    if (newIndex < 0 || newIndex >= steps.length) return;

    const newOrder = [...steps.map((s) => s.id)];
    [newOrder[currentIndex], newOrder[newIndex]] = [newOrder[newIndex], newOrder[currentIndex]];
    await reorderSteps(token, planId, newOrder);
  };

  const handleDeleteStep = async (stepId: string) => {
    if (!token) return;
    if (!confirm("Are you sure you want to delete this step?")) return;
    await removeStep(token, planId, stepId);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id || !token) return;

    const oldIndex = steps.findIndex((s) => s.id === active.id);
    const newIndex = steps.findIndex((s) => s.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    // Create new order array
    const newOrder = [...steps.map((s) => s.id)];
    const [removed] = newOrder.splice(oldIndex, 1);
    newOrder.splice(newIndex, 0, removed);

    await reorderSteps(token, planId, newOrder);
  };

  if (steps.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
        <Square className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">No steps defined</p>
        {isEditing && (
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => {
              setAddAfterStepId(null);
              setIsAddingStep(true);
            }}
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Step
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {/* Add step at beginning when editing */}
      {isEditing && !isAddingStep && (
        <Button
          variant="ghost"
          size="sm"
          className="w-full h-7 text-xs text-muted-foreground"
          onClick={() => {
            setAddAfterStepId(null);
            setIsAddingStep(true);
          }}
        >
          <Plus className="h-3 w-3 mr-1" />
          Add step at beginning
        </Button>
      )}

      {isAddingStep && addAfterStepId === null && (
        <StepEditor
          onSave={handleAddStep}
          onCancel={() => {
            setIsAddingStep(false);
            setAddAfterStepId(null);
          }}
        />
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={steps.map((s) => s.id)}
          strategy={verticalListSortingStrategy}
        >
          {steps.map((step, index) => (
            <div key={step.id}>
              <StepItem
                step={step}
                index={index}
                isLast={index === steps.length - 1}
                isActive={index === currentStepIndex}
                planId={planId}
                isEditing={isEditing}
                onEdit={() => {}}
                onMoveUp={() => handleMoveStep(step.id, "up")}
                onMoveDown={() => handleMoveStep(step.id, "down")}
                onDelete={() => handleDeleteStep(step.id)}
                onAddBefore={() => {
                  setAddAfterStepId(index > 0 ? steps[index - 1].id : null);
                  setIsAddingStep(true);
                }}
                onAddAfter={() => {
                  setAddAfterStepId(step.id);
                  setIsAddingStep(true);
                }}
              />

              {/* Add step after this one when editing */}
              {isAddingStep && addAfterStepId === step.id && (
                <StepEditor
                  onSave={handleAddStep}
                  onCancel={() => {
                    setIsAddingStep(false);
                    setAddAfterStepId(null);
                  }}
                />
              )}
            </div>
          ))}
        </SortableContext>
      </DndContext>
    </div>
  );
}
