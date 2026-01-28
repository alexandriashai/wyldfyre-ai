"use client";

import { ReactNode } from "react";
import { StepProgress } from "@/lib/api";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
  Pencil,
  Trash2,
  ArrowUp,
  ArrowDown,
  Plus,
  SkipForward,
  RotateCcw,
} from "lucide-react";

interface StepContextMenuProps {
  step: StepProgress;
  canMoveUp: boolean;
  canMoveDown: boolean;
  isEditing?: boolean;
  children: ReactNode;
  onEdit?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  onDelete?: () => void;
  onAddBefore?: () => void;
  onAddAfter?: () => void;
  onSkip?: () => void;
  onRetry?: () => void;
}

export function StepContextMenu({
  step,
  canMoveUp,
  canMoveDown,
  isEditing,
  children,
  onEdit,
  onMoveUp,
  onMoveDown,
  onDelete,
  onAddBefore,
  onAddAfter,
  onSkip,
  onRetry,
}: StepContextMenuProps) {
  const isPending = step.status === "pending";
  const isFailed = step.status === "failed";
  const isCompleted = step.status === "completed";
  const isInProgress = step.status === "in_progress";

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        {children}
      </ContextMenuTrigger>
      <ContextMenuContent className="w-48">
        {/* Edit actions - only when in edit mode */}
        {isEditing && (
          <>
            <ContextMenuItem onClick={onEdit}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit Step
            </ContextMenuItem>

            <ContextMenuSeparator />

            <ContextMenuItem onClick={onAddBefore}>
              <Plus className="h-4 w-4 mr-2" />
              Add Step Before
            </ContextMenuItem>

            <ContextMenuItem onClick={onAddAfter}>
              <Plus className="h-4 w-4 mr-2" />
              Add Step After
            </ContextMenuItem>

            <ContextMenuSeparator />

            {canMoveUp && (
              <ContextMenuItem onClick={onMoveUp}>
                <ArrowUp className="h-4 w-4 mr-2" />
                Move Up
              </ContextMenuItem>
            )}

            {canMoveDown && (
              <ContextMenuItem onClick={onMoveDown}>
                <ArrowDown className="h-4 w-4 mr-2" />
                Move Down
              </ContextMenuItem>
            )}

            {(canMoveUp || canMoveDown) && <ContextMenuSeparator />}

            <ContextMenuItem
              onClick={onDelete}
              className="text-destructive focus:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Remove Step
            </ContextMenuItem>
          </>
        )}

        {/* Runtime actions - always show edit and skip/retry */}
        {!isEditing && (
          <>
            <ContextMenuItem onClick={onEdit}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit Step
            </ContextMenuItem>

            {(isPending || isFailed) && <ContextMenuSeparator />}

            {isPending && onSkip && (
              <ContextMenuItem onClick={onSkip}>
                <SkipForward className="h-4 w-4 mr-2" />
                Skip Step
              </ContextMenuItem>
            )}

            {isFailed && onRetry && (
              <ContextMenuItem onClick={onRetry}>
                <RotateCcw className="h-4 w-4 mr-2" />
                Retry Step
              </ContextMenuItem>
            )}
          </>
        )}
      </ContextMenuContent>
    </ContextMenu>
  );
}
